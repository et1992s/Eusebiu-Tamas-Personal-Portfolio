from fastapi.testclient import TestClient

from app.main import app


def test_chat_endpoint_returns_success(monkeypatch):
    from app.api import ai

    class FakeAgent:
        class FakeOllamaClient:
            model = "test-model"

        ollama_client = FakeOllamaClient()

        def run(
            self,
            conversation,
            session_id="unknown",
            on_task_created=None,
        ):
            return "Test response"

    monkeypatch.setattr(ai, "agent", FakeAgent())
    ai.conversation_store.conversations.clear()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Hello Zebios",
                "session_id": "test-session",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["model"] == "test-model"
    assert data["session_id"] == "test-session"
    assert data["response"] == "Test response"

def test_chat_endpoint_returns_task_id_for_task_aware_agent(monkeypatch):
    from app.api import ai

    captured = {}

    class FakeAgent:
        class FakeOllamaClient:
            model = "test-model"

        ollama_client = FakeOllamaClient()

        def run(
            self,
            conversation,
            session_id="unknown",
            on_task_created=None,
        ):
            captured["callback"] = on_task_created

            if on_task_created is not None:
                on_task_created("task-from-agent")

            return "Task response"

    monkeypatch.setattr(ai, "agent", FakeAgent())
    ai.conversation_store.conversations.clear()

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Create an API endpoint",
                "session_id": "task-session",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert captured["callback"] is not None
    assert data["task_id"] == "task-from-agent"
    assert data["session_id"] == "task-session"
    assert data["response"] == "Task response"

def test_chat_endpoint_reuses_existing_session(monkeypatch):
    from app.api import ai

    captured_conversations = []

    class FakeAgent:
        class FakeOllamaClient:
            model = "test-model"

        ollama_client = FakeOllamaClient()

        def run(
            self,
            conversation,
            session_id="unknown",
            on_task_created=None,
        ):
            captured_conversations.append(list(conversation))
            return f"Response {len(captured_conversations)}"

    monkeypatch.setattr(ai, "agent", FakeAgent())
    ai.conversation_store.conversations.clear()

    with TestClient(app) as client:
        first_response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "First message",
                "session_id": "same-session",
            },
        )

        second_response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Second message",
                "session_id": "same-session",
            },
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    assert len(captured_conversations) == 2

    first_conversation = captured_conversations[0]
    second_conversation = captured_conversations[1]

    assert len(first_conversation) == 2
    assert first_conversation[0]["role"] == "system"
    assert first_conversation[1]["role"] == "user"
    assert first_conversation[1]["content"] == "First message"

    assert len(second_conversation) == 4
    assert second_conversation[0]["role"] == "system"
    assert second_conversation[1]["role"] == "user"
    assert second_conversation[1]["content"] == "First message"
    assert second_conversation[2]["role"] == "assistant"
    assert second_conversation[2]["content"] == "Response 1"
    assert second_conversation[3]["role"] == "user"
    assert second_conversation[3]["content"] == "Second message" 

def test_chat_endpoint_initializes_session_with_system_prompt_once(monkeypatch):
    from app.api import ai

    class FakeAgent:
        class FakeOllamaClient:
            model = "test-model"

        ollama_client = FakeOllamaClient()

        def run(
            self,
            conversation,
            session_id="unknown",
            on_task_created=None,
        ):
            system_messages = [
                message
                for message in conversation
                if message["role"] == "system"
            ]

            assert len(system_messages) == 1
            assert system_messages[0]["content"] == ai.ZEBIO_SYSTEM_PROMPT

            return "Test response"

    monkeypatch.setattr(ai, "agent", FakeAgent())
    ai.conversation_store.conversations.clear()

    request_a = ai.ChatRequest(
        message="First message",
        session_id="session-1",
    )

    request_b = ai.ChatRequest(
        message="Second message",
        session_id="session-1",
    )

    import asyncio

    asyncio.run(ai.chat_with_ai(request_a))
    asyncio.run(ai.chat_with_ai(request_b))

    conversation = ai.conversation_store.conversations["session-1"]

    system_messages = [
        message
        for message in conversation
        if message["role"] == "system"
    ]

    assert len(system_messages) == 1
    assert system_messages[0]["content"] == ai.ZEBIO_SYSTEM_PROMPT 

