from datetime import datetime
import threading
from uuid import UUID

import pytest

from app.ai.approval import (
    ApprovalManager,
    ApprovalStatus,
)
from app.ai.tools import ToolRisk


def test_creates_pending_approval_request():
    manager = ApprovalManager()

    arguments = {
        "relative_path": "example.py",
        "content": "print('hello')",
    }

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments=arguments,
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    assert request.approval_id
    UUID(request.approval_id)

    assert request.session_id == "session-1"
    assert request.tool_name == "write_file"
    assert request.arguments == arguments
    assert request.risk == ToolRisk.LOW_RISK_WRITE
    assert request.status == ApprovalStatus.PENDING

    assert isinstance(request.created_at, datetime)
    assert request.resolved_at is None
    assert request.resolution is None


def test_approves_pending_request():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    approved = manager.approve(request.approval_id)

    assert approved.status == ApprovalStatus.APPROVED
    assert approved.resolved_at is not None
    assert approved.resolution == "user_approved"


def test_rejects_pending_request():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    rejected = manager.reject(request.approval_id)

    assert rejected.status == ApprovalStatus.REJECTED
    assert rejected.resolved_at is not None
    assert rejected.resolution == "user_rejected"


def test_approved_request_can_enter_execution():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.approve(request.approval_id)

    executing = manager.begin_execution(request.approval_id)

    assert executing.status == ApprovalStatus.EXECUTING


def test_executing_request_can_be_completed():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.approve(request.approval_id)
    manager.begin_execution(request.approval_id)

    completed = manager.complete(request.approval_id)

    assert completed.status == ApprovalStatus.EXECUTED


def test_cannot_execute_pending_request():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    with pytest.raises(ValueError):
        manager.begin_execution(request.approval_id)


def test_cannot_approve_rejected_request():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.reject(request.approval_id)

    with pytest.raises(ValueError):
        manager.approve(request.approval_id)


def test_cannot_reject_approved_request():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.approve(request.approval_id)

    with pytest.raises(ValueError):
        manager.reject(request.approval_id)


def test_cannot_modify_executed_request():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.approve(request.approval_id)
    manager.begin_execution(request.approval_id)
    manager.complete(request.approval_id)

    with pytest.raises(ValueError):
        manager.approve(request.approval_id)

    with pytest.raises(ValueError):
        manager.reject(request.approval_id)

    with pytest.raises(ValueError):
        manager.begin_execution(request.approval_id)


def test_preserves_exact_action_arguments():
    manager = ApprovalManager()

    arguments = {
        "relative_path": "backend/app/example.py",
        "content": "original content",
    }

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments=arguments,
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    assert request.arguments == arguments

    manager.approve(request.approval_id)

    approved = manager.get(request.approval_id)

    assert approved.arguments == arguments


def test_unknown_approval_id_raises_error():
    manager = ApprovalManager()

    with pytest.raises(KeyError):
        manager.get("does-not-exist")

    with pytest.raises(KeyError):
        manager.approve("does-not-exist")

    with pytest.raises(KeyError):
        manager.reject("does-not-exist")

def test_execution_uses_approved_action():
    manager = ApprovalManager()

    arguments = {
        "relative_path": "backend/app/example.py",
        "content": "approved content",
    }

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments=arguments,
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.approve(request.approval_id)

    executing = manager.begin_execution(request.approval_id)

    assert executing.tool_name == "write_file"
    assert executing.arguments == arguments
    assert executing.risk == ToolRisk.LOW_RISK_WRITE
    assert executing.session_id == "session-1"     

def test_terminal_states_cannot_be_reentered():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.approve(request.approval_id)
    manager.begin_execution(request.approval_id)
    manager.complete(request.approval_id)

    completed = manager.get(request.approval_id)

    assert completed.status == ApprovalStatus.EXECUTED

    with pytest.raises(ValueError):
        manager.complete(request.approval_id)

    assert manager.get(request.approval_id).status == ApprovalStatus.EXECUTED       

def test_approval_arguments_are_isolated_from_caller_mutation():
    manager = ApprovalManager()

    arguments = {
        "relative_path": "example.py",
        "content": "original",
    }

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments=arguments,
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    arguments["content"] = "malicious replacement"

    stored = manager.get(request.approval_id)

    assert stored.arguments["content"] == "original"    

def test_executing_request_can_be_marked_failed():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-42",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.txt",
            "content": "will fail",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.approve(request.approval_id)
    manager.begin_execution(request.approval_id)

    failed = manager.fail(
        request.approval_id,
        error="Tool execution failed",
    )

    assert failed.status == ApprovalStatus.FAILED    

def test_failed_request_preserves_error_message():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-42",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.txt",
            "content": "will fail",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.approve(request.approval_id)
    manager.begin_execution(request.approval_id)

    failed = manager.fail(
        request.approval_id,
        error="Permission denied",
    )

    assert failed.status == ApprovalStatus.FAILED
    assert failed.error == "Permission denied"    

def test_concurrent_execution_allows_only_one_transition():
    manager = ApprovalManager()

    request = manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    manager.approve(request.approval_id)

    barrier = threading.Barrier(2)
    results = []
    errors = []

    def attempt_execution():
        barrier.wait()

        try:
            manager.begin_execution(request.approval_id)
            results.append("success")
        except ValueError:
            errors.append("rejected")

    thread_a = threading.Thread(target=attempt_execution)
    thread_b = threading.Thread(target=attempt_execution)

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert results == ["success"]
    assert errors == ["rejected"]
    assert manager.get(request.approval_id).status == ApprovalStatus.EXECUTING

def test_get_for_task_returns_only_matching_approvals():
    from app.ai.approval import ApprovalManager
    from app.ai.tools import ToolRisk

    manager = ApprovalManager()

    approval_a = manager.create(
        session_id="session-a",
        task_id="task-a",
        step_id="step-a",
        tool_name="write_file",
        arguments={"relative_path": "a.py", "content": "a"},
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    approval_b = manager.create(
        session_id="session-b",
        task_id="task-b",
        step_id="step-b",
        tool_name="write_file",
        arguments={"relative_path": "b.py", "content": "b"},
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    matching = manager.get_for_task("task-a")

    assert matching == [approval_a]
    assert approval_b not in matching