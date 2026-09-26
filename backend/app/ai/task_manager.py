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
    observations: list[dict] | None = None
    verification_status: str | None = None
    requires_verification: bool = False
    verification_summary: str | None = None
    verification_evidence: list[dict] | None = None
    errors: list[str] | None = None


class TaskManager:
    """Manages the lifecycle of Zebio tasks."""

    def __init__(self):
        self.tasks: dict[str, Task] = {}
        self.steps: dict[str, TaskStep] = {}
        self.lock = threading.Lock()

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

        return task

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
            return step

    def get(self, task_id: str) -> Task:
        with self.lock:
            if task_id not in self.tasks:
                raise KeyError(f"Unknown task: {task_id}")

            return self.tasks[task_id]

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

            step.status = TaskStepStatus.RUNNING
            step.updated_at = datetime.now(timezone.utc)

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

            step.status = TaskStepStatus.FAILED
            step.updated_at = datetime.now(timezone.utc)
            step.error = error

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

            step.status = TaskStepStatus.CANCELLED
            step.updated_at = datetime.now(timezone.utc)

            return step    

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

            task.status = TaskStatus.RUNNING
            task.updated_at = datetime.now(timezone.utc)

            return task

    def complete(self, task_id: str) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Cannot complete task in state: {task.status.value}"
                )

            now = datetime.now(timezone.utc)

            if task.requires_verification:
                if (
                    task.verification_status != "succeeded"
                    or not task.verification_evidence
                ):
                    raise ValueError(
                        "Cannot complete task without successful verification evidence."
                    )

            task.status = TaskStatus.COMPLETED
            task.updated_at = now
            task.completed_at = now

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

            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.now(timezone.utc)

            return task

    def set_current_step(self, task_id: str, step: str) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Cannot update step for task in state: {task.status.value}"
                )

            task.current_step = step
            task.updated_at = datetime.now(timezone.utc)

            return task

    def add_observation(
        self,
        task_id: str,
        observation: Observation | dict,
    ) -> Task:
        with self.lock:
            task = self._get_unlocked(task_id)

            if task.status != TaskStatus.RUNNING:
                raise ValueError(
                    f"Cannot add observation for task in state: {task.status.value}"
                )

            if isinstance(observation, dict):
                observation = Observation.model_validate(observation)

            observation_record = {
                "observation_id": str(uuid4()),
                **observation.model_dump(),
            }

            task.observations = (task.observations or []) + [observation_record]
            task.updated_at = datetime.now(timezone.utc)

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
                    f"Cannot set verification for task in state: {task.status.value}"
                )

            task.verification_status = status
            task.verification_summary = summary
            task.verification_evidence = evidence or []
            task.updated_at = datetime.now(timezone.utc)

            return task