def test_chat_endpoint_preserves_conversation_message_order(monkeypatch):
    from app.api import ai

    class FakeAgent:
        class FakeOllamaClient:
            model = "test-model"

        ollama_client = FakeOllamaClient()

        def run(
            self,
            conversation,
            session_id="unknown",
            on_task_created=None,
        ):
            return f"Response to: {conversation[-1]['content']}"

    monkeypatch.setattr(ai, "agent", FakeAgent())
    ai.conversation_store.conversations.clear()

    import asyncio

    request_a = ai.ChatRequest(
        message="First message",
        session_id="session-1",
    )

    request_b = ai.ChatRequest(
        message="Second message",
        session_id="session-1",
    )

    asyncio.run(ai.chat_with_ai(request_a))
    asyncio.run(ai.chat_with_ai(request_b))

    conversation = ai.conversation_store.conversations["session-1"]

    assert conversation == [
        {
            "role": "system",
            "content": ai.ZEBIO_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": "First message",
        },
        {
            "role": "assistant",
            "content": "Response to: First message",
        },
        {
            "role": "user",
            "content": "Second message",
        },
        {
            "role": "assistant",
            "content": "Response to: Second message",
        },
    ]          

def test_chat_endpoint_persists_conversations(monkeypatch, tmp_path):
    from app.api import ai

    class FakeAgent:
        class FakeOllamaClient:
            model = "test-model"

        ollama_client = FakeOllamaClient()

        def run(
            self,
            conversation,
            session_id="unknown",
            on_task_created=None,
        ):
            return "Persistent response"

    monkeypatch.setattr(ai, "agent", FakeAgent())
    ai.conversation_store.conversations.clear()

    persistence_file = tmp_path / "chat_history.pkl"

    monkeypatch.setattr(ai, "CHAT_HISTORY_FILE", str(persistence_file))

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Remember this message",
                "session_id": "persistent-session",
            },
        )

    assert response.status_code == 200

    assert persistence_file.exists()

    import pickle

    with open(persistence_file, "rb") as f:
        saved_conversations = pickle.load(f)

    assert "persistent-session" in saved_conversations

    conversation = saved_conversations["persistent-session"]

    assert conversation[0]["role"] == "system"
    assert conversation[1]["role"] == "user"
    assert conversation[1]["content"] == "Remember this message"
    assert conversation[2]["role"] == "assistant"
    assert conversation[2]["content"] == "Persistent response"         

def test_chat_endpoint_keeps_concurrent_session_updates_isolated(monkeypatch):
    from app.api import ai

    class FakeAgent:
        class FakeOllamaClient:
            model = "test-model"

        ollama_client = FakeOllamaClient()

        def run(
            self,
            conversation,
            session_id="unknown",
            on_task_created=None,
        ):
            return f"Response to: {conversation[-1]['content']}"

    monkeypatch.setattr(ai, "agent", FakeAgent())
    ai.conversation_store.conversations.clear()

    with TestClient(app) as client:
        response_a = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Message from session A",
                "session_id": "session-a",
            },
        )

        response_b = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Message from session B",
                "session_id": "session-b",
            },
        )

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    assert response_a.json()["response"] == "Response to: Message from session A"
    assert response_b.json()["response"] == "Response to: Message from session B"

    assert "session-a" in ai.conversation_store.conversations
    assert "session-b" in ai.conversation_store.conversations

    assert all(
        message["content"] != "Message from session B"
        for message in ai.conversation_store.conversations["session-a"]
        if message["role"] == "user"
    )

    assert all(
        message["content"] != "Message from session A"
        for message in ai.conversation_store.conversations["session-b"]
        if message["role"] == "user"
    )

