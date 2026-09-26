from fastapi.testclient import TestClient

from app.main import app

def test_get_approval_returns_existing_request(monkeypatch):
    from app.api import ai
    from app.ai.tools import ToolRisk

    approval = ai.agent.approval_manager.create(
        session_id="session-1",
        task_id="task-1",
        step_id="step-1",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "hello",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/ai/approvals/{approval.approval_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["approval_id"] == approval.approval_id
    assert data["session_id"] == "session-1"
    assert data["task_id"] == "task-1"
    assert data["step_id"] == "step-1"
    assert data["tool_name"] == "write_file"
    assert data["arguments"] == {
        "relative_path": "example.py",
        "content": "hello",
    }
    assert data["risk"] == "low_risk_write"
    assert data["status"] == "pending"

def test_get_unknown_approval_returns_not_found():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ai/approvals/does-not-exist"
        )

    assert response.status_code == 404

def test_approve_existing_request():
    from app.api import ai
    from app.ai.tools import ToolRisk

    approval = ai.agent.approval_manager.create(
        session_id="session-approve",
        task_id="task-approve",
        step_id="step-approve",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "hello",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai/approvals/{approval.approval_id}/approve"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["approval_id"] == approval.approval_id
    assert data["status"] == "approved"

def test_approve_existing_request_resumes_task(monkeypatch):
    from app.api import ai
    from app.ai.tools import ToolRisk

    approval = ai.agent.approval_manager.create(
        session_id="session-resume",
        task_id="task-resume",
        step_id="step-resume",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "hello",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    ai.conversation_store.conversations["session-resume"] = [
        {
            "role": "system",
            "content": "test system prompt",
        },
        {
            "role": "user",
            "content": "Create example.py",
        },
    ]

    resume_called = False

    def fake_resume(approval_id, messages):
        nonlocal resume_called
        resume_called = True

        assert approval_id == approval.approval_id
        assert messages == ai.conversation_store.conversations["session-resume"]

        ai.agent.approval_manager.begin_execution(approval_id)
        ai.agent.approval_manager.complete(approval_id)

        return "Task resumed successfully."

    monkeypatch.setattr(
        ai.agent,
        "resume_approved_action",
        fake_resume,
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai/approvals/{approval.approval_id}/approve"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["approval_id"] == approval.approval_id
    assert data["status"] == "executed"
    assert data["response"] == "Task resumed successfully."

    assert resume_called is True

def test_approve_existing_request_returns_error_when_resume_fails(monkeypatch):
    from app.api import ai
    from app.ai.tools import ToolRisk

    approval = ai.agent.approval_manager.create(
        session_id="session-failure",
        task_id="task-failure",
        step_id="step-failure",
        tool_name="write_file",
        arguments={
            "relative_path": "example.py",
            "content": "hello",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    ai.conversation_store.conversations["session-failure"] = [
        {
            "role": "system",
            "content": "test system prompt",
        },
        {
            "role": "user",
            "content": "Create example.py",
        },
    ]

    def fake_resume(approval_id, messages):
        assert approval_id == approval.approval_id
        assert messages == ai.conversation_store.conversations["session-failure"]

        ai.agent.approval_manager.begin_execution(approval_id)
        ai.agent.approval_manager.fail(
            approval_id,
            error="Tool execution failed.",
        )

        raise RuntimeError("Tool execution failed.")

    monkeypatch.setattr(
        ai.agent,
        "resume_approved_action",
        fake_resume,
    )

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/ai/approvals/{approval.approval_id}/approve"
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Tool execution failed."

    final_approval = ai.agent.approval_manager.get(
        approval.approval_id
    )

    assert final_approval.status.value == "failed"
    assert final_approval.error == "Tool execution failed."

def test_approve_requests_for_same_session_are_serialized(monkeypatch):
    from app.api import ai
    from app.ai.tools import ToolRisk
    import threading
    import time

    session_id = "session-concurrent"

    approval_1 = ai.agent.approval_manager.create(
        session_id=session_id,
        task_id="task-concurrent-1",
        step_id="step-concurrent-1",
        tool_name="write_file",
        arguments={
            "relative_path": "one.py",
            "content": "one",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    approval_2 = ai.agent.approval_manager.create(
        session_id=session_id,
        task_id="task-concurrent-2",
        step_id="step-concurrent-2",
        tool_name="write_file",
        arguments={
            "relative_path": "two.py",
            "content": "two",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    ai.conversation_store.conversations[session_id] = [
        {
            "role": "system",
            "content": "test system prompt",
        },
        {
            "role": "user",
            "content": "Create both files.",
        },
    ]

    active_resumes = 0
    max_active_resumes = 0
    state_lock = threading.Lock()

    def fake_resume(approval_id, messages):
        nonlocal active_resumes, max_active_resumes

        with state_lock:
            active_resumes += 1
            max_active_resumes = max(
                max_active_resumes,
                active_resumes,
            )

        time.sleep(0.1)

        with state_lock:
            active_resumes -= 1

        ai.agent.approval_manager.begin_execution(approval_id)
        ai.agent.approval_manager.complete(approval_id)

        return f"Resumed {approval_id}"

    monkeypatch.setattr(
        ai.agent,
        "resume_approved_action",
        fake_resume,
    )

    responses = []

    def approve(approval_id):
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/ai/approvals/{approval_id}/approve"
            )
            responses.append(response)

    thread_1 = threading.Thread(
        target=approve,
        args=(approval_1.approval_id,),
    )
    thread_2 = threading.Thread(
        target=approve,
        args=(approval_2.approval_id,),
    )

    thread_1.start()
    thread_2.start()

    thread_1.join()
    thread_2.join()

    assert len(responses) == 2

    assert all(
        response.status_code == 200
        for response in responses
    )

    assert max_active_resumes == 1

    assert (
        ai.agent.approval_manager.get(
            approval_1.approval_id
        ).status.value
        == "executed"
    )

    assert (
        ai.agent.approval_manager.get(
            approval_2.approval_id
        ).status.value
        == "executed"
    )