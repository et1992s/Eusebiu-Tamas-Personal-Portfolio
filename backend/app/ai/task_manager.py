from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import threading
from uuid import uuid4

from .schemas import Observation


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskStep:
    step_id: str
    task_id: str
    tool_name: str
    arguments: dict
    status: TaskStepStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    error: str | None = None


@dataclass
class Task:
    task_id: str
    session_id: str
    goal: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    current_step: str | None = None
    current_thought: str | None = None
    final_response: str | None = None
    observations: list[dict] | None = None
    verification_status: str | None = None
    requires_verification: bool = False
    verification_summary: str | None = None
    verification_evidence: list[dict] | None = None
    errors: list[str] | None = None


class TaskManager:
    """
    Manages the lifecycle of Zebio tasks.

    Responsibilities:

        - task and step state
        - current thought / final response
        - append-only event log per task for real-time streaming

    The event log is what enables the SSE endpoint to push state
    changes the instant they happen, rather than waiting for the
    next polling interval.

    Every public mutation appends an event. Consumers read events
    by monotonically increasing sequence number so no update is
    ever missed, even across reconnects.

    Locking:

        All mutations and event appends share a single lock. The
        `_append_event_unlocked` helper must only be called while
        the lock is held. `publish_event` is the public entry point
        that acquires the lock itself.
    """

    # Cap the per-task event log so a runaway task cannot leak memory.
    # When the log exceeds MAX_EVENTS, the oldest half is dropped.
    # Consumers that reconnect after that point will still get a
    # fresh snapshot from the stream endpoint, so dropping history
    # is safe.
    MAX_EVENTS = 2000

    def __init__(self):
        self.tasks: dict[str, Task] = {}
        self.steps: dict[str, TaskStep] = {}
        self.lock = threading.Lock()

        self.events: dict[str, list[dict]] = {}
        self.event_seq: dict[str, int] = {}

    # ==================================================================
    # EVENT LOG
    # ==================================================================

    def _append_event_unlocked(
        self,
        task_id: str,
        event_type: str,
        data: dict,
        timestamp: datetime,
    ) -> None:
        """Append one event. Caller must hold `self.lock`."""
        seq = self.event_seq.get(task_id, 0) + 1
        self.event_seq[task_id] = seq

        self.events.setdefault(task_id, []).append(
            {
                "seq": seq,
                "type": event_type,
                "data": data,
                "timestamp": timestamp.isoformat(),
            }
        )

        if len(self.events[task_id]) > self.MAX_EVENTS:
            # Drop the oldest half in one go to keep amortised
            # cost low.
            del self.events[task_id][: self.MAX_EVENTS // 2]

    def publish_event(
        self,
        task_id: str,
        event_type: str,
        data: dict,
    ) -> None:
        """Public entry point for external event emission."""
        with self.lock:
            self._get_unlocked(task_id)
            self._append_event_unlocked(
                task_id,
                event_type,
                data,
                datetime.now(timezone.utc),
            )

    def get_events_since(
        self,
        task_id: str,
        since_seq: int,
    ) -> list[dict]:
        with self.lock:
            return [
                event
                for event in self.events.get(task_id, [])
                if event["seq"] > since_seq
            ]

    def get_max_seq(self, task_id: str) -> int:
        with self.lock:
            return self.event_seq.get(task_id, 0)

    # ==================================================================
    # TASK LIFECYCLE
    # ==================================================================

    def create(
        self,
        session_id: str,
        goal: str,
        requires_verification: bool = False,
    ) -> Task:
        now = datetime.now(timezone.utc)

        task = Task(
            task_id=str(uuid4()),
            session_id=session_id,
            goal=goal,
            status=TaskStatus.PENDING,
            created_at=now,
            updated_at=now,
            requires_verification=requires_verification,
        )

        with self.lock:
            self.tasks[task.task_id] = task

            self._append_event_unlocked(
                task.task_id,
                "status",
                {"status": task.status.value},
                now,
            )

        return task

    def get(self, task_id: str) -> Task:
        with self.lock:
            return self._get_unlocked(task_id)

    def _get_unlocked(self, task_id: str) -> Task:
        if task_id not in self.tasks:
            raise KeyError(f"Unknown task: {task_id}")

        return self.tasks[task_id]

    def start(self, task_id: str) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status != TaskStatus.PENDING:
                raise ValueError(
                    f"Cannot start task in state: {task.status.value}"
                )

            now = datetime.now(timezone.utc)

            task.status = TaskStatus.RUNNING
            task.updated_at = now

            self._append_event_unlocked(
                task_id,
                "status",
                {"status": task.status.value},
                now,
            )

            return task

    def complete(self, task_id: str) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Cannot complete task in state: {task.status.value}"
                )

            if task.requires_verification:
                if (
                    task.verification_status != "succeeded"
                    or not task.verification_evidence
                ):
                    raise ValueError(
                        "Cannot complete task without successful "
                        "verification evidence."
                    )

            now = datetime.now(timezone.utc)

            task.status = TaskStatus.COMPLETED
            task.updated_at = now
            task.completed_at = now

            self._append_event_unlocked(
                task_id,
                "status",
                {
                    "status": task.status.value,
                    "completed_at": now.isoformat(),
                },
                now,
            )

            return task

    def fail(self, task_id: str, error: str) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Cannot fail task in state: {task.status.value}"
                )

            now = datetime.now(timezone.utc)

            task.status = TaskStatus.FAILED
            task.updated_at = now
            task.errors = (task.errors or []) + [error]

            self._append_event_unlocked(
                task_id,
                "status",
                {
                    "status": task.status.value,
                    "error": error,
                },
                now,
            )

            return task

    def cancel(self, task_id: str) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status not in {
                TaskStatus.PENDING,
                TaskStatus.RUNNING,
            }:
                raise ValueError(
                    f"Cannot cancel task in state: {task.status.value}"
                )

            now = datetime.now(timezone.utc)

            task.status = TaskStatus.CANCELLED
            task.updated_at = now

            self._append_event_unlocked(
                task_id,
                "status",
                {"status": task.status.value},
                now,
            )

            return task

    # ==================================================================
    # TASK FIELDS
    # ==================================================================

    def set_current_step(self, task_id: str, step: str) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Cannot update step for task in state: {task.status.value}"
                )

            now = datetime.now(timezone.utc)

            task.current_step = step
            task.updated_at = now

            self._append_event_unlocked(
                task_id,
                "current_step",
                {"current_step": step},
                now,
            )

            return task

    def set_current_thought(self, task_id: str, thought: str) -> Task:
        """
        Publish the model's current reasoning. Unlike set_current_step
        this is allowed in any non-terminal state so a thought can
        still be set while awaiting approval.
        """
        with self.lock:
            task = self._get_unlocked(task_id)

            now = datetime.now(timezone.utc)

            task.current_thought = thought
            task.updated_at = now

            self._append_event_unlocked(
                task_id,
                "thought",
                {"thought": thought},
                now,
            )

            return task

    def set_final_response(self, task_id: str, response: str) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            now = datetime.now(timezone.utc)

            task.final_response = response
            task.updated_at = now

            self._append_event_unlocked(
                task_id,
                "final_response",
                {"final_response": response},
                now,
            )

            return task

    def attach_approval(
        self,
        step_id: str,
        approval_id: str,
        approval_status: str,
    ) -> None:
        """
        Associate an approval with a step and emit a `step` event so
        the streaming client sees it immediately.
        """
        with self.lock:
            step = self.steps.get(step_id)
            if step is None:
                return

            now = datetime.now(timezone.utc)
            step.updated_at = now

            self._append_event_unlocked(
                step.task_id,
                "step",
                {
                    "step_id": step.step_id,
                    "approval_id": approval_id,
                    "approval_status": approval_status,
                    "updated_at": now.isoformat(),
                },
                now,
            )

    def add_observation(
        self,
        task_id: str,
        observation: Observation | dict,
    ) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Cannot add observation for task in state: "
                    f"{task.status.value}"
                )

            if isinstance(observation, dict):
                observation = Observation.model_validate(observation)

            observation_record = {
                "observation_id": str(uuid4()),
                **observation.model_dump(),
            }

            task.observations = (
                task.observations or []
            ) + [observation_record]

            now = datetime.now(timezone.utc)
            task.updated_at = now

            self._append_event_unlocked(
                task_id,
                "observation",
                {"observation": observation_record},
                now,
            )

            return task

    def set_verification(
        self,
        task_id: str,
        status: str,
        summary: str,
        evidence: list[dict] | None = None,
    ) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Cannot set verification for task in state: "
                    f"{task.status.value}"
                )

            now = datetime.now(timezone.utc)

            task.verification_status = status
            task.verification_summary = summary
            task.verification_evidence = evidence or []
            task.updated_at = now

            self._append_event_unlocked(
                task_id,
                "verification",
                {
                    "status": status,
                    "summary": summary,
                    "evidence": evidence or [],
                },
                now,
            )

            return task

    # ==================================================================
    # STEP LIFECYCLE
    # ==================================================================

    def create_step(
        self,
        task_id: str,
        tool_name: str,
        arguments: dict,
    ) -> TaskStep:
        now = datetime.now(timezone.utc)

        with self.lock:
            self._get_unlocked(task_id)

            step = TaskStep(
                step_id=str(uuid4()),
                task_id=task_id,
                tool_name=tool_name,
                arguments=arguments.copy(),
                status=TaskStepStatus.PENDING,
                created_at=now,
                updated_at=now,
            )

            self.steps[step.step_id] = step

            self._append_event_unlocked(
                task_id,
                "step",
                {
                    "step_id": step.step_id,
                    "task_id": step.task_id,
                    "tool_name": step.tool_name,
                    "arguments": step.arguments,
                    "status": step.status.value,
                    "created_at": step.created_at.isoformat(),
                    "updated_at": step.updated_at.isoformat(),
                    "completed_at": None,
                    "error": None,
                },
                now,
            )

            return step

    def get_step(self, step_id: str) -> TaskStep:
        with self.lock:
            if step_id not in self.steps:
                raise KeyError(f"Unknown task step: {step_id}")
            return self.steps[step_id]

    def get_steps(self, task_id: str) -> list[TaskStep]:
        with self.lock:
            self._get_unlocked(task_id)

            return [
                step
                for step in self.steps.values()
                if step.task_id == task_id
            ]

    def get_latest_step(self, task_id: str) -> TaskStep | None:
        with self.lock:
            self._get_unlocked(task_id)

            task_steps = [
                step
                for step in self.steps.values()
                if step.task_id == task_id
            ]

            if not task_steps:
                return None

            return max(
                task_steps,
                key=lambda step: step.updated_at,
            )

    def start_step(self, step_id: str) -> TaskStep:
        with self.lock:
            step = self.steps.get(step_id)

            if step is None:
                raise KeyError(f"Unknown task step: {step_id}")

            if step.status != TaskStepStatus.PENDING:
                raise ValueError(
                    f"Cannot start task step in state: {step.status.value}"
                )

            now = datetime.now(timezone.utc)

            step.status = TaskStepStatus.RUNNING
            step.updated_at = now

            self._append_event_unlocked(
                step.task_id,
                "step",
                {
                    "step_id": step.step_id,
                    "status": step.status.value,
                    "updated_at": now.isoformat(),
                },
                now,
            )

            return step

    def complete_task_step(self, step_id: str) -> TaskStep:
        with self.lock:
            step = self.steps.get(step_id)

            if step is None:
                raise KeyError(f"Unknown task step: {step_id}")

            if step.status != TaskStepStatus.RUNNING:
                raise ValueError(
                    f"Cannot complete task step in state: {step.status.value}"
                )

            now = datetime.now(timezone.utc)

            step.status = TaskStepStatus.COMPLETED
            step.updated_at = now
            step.completed_at = now

            self._append_event_unlocked(
                step.task_id,
                "step",
                {
                    "step_id": step.step_id,
                    "status": step.status.value,
                    "updated_at": now.isoformat(),
                    "completed_at": now.isoformat(),
                },
                now,
            )

            return step

    def fail_task_step(
        self,
        step_id: str,
        error: str,
    ) -> TaskStep:
        with self.lock:
            step = self.steps.get(step_id)

            if step is None:
                raise KeyError(f"Unknown task step: {step_id}")

            if step.status != TaskStepStatus.RUNNING:
                raise ValueError(
                    f"Cannot fail task step in state: {step.status.value}"
                )

            now = datetime.now(timezone.utc)

            step.status = TaskStepStatus.FAILED
            step.updated_at = now
            step.error = error

            self._append_event_unlocked(
                step.task_id,
                "step",
                {
                    "step_id": step.step_id,
                    "status": step.status.value,
                    "updated_at": now.isoformat(),
                    "error": error,
                },
                now,
            )

            return step

    def cancel_task_step(self, step_id: str) -> TaskStep:
        with self.lock:
            step = self.steps.get(step_id)

            if step is None:
                raise KeyError(f"Unknown task step: {step_id}")

            if step.status not in (
                TaskStepStatus.PENDING,
                TaskStepStatus.RUNNING,
            ):
                raise ValueError(
                    f"Cannot cancel task step in state: {step.status.value}"
                )

            now = datetime.now(timezone.utc)

            step.status = TaskStepStatus.CANCELLED
            step.updated_at = now

            self._append_event_unlocked(
                step.task_id,
                "step",
                {
                    "step_id": step.step_id,
                    "status": step.status.value,
                    "updated_at": now.isoformat(),
                },
                now,
            )

            return step