def test_chat_endpoint_handles_overlapping_requests(monkeypatch):
    from app.api import ai
    import threading
    import time

    execution_order = []

    class FakeAgent:
        class FakeOllamaClient:
            model = "test-model"

        ollama_client = FakeOllamaClient()

        def run(
            self,
            conversation,
            session_id="unknown",
            on_task_created=None,
        ):
            message = conversation[-1]["content"]

            execution_order.append(f"{message} - start")

            time.sleep(0.1)

            execution_order.append(f"{message} - finish")

            return f"Response to: {message}"

    monkeypatch.setattr(ai, "agent", FakeAgent())
    ai.conversation_store.conversations.clear()

    responses = {}

    def send_request(session_id, message):
        with TestClient(app) as client:
            responses[session_id] = client.post(
                "/api/v1/ai/chat",
                json={
                    "message": message,
                    "session_id": session_id,
                },
            )

    thread_a = threading.Thread(
        target=send_request,
        args=("session-a", "Message from A"),
    )

    thread_b = threading.Thread(
        target=send_request,
        args=("session-b", "Message from B"),
    )

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert execution_order[:2] in [
        [
            "Message from A - start",
            "Message from B - start",
        ],
        [
            "Message from B - start",
            "Message from A - start",
        ],
    ]

    assert set(execution_order[2:]) == {
        "Message from A - finish",
        "Message from B - finish",
    }

    assert responses["session-a"].status_code == 200
    assert responses["session-b"].status_code == 200

    assert responses["session-a"].json()["response"] == "Response to: Message from A"
    assert responses["session-b"].json()["response"] == "Response to: Message from B"

    session_a_messages = ai.conversation_store.conversations["session-a"]
    session_b_messages = ai.conversation_store.conversations["session-b"]

    assert any(
        message["content"] == "Message from A"
        for message in session_a_messages
        if message["role"] == "user"
    )

    assert any(
        message["content"] == "Message from B"
        for message in session_b_messages
        if message["role"] == "user"
    )

def test_chat_endpoint_handles_overlapping_requests_same_session(monkeypatch):
    from app.api import ai
    import threading
    import time

    execution_order = []
    
    class FakeAgent:
        class FakeOllamaClient:
            model = "test-model"

        ollama_client = FakeOllamaClient()

        def run(
            self,
            conversation,
            session_id="unknown",
            on_task_created=None,
        ):
            message = conversation[-1]["content"]

            execution_order.append(f"{message} - start")

            time.sleep(0.1)

            execution_order.append(f"{message} - finish")

            return f"Response to: {message}"

    monkeypatch.setattr(ai, "agent", FakeAgent())
    ai.conversation_store.conversations.clear()

    responses = {}

    def send_request(request_id, message):
        with TestClient(app) as client:
            responses[request_id] = client.post(
                "/api/v1/ai/chat",
                json={
                    "message": message,
                    "session_id": "shared-session",
                },
            )

    thread_a = threading.Thread(
        target=send_request,
        args=("a", "Message from A"),
    )

    thread_b = threading.Thread(
        target=send_request,
        args=("b", "Message from B"),
    )

    thread_a.start()
    thread_b.start()

    thread_a.join()
    thread_b.join()

    assert execution_order in [
        [
            "Message from A - start",
            "Message from A - finish",
            "Message from B - start",
            "Message from B - finish",
        ],
        [
            "Message from B - start",
            "Message from B - finish",
            "Message from A - start",
            "Message from A - finish",
        ],
    ]

    assert responses["a"].status_code == 200
    assert responses["b"].status_code == 200

    conversation = ai.conversation_store.conversations["shared-session"]

    user_messages = [
        message["content"]
        for message in conversation
        if message["role"] == "user"
    ]

    assistant_messages = [
        message["content"]
        for message in conversation
        if message["role"] == "assistant"
    ]

    assert sorted(user_messages) == [
        "Message from A",
        "Message from B",
    ]

    assert len(assistant_messages) == 2

