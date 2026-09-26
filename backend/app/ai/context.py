from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import ActionDecision
from .task_manager import Task


@dataclass
class PendingAction:
    """
    Model action that has been produced but has not yet completed.

    The ActionDecision represents provider-neutral agent intent.
    tool_call_id is transport metadata and is present only when the
    model/provider supplied a native tool-call identifier.
    """

    decision: ActionDecision
    tool_call_id: str | None = None

@dataclass
class AgentLoopState:
    """
    Runtime state for one autonomous engineering loop.

    This state belongs to the execution process rather than the
    human conversation or the model protocol.
    """

    previous_signature: str | None = None
    repeated_call_count: int = 0
    invalid_request_count: int = 0
    tool_error_count: int = 0
    verification_started: bool = False

    completed_actions: list[str] = field(
        default_factory=list
    )


@dataclass
class AgentContext:
    """
    Runtime context used to construct the model-facing execution context.

    AgentContext is deliberately separate from:
    - ConversationStore: persistent human conversation
    - TaskManager: authoritative task state
    - Ollama's message protocol: temporary model interaction
    """

    task: Task
    conversation: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)
    pending_action: PendingAction | None = None
    loop_state: AgentLoopState = field(default_factory=AgentLoopState)
    runtime_feedback: RuntimeFeedback | None = None

    @property
    def task_id(self) -> str:
        return self.task.task_id

    @property
    def goal(self) -> str:
        return self.task.goal

@dataclass
class RuntimeFeedback:
    """
    Structured feedback produced by the runtime for the next model turn.
    """

    type: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)