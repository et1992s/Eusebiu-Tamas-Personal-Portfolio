from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
import threading

from .tools import ToolRisk


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    approval_id: str
    session_id: str
    task_id: str
    step_id: str
    tool_name: str
    arguments: dict
    tool_call_id: str | None
    risk: ToolRisk
    status: ApprovalStatus
    created_at: datetime
    resolved_at: datetime | None = None
    resolution: str | None = None
    error: str | None = None


class ApprovalManager:
    """Manages the lifecycle of tool approval requests."""

    def __init__(self):
        self.requests: dict[str, ApprovalRequest] = {}
        self.lock = threading.Lock()

    def create(
        self,
        session_id: str,
        task_id: str,
        step_id: str,
        tool_name: str,
        arguments: dict,
        risk: ToolRisk,
        tool_call_id: str | None = None,
    ) -> ApprovalRequest:
        approval_id = str(uuid4())

        request = ApprovalRequest(
            approval_id=approval_id,
            task_id=task_id,
            session_id=session_id,
            step_id=step_id,
            tool_name=tool_name,
            arguments=arguments.copy(),
            risk=risk,
            tool_call_id=tool_call_id,
            status=ApprovalStatus.PENDING,
            created_at=datetime.now(timezone.utc),
        )

        self.requests[approval_id] = request

        return request

    def get(self, approval_id: str) -> ApprovalRequest:
        if approval_id not in self.requests:
            raise KeyError(f"Unknown approval request: {approval_id}")

        return self.requests[approval_id]

    def get_for_task(self, task_id: str) -> list[ApprovalRequest]:
        with self.lock:
            return [
                request
                for request in self.requests.values()
                if request.task_id == task_id
            ]

    def approve(self, approval_id: str) -> ApprovalRequest:
        with self.lock:
            request = self.get(approval_id)

            if request.status != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Cannot approve request in state: {request.status.value}"
                )

            request.status = ApprovalStatus.APPROVED
            request.resolved_at = datetime.now(timezone.utc)
            request.resolution = "user_approved"

            return request

    def reject(self, approval_id: str) -> ApprovalRequest:
        with self.lock:
            request = self.get(approval_id)

            if request.status != ApprovalStatus.PENDING:
                raise ValueError(
                    f"Cannot reject request in state: {request.status.value}"
                )

            request.status = ApprovalStatus.REJECTED
            request.resolved_at = datetime.now(timezone.utc)
            request.resolution = "user_rejected"

            return request

    def begin_execution(self, approval_id: str) -> ApprovalRequest:
        with self.lock:
            request = self.get(approval_id)

            if request.status != ApprovalStatus.APPROVED:
                raise ValueError(
                    f"Cannot begin execution in state: {request.status.value}"
                )

            request.status = ApprovalStatus.EXECUTING

            return request

    def complete(self, approval_id: str) -> ApprovalRequest:
        with self.lock:
            request = self.get(approval_id)

            if request.status != ApprovalStatus.EXECUTING:
                raise ValueError(
                    f"Cannot complete request in state: {request.status.value}"
                )

            request.status = ApprovalStatus.EXECUTED

            return request

    def fail(
        self,
        approval_id: str,
        error: str,
    ) -> ApprovalRequest:
        with self.lock:
            request = self.get(approval_id)

            if request.status != ApprovalStatus.EXECUTING:
                raise ValueError(
                    f"Cannot fail request in state: {request.status.value}"
                )

            request.status = ApprovalStatus.FAILED
            request.error = error

            return request    