def test_task_state_endpoint_returns_task_and_steps(monkeypatch):
    from app.api import ai
    from app.ai.task_manager import TaskStatus, TaskStepStatus
    from app.ai.tools import ToolRisk

    task = ai.agent.task_manager.create(
        session_id="state-session",
        goal="Create an API endpoint",
    )
    ai.agent.task_manager.start(task.task_id)
    ai.agent.task_manager.set_current_step(
        task.task_id,
        "Designing endpoint",
    )

    step = ai.agent.task_manager.create_step(
        task.task_id,
        "write_file",
        {
            "relative_path": "backend/app/api/example.py",
            "content": "test",
        },
    )
    ai.agent.task_manager.start_step(step.step_id)

    approval = ai.agent.approval_manager.create(
        session_id="state-session",
        task_id=task.task_id,
        step_id=step.step_id,
        tool_name="write_file",
        arguments={
            "relative_path": "backend/app/api/example.py",
            "content": "test",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/ai/tasks/{task.task_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["task_id"] == task.task_id
    assert data["session_id"] == "state-session"
    assert data["goal"] == "Create an API endpoint"
    assert data["status"] == TaskStatus.RUNNING.value
    assert data["current_step"] == "Designing endpoint"

    assert len(data["steps"]) == 1

    returned_step = data["steps"][0]

    assert returned_step["step_id"] == step.step_id
    assert returned_step["task_id"] == task.task_id
    assert returned_step["tool_name"] == "write_file"
    assert returned_step["status"] == TaskStepStatus.RUNNING.value

    assert returned_step["approval_id"] == approval.approval_id
    assert returned_step["approval_status"] == "pending"
    assert returned_step["risk"] == ToolRisk.LOW_RISK_WRITE.value

def test_task_state_endpoint_returns_running_task_without_steps():
    from app.api import ai

    task = ai.agent.task_manager.create(
        session_id="empty-task-session",
        goal="Inspect the project",
    )
    ai.agent.task_manager.start(task.task_id)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/ai/tasks/{task.task_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["task_id"] == task.task_id
    assert data["session_id"] == "empty-task-session"
    assert data["goal"] == "Inspect the project"
    assert data["status"] == "running"
    assert data["current_step"] is None
    assert data["observations"] == []
    assert data["errors"] == []
    assert data["steps"] == []

def test_task_state_endpoint_reflects_state_changes_for_same_task():
    from app.api import ai
    from app.ai.tools import ToolRisk

    task = ai.agent.task_manager.create(
        session_id="observation-session",
        goal="Modify a backend file",
    )
    ai.agent.task_manager.start(task.task_id)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/ai/tasks/{task.task_id}"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["steps"] == []

    step = ai.agent.task_manager.create_step(
        task.task_id,
        "write_file",
        {
            "relative_path": "backend/app/example.py",
            "content": "updated",
        },
    )
    ai.agent.task_manager.start_step(step.step_id)

    approval = ai.agent.approval_manager.create(
        session_id="observation-session",
        task_id=task.task_id,
        step_id=step.step_id,
        tool_name="write_file",
        arguments={
            "relative_path": "backend/app/example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/ai/tasks/{task.task_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "running"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["status"] == "running"
    assert data["steps"][0]["approval_id"] == approval.approval_id
    assert data["steps"][0]["approval_status"] == "pending"

    ai.agent.approval_manager.approve(approval.approval_id)
    ai.agent.approval_manager.begin_execution(approval.approval_id)
    ai.agent.approval_manager.complete(approval.approval_id)

    ai.agent.task_manager.complete_task_step(step.step_id)
    ai.agent.task_manager.complete(task.task_id)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/ai/tasks/{task.task_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "completed"
    assert data["steps"][0]["status"] == "completed"
    assert data["steps"][0]["approval_status"] == "executed"

def test_task_state_endpoint_returns_404_for_unknown_task():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/ai/tasks/task-does-not-exist"
        )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Task not found: task-does-not-exist"
    }

def test_task_state_endpoint_reflects_approval_lifecycle(monkeypatch):
    from app.api import ai
    from app.ai.tools import ToolRisk

    task = ai.agent.task_manager.create(
        session_id="approval-state-session",
        goal="Modify a backend file",
    )
    ai.agent.task_manager.start(task.task_id)

    step = ai.agent.task_manager.create_step(
        task.task_id,
        "write_file",
        {
            "relative_path": "backend/app/example.py",
            "content": "updated",
        },
    )
    ai.agent.task_manager.start_step(step.step_id)

    approval = ai.agent.approval_manager.create(
        session_id="approval-state-session",
        task_id=task.task_id,
        step_id=step.step_id,
        tool_name="write_file",
        arguments={
            "relative_path": "backend/app/example.py",
            "content": "updated",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/ai/tasks/{task.task_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "running"
    assert len(data["steps"]) == 1

    returned_step = data["steps"][0]

    assert returned_step["step_id"] == step.step_id
    assert returned_step["status"] == "running"
    assert returned_step["approval_id"] == approval.approval_id
    assert returned_step["approval_status"] == "pending"
    assert returned_step["risk"] == ToolRisk.LOW_RISK_WRITE.value

    # The approval itself must remain authoritative.
    stored_approval = ai.agent.approval_manager.get(
        approval.approval_id
    )

    assert stored_approval.status.value == "pending"

def test_task_state_endpoint_reflects_completed_step_and_approval():
    from app.api import ai
    from app.ai.tools import ToolRisk

    task = ai.agent.task_manager.create(
        session_id="completed-state-session",
        goal="Create a backend file",
    )
    ai.agent.task_manager.start(task.task_id)

    step = ai.agent.task_manager.create_step(
        task.task_id,
        "write_file",
        {
            "relative_path": "backend/app/example.py",
            "content": "completed",
        },
    )
    ai.agent.task_manager.start_step(step.step_id)

    approval = ai.agent.approval_manager.create(
        session_id="completed-state-session",
        task_id=task.task_id,
        step_id=step.step_id,
        tool_name="write_file",
        arguments={
            "relative_path": "backend/app/example.py",
            "content": "completed",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    ai.agent.approval_manager.approve(approval.approval_id)
    ai.agent.approval_manager.begin_execution(approval.approval_id)
    ai.agent.approval_manager.complete(approval.approval_id)

    ai.agent.task_manager.complete_task_step(step.step_id)
    ai.agent.task_manager.complete(task.task_id)

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/ai/tasks/{task.task_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "completed"
    assert data["completed_at"] is not None

    assert len(data["steps"]) == 1

    returned_step = data["steps"][0]

    assert returned_step["status"] == "completed"
    assert returned_step["completed_at"] is not None
    assert returned_step["approval_id"] == approval.approval_id
    assert returned_step["approval_status"] == "executed"
    assert returned_step["risk"] == ToolRisk.LOW_RISK_WRITE.value

def test_task_state_endpoint_reflects_failed_step_and_task():
    from app.api import ai
    from app.ai.tools import ToolRisk

    task = ai.agent.task_manager.create(
        session_id="failed-state-session",
        goal="Modify a backend file",
    )
    ai.agent.task_manager.start(task.task_id)

    step = ai.agent.task_manager.create_step(
        task.task_id,
        "write_file",
        {
            "relative_path": "backend/app/example.py",
            "content": "failed",
        },
    )
    ai.agent.task_manager.start_step(step.step_id)

    approval = ai.agent.approval_manager.create(
        session_id="failed-state-session",
        task_id=task.task_id,
        step_id=step.step_id,
        tool_name="write_file",
        arguments={
            "relative_path": "backend/app/example.py",
            "content": "failed",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    ai.agent.approval_manager.approve(approval.approval_id)
    ai.agent.approval_manager.begin_execution(approval.approval_id)
    ai.agent.approval_manager.fail(
        approval.approval_id,
        "File write failed",
    )

    ai.agent.task_manager.fail_task_step(
        step.step_id,
        "File write failed",
    )
    ai.agent.task_manager.fail(
        task.task_id,
        "File write failed",
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/ai/tasks/{task.task_id}"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "failed"
    assert data["completed_at"] is None
    assert data["errors"] == ["File write failed"]

    assert len(data["steps"]) == 1

    returned_step = data["steps"][0]

    assert returned_step["status"] == "failed"
    assert returned_step["completed_at"] is None
    assert returned_step["error"] == "File write failed"

    assert returned_step["approval_id"] == approval.approval_id
    assert returned_step["approval_status"] == "failed"
    assert returned_step["risk"] == ToolRisk.LOW_RISK_WRITE.value
