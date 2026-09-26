from types import SimpleNamespace
from typing import Any, cast
import pytest

from app.ai.approval import ApprovalStatus
from app.ai.task_manager import TaskManager, TaskStatus, TaskStepStatus
from app.ai.tools import ToolRisk
from app.ai.agent import ZebioAgent
from app.ai.context import AgentContext
from app.ai.schemas import FinalDecision

def test_is_simple_conversation_returns_false_for_file_creation():
    agent = ZebioAgent()

    messages = [
        {
            "role": "user",
            "content": (
                "Create a new file backend/app/ai/"
                "zebio_test_file.py containing a simple Python function."
            ),
        }
    ]

    assert agent._is_simple_conversation(messages) is False


def test_is_simple_conversation_returns_false_for_existing_file_modification():
    agent = ZebioAgent()

    messages = [
        {
            "role": "user",
            "content": (
                "Modify an existing project file to add a comment "
                "explaining the TaskManager class."
            ),
        }
    ]

    assert agent._is_simple_conversation(messages) is False


def test_is_simple_conversation_returns_true_for_normal_conversation():
    agent = ZebioAgent()

    messages = [
        {
            "role": "user",
            "content": "What is the difference between Python and Java?",
        }
    ]

    assert agent._is_simple_conversation(messages) is True


def test_run_executes_native_tool_call_and_returns_final_response(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    test_file = tmp_path / "example.txt"
    test_file.write_text("hello zebios", encoding="utf-8")

    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="read_file",
            arguments={"relative_path": "example.txt"},
        ),
    )

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[tool_call],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="The file contains: hello zebios",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
    ])

    captured_messages = []

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        captured_messages.clear()
        captured_messages.extend(messages)
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Read the file example.txt",
        }
    ]

    result = agent.run(messages)

    assert result == "The file contains: hello zebios"

    assert any(
        message.get("role") == "tool"
        and "hello zebios" in message.get("content", "")
        for message in captured_messages
    )

def test_run_completes_task_lifecycle(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    test_file = tmp_path / "example.txt"
    test_file.write_text("hello zebios", encoding="utf-8")

    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="read_file",
            arguments={"relative_path": "example.txt"},
        ),
    )

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[tool_call],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="The file contains: hello zebios",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
    ])

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Read the file example.txt",
        }
    ]

    captured = {}

    def on_task_created(task_id: str) -> None:
        captured["task_id"] = task_id

    result = agent.run(
        messages,
        session_id="session-lifecycle",
        on_task_created=on_task_created,
    )

    assert result == "The file contains: hello zebios"

    assert len(agent.task_manager.tasks) == 1

    task = next(iter(agent.task_manager.tasks.values()))
    
    assert captured["task_id"] == task.task_id

    assert task.session_id == "session-lifecycle"
    assert task.goal == "Read the file example.txt"
    assert task.status.value == "completed"
    assert task.current_step == "Agent step 2"
    steps = list(agent.task_manager.steps.values())

    assert len(steps) == 1

    task_step = steps[0]

    assert task_step.task_id == task.task_id
    assert task_step.tool_name == "read_file"
    assert task_step.arguments == {
        "relative_path": "example.txt"
    }
    assert task_step.status == TaskStepStatus.COMPLETED
    assert task_step.completed_at is not None
    assert task.completed_at is not None
    assert task.created_at.tzinfo is not None
    assert task.updated_at.tzinfo is not None

def test_run_fails_task_when_llm_returns_invalid_response():
    agent = ZebioAgent()

    invalid_response = SimpleNamespace(
        message=None,
    )

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return invalid_response

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Inspect the project structure.",
        }
    ]

    result = agent.run(
        messages,
        session_id="invalid-response",
    )

    assert result == "Zebio received an invalid response from the local LLM."

    assert len(agent.task_manager.tasks) == 1

    task = next(iter(agent.task_manager.tasks.values()))

    assert task.session_id == "invalid-response"
    assert task.goal == "Inspect the project structure."
    assert task.status.value == "failed"
    assert task.errors == [
        "InvalidResponse: The local LLM returned no message."
    ]    

def test_run_marks_task_failed_when_llm_communication_fails():
    agent = ZebioAgent()

    def failing_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        raise RuntimeError("Ollama unavailable")

    agent.ollama_client.chat_with_tools = failing_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Inspect the project.",
        }
    ]

    result = agent.run(
        messages,
        session_id="session-failure",
    )

    assert result == (
        "Zebio could not communicate with the "
        "local LLM: RuntimeError: Ollama unavailable"
    )

    assert len(agent.task_manager.tasks) == 1

    task = next(iter(agent.task_manager.tasks.values()))

    assert task.session_id == "session-failure"
    assert task.goal == "Inspect the project."
    assert task.status.value == "failed"
    assert task.errors == ["RuntimeError: Ollama unavailable"]
    assert task.completed_at is None

def test_run_marks_task_failed_when_max_steps_reached():
    agent = ZebioAgent()

    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="read_file",
            arguments={"relative_path": "example.txt"},
        ),
    )

    response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[tool_call],
        )
    )

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return response

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Inspect the project files and investigate the implementation.",
        }
    ]

    result = agent.run(
        messages,
        max_steps=1,
        session_id="session-max-steps",
    )

    assert result == (
        "Zebio stopped because it reached the maximum "
        "number of engineering steps (1).\n\n"
        "The task may be incomplete."
    )

    assert len(agent.task_manager.tasks) == 1

    task = next(iter(agent.task_manager.tasks.values()))

    assert task.session_id == "session-max-steps"
    assert task.status.value == "failed"
    assert task.errors == [
        "Maximum engineering steps reached (1)."
    ]
    assert task.completed_at is None

def test_run_rejects_invalid_tool_arguments(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="read_file",
            arguments={},
        ),
    )

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[tool_call],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="I cannot read the file because the required argument is missing.",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
    ])

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Read the file example.txt",
        }
    ]

    result = agent.run(messages)

    assert result == (
        "I cannot read the file because the required argument is missing."
    )

    assert not any(
        message.get("role") == "tool"
        and "hello zebios" in message.get("content", "")
        for message in messages
    )

def test_run_rejects_unknown_tool(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="delete_everything",
            arguments={},
        ),
    )

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[tool_call],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="I cannot execute that tool because it is not available.",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
    ])

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Run the command to delete everything.",
        }
    ]

    result = agent.run(messages)

    assert result == (
        "I cannot execute that tool because it is not available."
    )    

def test_run_marks_task_failed_after_three_invalid_tool_requests(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    responses = iter([
        SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="call_1",
                        function=SimpleNamespace(
                            name="delete_everything",
                            arguments={},
                        ),
                    )
                ],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="call_2",
                        function=SimpleNamespace(
                            name="delete_everything",
                            arguments={},
                        ),
                    )
                ],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="call_3",
                        function=SimpleNamespace(
                            name="delete_everything",
                            arguments={},
                        ),
                    )
                ],
            )
        ),
    ])

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Inspect the project and investigate the requested operation.",
        }
    ]

    result = agent.run(messages)

    assert result == (
        "Zebio stopped after receiving multiple "
        "invalid tool requests."
    )

    tasks = list(agent.task_manager.tasks.values())

    assert len(tasks) == 1

    task = tasks[0]

    assert task.status.value == "failed"
    assert task.errors == [
        "Multiple consecutive invalid tool requests."
    ]
    assert task.completed_at is None

def test_run_completes_task_step_for_legacy_tool_call(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    test_file = tmp_path / "example.txt"
    test_file.write_text("hello zebios", encoding="utf-8")

    responses = iter([
        SimpleNamespace(
            message=SimpleNamespace(
                content=(
                    '{"name": "read_file", '
                    '"arguments": {"relative_path": "example.txt"}}'
                ),
                tool_calls=[],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="The file contains: hello zebios",
                tool_calls=[],
            )
        ),
    ])

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Inspect the project files and investigate the contents of example.txt.",
        }
    ]

    result = agent.run(messages)

    assert result == "The file contains: hello zebios"

    tasks = list(agent.task_manager.tasks.values())

    assert len(tasks) == 1

    task = tasks[0]

    assert task.status.value == "completed"

    task_steps = [
        step
        for step in agent.task_manager.steps.values()
        if step.task_id == task.task_id
    ]

    assert len(task_steps) == 1

    step = task_steps[0]

    assert step.tool_name == "read_file"
    assert step.arguments == {
        "relative_path": "example.txt",
    }
    assert step.status == TaskStepStatus.COMPLETED
    assert step.completed_at is not None
    assert step.error is None
    assert task.current_step == "Agent step 2"
    assert task.completed_at is not None

def test_run_handles_tool_execution_error(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="read_file",
            arguments={"relative_path": "missing.txt"},
        ),
    )

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[tool_call],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="The file could not be found.",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
    ])

    captured_messages = []

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        captured_messages.clear()
        captured_messages.extend(messages)
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Read the file missing.txt",
        }
    ]

    result = agent.run(messages)

    assert result == "The file could not be found."

    assert any(
        message.get("role") == "tool"
        and "FileNotFoundError" in message.get("content", "")
        for message in captured_messages
    )    

def test_run_executes_multiple_sequential_tool_calls(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    test_file = tmp_path / "example.txt"
    test_file.write_text("hello zebios", encoding="utf-8")

    first_tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="list_directory",
            arguments={"relative_path": "."},
        ),
    )

    second_tool_call = SimpleNamespace(
        id="call_2",
        function=SimpleNamespace(
            name="read_file",
            arguments={"relative_path": "example.txt"},
        ),
    )

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[first_tool_call],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[second_tool_call],
        )
    )

    final_response = SimpleNamespace(
        message=SimpleNamespace(
            content="The directory contains example.txt, which contains hello zebios.",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
        final_response,
    ])

    captured_messages = []

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        captured_messages.clear()
        captured_messages.extend(messages)
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Inspect the project and tell me what example.txt contains.",
        }
    ]

    result = agent.run(messages)

    assert result == (
        "The directory contains example.txt, which contains hello zebios."
    )

    tool_messages = [
        message
        for message in captured_messages
        if message.get("role") == "tool"
    ]

    assert len(tool_messages) == 2

    assert "example.txt" in tool_messages[0]["content"]
    assert "hello zebios" in tool_messages[1]["content"]    

def test_run_detects_repeated_identical_tool_call(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    test_file = tmp_path / "example.txt"
    test_file.write_text("hello zebios", encoding="utf-8")

    first_tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="read_file",
            arguments={"relative_path": "example.txt"},
        ),
    )

    repeated_tool_call = SimpleNamespace(
        id="call_2",
        function=SimpleNamespace(
            name="read_file",
            arguments={"relative_path": "example.txt"},
        ),
    )

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[first_tool_call],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[repeated_tool_call],
        )
    )

    final_response = SimpleNamespace(
        message=SimpleNamespace(
            content="The repeated tool call was detected.",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
        final_response,
    ])

    captured_messages = []

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        captured_messages.clear()
        captured_messages.extend(messages)
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Read the file example.txt.",
        }
    ]

    result = agent.run(messages)

    assert result == "The repeated tool call was detected."

    tool_messages = [
        message
        for message in captured_messages
        if message.get("role") == "tool"
    ]

    assert len(tool_messages) == 2

    assert "hello zebios" in tool_messages[0]["content"]
    assert "LoopDetected" in tool_messages[1]["content"]
    assert "not executed" in tool_messages[1]["content"]    

def test_run_stops_after_three_consecutive_tool_execution_errors(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    responses = iter([
        SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="call_1",
                        function=SimpleNamespace(
                            name="read_file",
                            arguments={"relative_path": "missing1.txt"},
                        ),
                    )
                ],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="call_2",
                        function=SimpleNamespace(
                            name="read_file",
                            arguments={"relative_path": "missing2.txt"},
                        ),
                    )
                ],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="call_3",
                        function=SimpleNamespace(
                            name="read_file",
                            arguments={"relative_path": "missing3.txt"},
                        ),
                    )
                ],
            )
        ),
    ])

    captured_messages = []

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        captured_messages.clear()
        captured_messages.extend(messages)
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    messages = [
        {
            "role": "user",
            "content": "Inspect the project and read the missing files.",
        }
    ]

    result = agent.run(messages)

    assert result == (
        "Zebio stopped after multiple consecutive "
        "tool execution failures.\n\n"
        "The task requires investigation before continuing."
    )

    tasks = list(agent.task_manager.tasks.values())

    assert len(tasks) == 1

    task = tasks[0]

    assert task.status.value == "failed"
    assert task.errors == [
        "Multiple consecutive tool execution failures."
    ]
    assert task.completed_at is None

    tool_messages = [
        message
        for message in captured_messages
        if message.get("role") == "tool"
    ]

    assert len(tool_messages) == 2

    assert "FileNotFoundError" in tool_messages[0]["content"]
    assert "FileNotFoundError" in tool_messages[1]["content"]  

def test_run_does_not_execute_tool_when_policy_requires_approval(tmp_path):
    agent = ZebioAgent()
    agent.tool_registry.tools.project_context.project_root = tmp_path

    test_file = tmp_path / "example.txt"
    test_file.write_text("secret content", encoding="utf-8")

    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="write_file",
            arguments={
                "relative_path": "example.txt",
                "content": "modified content",
            },
        ),
    )

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[tool_call],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="The file change requires user approval.",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
    ])

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    original_execute = agent.tool_registry.execute

    def fail_if_executed(tool_name, arguments):
        raise AssertionError("Tool was executed without approval.")

    agent.tool_registry.execute = fail_if_executed


    messages = [
        {
            "role": "user",
            "content": "Modify this file: example.txt.",
        }
    ]

    result = agent.run(messages)

    assert "Approval required before executing 'write_file'." in result

    assert test_file.read_text(encoding="utf-8") == "secret content"

    assert not any(
        message.get("role") == "tool"
        for message in messages
    )

    agent.tool_registry.execute = original_execute     

def test_run_executes_tool_when_policy_allows():
    agent = ZebioAgent()

    tool_call = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(
            name="read_file",
            arguments={"relative_path": "example.txt"},
        ),
    )

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[tool_call],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="The file contains test content.",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
    ])

    def fake_chat_with_tools(
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools

    executed = []

    def fake_execute(tool_name, arguments):
        executed.append((tool_name, arguments))
        return "test content"

    agent.tool_registry.execute = fake_execute

    messages = [
        {
            "role": "user",
            "content": "Read this file: example.txt.",
        }
    ]

    result = agent.run(messages)

    assert result == "The file contains test content."

    assert executed == [
        (
            "read_file",
            {"relative_path": "example.txt"},
        )
    ]

def test_execute_tool_creates_approval_request_when_policy_requires_approval():
    agent = ZebioAgent()

    arguments = {
        "relative_path": "example.txt",
        "content": "approved content",
    }

    result = agent._execute_tool(
        "write_file",
        arguments,
    )

    assert result["error"] == "ApprovalRequired"
    assert result["approval_id"]
    assert result["tool_name"] == "write_file"
    assert result["arguments"] == arguments
    assert result["risk"] == ToolRisk.LOW_RISK_WRITE

def test_execute_tool_uses_session_id_for_approval_request():
    agent = ZebioAgent()

    arguments = {
        "relative_path": "example.txt",
        "content": "approved content",
    }

    result = agent._execute_tool(
        "write_file",
        arguments,
        session_id="session-42",
    )

    assert result["error"] == "ApprovalRequired"

    approval = agent.approval_manager.get(
        result["approval_id"]
    )

    assert approval.session_id == "session-42"

def test_execute_tool_creates_pending_approval_request():
    agent = ZebioAgent()

    arguments = {
        "relative_path": "example.txt",
        "content": "approved content",
    }

    result = agent._execute_tool(
        "write_file",
        arguments,
        session_id="session-42",
    )

    approval = agent.approval_manager.get(
        result["approval_id"]
    )

    assert approval.status == ApprovalStatus.PENDING
    assert approval.approval_id == result["approval_id"]
    assert approval.tool_name == "write_file"
    assert approval.arguments == arguments
    assert approval.session_id == "session-42"
    assert approval.risk == ToolRisk.LOW_RISK_WRITE    

def test_agent_can_approve_pending_request():
    agent = ZebioAgent()

    arguments = {
        "relative_path": "example.txt",
        "content": "approved content",
    }

    result = agent._execute_tool(
        "write_file",
        arguments,
        session_id="session-42",
    )

    approval_id = result["approval_id"]

    approved = agent.approve_action(approval_id)

    assert approved.status == ApprovalStatus.APPROVED
    assert approved.approval_id == approval_id
    assert approved.resolution == "user_approved"
    assert approved.resolved_at is not None    

def test_agent_can_reject_pending_request():
    agent = ZebioAgent()

    arguments = {
        "relative_path": "example.txt",
        "content": "rejected content",
    }

    result = agent._execute_tool(
        "write_file",
        arguments,
        session_id="session-42",
    )

    approval_id = result["approval_id"]

    rejected = agent.reject_action(approval_id)

    assert rejected.status == ApprovalStatus.REJECTED
    assert rejected.approval_id == approval_id
    assert rejected.resolution == "user_rejected"
    assert rejected.resolved_at is not None    

def test_agent_can_begin_approved_action():
    agent = ZebioAgent()

    arguments = {
        "relative_path": "example.txt",
        "content": "approved content",
    }

    result = agent._execute_tool(
        "write_file",
        arguments,
        session_id="session-42",
    )

    approval_id = result["approval_id"]

    agent.approve_action(approval_id)

    executing = agent.begin_approved_action(approval_id)

    assert executing.status == ApprovalStatus.EXECUTING
    assert executing.approval_id == approval_id      

def test_agent_executes_exact_approved_action(monkeypatch):
    agent = ZebioAgent()

    arguments = {
        "relative_path": "example.txt",
        "content": "approved content",
    }

    result = agent._execute_tool(
        "write_file",
        arguments,
        session_id="session-42",
    )

    approval_id = result["approval_id"]

    agent.approve_action(approval_id)

    captured = {}

    def fake_execute(tool_name, tool_arguments):
        captured["tool_name"] = tool_name
        captured["arguments"] = tool_arguments
        return {"status": "executed"}

    monkeypatch.setattr(
        agent.tool_registry,
        "execute",
        fake_execute,
    )

    execution_result = agent.execute_approved_action(approval_id)

    assert execution_result == {"status": "executed"}
    assert captured["tool_name"] == "write_file"
    assert captured["arguments"] == arguments     

def test_agent_executes_exact_approved_command(monkeypatch):
    agent = ZebioAgent()

    arguments = {
        "command": "git add .",
    }

    result = agent._execute_tool(
        "run_command",
        arguments,
        session_id="session-42",
    )

    assert result["error"] == "ApprovalRequired"

    approval_id = result["approval_id"]

    agent.approve_action(approval_id)

    captured = {}

    def fake_execute(tool_name, tool_arguments):
        captured["tool_name"] = tool_name
        captured["arguments"] = tool_arguments
        return {"status": "executed"}

    monkeypatch.setattr(
        agent.tool_registry,
        "execute",
        fake_execute,
    )

    execution_result = agent.execute_approved_action(approval_id)

    assert execution_result == {"status": "executed"}
    assert captured["tool_name"] == "run_command"
    assert captured["arguments"] == arguments    

def test_agent_cannot_execute_unapproved_action(monkeypatch):
    agent = ZebioAgent()

    arguments = {
        "relative_path": "example.txt",
        "content": "should not execute",
    }

    result = agent._execute_tool(
        "write_file",
        arguments,
        session_id="session-42",
    )

    approval_id = result["approval_id"]

    captured = {}

    def fake_execute(tool_name, tool_arguments):
        captured["called"] = True
        return {"status": "executed"}

    monkeypatch.setattr(
        agent.tool_registry,
        "execute",
        fake_execute,
    )

    with pytest.raises(ValueError, match="Cannot begin execution"):
        agent.execute_approved_action(approval_id)

    assert "called" not in captured

    approval = agent.approval_manager.get(approval_id)
    assert approval.status == ApprovalStatus.PENDING    

def test_agent_marks_approved_action_failed_when_execution_raises(monkeypatch):
    agent = ZebioAgent()

    arguments = {
        "relative_path": "example.txt",
        "content": "will fail",
    }

    task = agent.task_manager.create(
        session_id="session-42",
        goal="Write a file.",
    )
    agent.task_manager.start(task.task_id)

    task_step = agent.task_manager.create_step(
        task_id=task.task_id,
        tool_name="write_file",
        arguments=arguments,
    )
    agent.task_manager.start_step(task_step.step_id)

    result = agent._execute_tool(
        "write_file",
        arguments,
        session_id="session-42",
        task_id=task.task_id,
        step_id=task_step.step_id,
    )

    approval_id = result["approval_id"]

    agent.approve_action(approval_id)

    def failing_execute(tool_name, tool_arguments):
        raise RuntimeError("Tool execution failed")

    monkeypatch.setattr(
        agent.tool_registry,
        "execute",
        failing_execute,
    )

    with pytest.raises(RuntimeError, match="Tool execution failed"):
        agent.execute_approved_action(approval_id)

    approval = agent.approval_manager.get(approval_id)

    assert approval.status == ApprovalStatus.FAILED
    assert approval.error == "Tool execution failed"

    task_step = agent.task_manager.get_step(task_step.step_id)

    assert task_step.status == TaskStepStatus.FAILED
    assert task_step.error == "Tool execution failed"

def test_execute_tool_allows_classified_read_only_command(monkeypatch):
    agent = ZebioAgent()

    executed = []

    monkeypatch.setattr(
        agent.tool_registry,
        "execute",
        lambda tool_name, arguments: executed.append(
            (tool_name, arguments)
        ) or {"status": "executed"},
    )

    result = agent._execute_tool(
        "run_command",
        {"command": "git status"},
        session_id="session-1",
    )

    assert result == {"status": "executed"}
    assert executed == [
        ("run_command", {"command": "git status"})
    ]


def test_execute_tool_denies_classified_destructive_command():
    agent = ZebioAgent()

    result = agent._execute_tool(
        "run_command",
        {"command": "git reset --hard"},
        session_id="session-1",
    )

    assert result["error"] == "PolicyDenied"
    assert result["message"] == (
        "Tool execution denied by policy: run_command"
    )    

def test_execute_tool_requires_approval_for_low_risk_command():
    agent = ZebioAgent()

    result = agent._execute_tool(
        "run_command",
        {"command": "git add ."},
        session_id="session-1",
    )

    assert result["error"] == "ApprovalRequired"
    assert result["tool_name"] == "run_command"
    assert result["arguments"] == {"command": "git add ."}
    assert result["risk"] == ToolRisk.LOW_RISK_WRITE


def test_execute_tool_requires_approval_for_system_change_command():
    agent = ZebioAgent()

    result = agent._execute_tool(
        "run_command",
        {"command": "pip install pandas"},
        session_id="session-1",
    )

    assert result["error"] == "ApprovalRequired"
    assert result["tool_name"] == "run_command"
    assert result["arguments"] == {"command": "pip install pandas"}
    assert result["risk"] == ToolRisk.SYSTEM_CHANGE    

def test_is_simple_conversation_returns_false_for_follow_up_engineering_request():
    agent = ZebioAgent()

    messages = [
        {
            "role": "assistant",
            "content": (
                "Here are some things I can do:\n"
                "1. Inspect and understand the project\n"
                "2. Create or modify files\n"
                "3. Run commands\n"
                "4. Debugging"
            ),
        },
        {
            "role": "user",
            "content": "Please, do 1",
        },
    ]

    assert agent._is_simple_conversation(messages) is False

def test_run_stops_when_tool_requires_approval():
    agent = ZebioAgent()

    tool_call = SimpleNamespace(
        id="call_approval_1",
        function=SimpleNamespace(
            name="create_file",
            arguments={
                "relative_path": "backend/app/ai/zebio_test_file.py",
                "content": 'def hello_zebio():\n    return "Hello from Zebio"',
            },
        ),
    )

    response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[tool_call],
        )
    )

    chat_call_count = 0

    def fake_chat_with_tools(messages, tools):
        nonlocal chat_call_count
        chat_call_count += 1
        return response

    agent.ollama_client.chat_with_tools = fake_chat_with_tools # type: ignore

    messages = [
        {
            "role": "user",
            "content": "Create a new Python file called zebio_test_file.py.",
        }
    ]

    result = agent.run(messages, session_id="approval-test")

    assert "approval" in result.lower()
    assert chat_call_count == 1

    tasks = agent.task_manager.tasks
    assert len(tasks) == 1

    task = next(iter(tasks.values()))

    task_steps = [
        step
        for step in agent.task_manager.steps.values()
        if step.task_id == task.task_id
    ]

    assert len(task_steps) == 1

    task_step = task_steps[0]

    approvals = list(agent.approval_manager.requests.values())

    assert len(approvals) == 1

    approval = approvals[0]

    assert approval.task_id == task.task_id
    assert approval.step_id == task_step.step_id
    assert approval.step_id != "unknown"

def test_run_stops_when_legacy_tool_requires_approval():
    agent = ZebioAgent()

    first_response = SimpleNamespace(
        message=SimpleNamespace(
            content=(
                '{"name":"create_file","arguments":'
                '{"relative_path":"backend/app/ai/zebio_legacy_test.py",'
                '"content":"def hello_zebio():\\n    return \\"Hello from Zebio\\""}}'
            ),
            tool_calls=[],
        )
    )

    second_response = SimpleNamespace(
        message=SimpleNamespace(
            content="This should never be requested.",
            tool_calls=[],
        )
    )

    responses = iter([
        first_response,
        second_response,
    ])

    chat_call_count = 0

    def fake_chat_with_tools(messages, tools):
        nonlocal chat_call_count
        chat_call_count += 1
        return next(responses)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools # type: ignore

    messages = [
        {
            "role": "user",
            "content": "Create a new Python file using the legacy tool format.",
        }
    ]

    result = agent.run(messages, session_id="legacy-approval-test")

    assert "Approval required" in result
    assert chat_call_count == 1    

    tasks = agent.task_manager.tasks
    assert len(tasks) == 1

    task = next(iter(tasks.values()))

    task_steps = [
        step
        for step in agent.task_manager.steps.values()
        if step.task_id == task.task_id
    ]

    assert len(task_steps) == 1

    task_step = task_steps[0]

    approvals = list(agent.approval_manager.requests.values())

    assert len(approvals) == 1

    approval = approvals[0]

    assert approval.task_id == task.task_id
    assert approval.step_id == task_step.step_id
    assert approval.step_id != "unknown"

def test_approved_action_execution_is_not_confused_with_task_step_completion():
    agent = ZebioAgent()

    test_file = (
        agent.tool_registry.tools.project_context.project_root
        / "backend/app/ai/approved_test.py"
    )

    try:
        task = agent.task_manager.create(
            session_id="approval-task-test",
            goal="Create a test file.",
        )
        agent.task_manager.start(task.task_id)

        task_step = agent.task_manager.create_step(
            task_id=task.task_id,
            tool_name="create_file",
            arguments={
                "relative_path": "backend/app/ai/approved_test.py",
                "content": "def approved_test():\n    return True",
            },
        )

        agent.task_manager.start_step(task_step.step_id)

        approval = agent.approval_manager.create(
            session_id="approval-task-test",
            task_id=task.task_id,
            step_id=task_step.step_id,
            tool_name="create_file",
            arguments={
                "relative_path": "backend/app/ai/approved_test.py",
                "content": "def approved_test():\n    return True",
            },
            risk=ToolRisk.LOW_RISK_WRITE,
        )

        agent.approval_manager.approve(approval.approval_id)

        result = agent.execute_approved_action(approval.approval_id)

        print(f"\nAPPROVED ACTION RESULT: {result!r}")
        print(f"RESULT TYPE: {type(result).__name__}")

        assert result == "Created backend/app/ai/approved_test.py"

        updated_task = agent.task_manager.get(task.task_id)

        updated_step = agent.task_manager.get_step(task_step.step_id)

        assert updated_task.status.value == "running"
        assert updated_step.status.value == "completed"
        assert updated_step.completed_at is not None
        assert updated_step.error is None

    finally:
        if test_file.exists():
            test_file.unlink()

def test_resume_approved_action_continues_existing_task():
    agent = ZebioAgent()

    test_file = (
        agent.tool_registry.tools.project_context.project_root
        / "backend/app/ai/resume_test.py"
    )

    try:
        task = agent.task_manager.create(
            session_id="resume-test",
            goal="Create a test file.",
        )
        agent.task_manager.start(task.task_id)

        task_step = agent.task_manager.create_step(
            task_id=task.task_id,
            tool_name="create_file",
            arguments={
                "relative_path": "backend/app/ai/resume_test.py",
                "content": "def resume_test():\n    return True",
            },
        )
        agent.task_manager.start_step(task_step.step_id)

        approval = agent.approval_manager.create(
            session_id="resume-test",
            task_id=task.task_id,
            step_id=task_step.step_id,
            tool_name="create_file",
            arguments=task_step.arguments,
            tool_call_id="call_resume_1",
            risk=ToolRisk.LOW_RISK_WRITE,
        )

        agent.approval_manager.approve(approval.approval_id)

        assistant_tool_call = {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_resume_1",
                    "function": {
                        "name": "create_file",
                        "arguments": task_step.arguments,
                    },
                }
            ],
        }

        messages = [
            {
                "role": "user",
                "content": "Create resume_test.py.",
            },
            assistant_tool_call,
        ]

        final_response = SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="The file was created successfully.",
                tool_calls=[],
            )
        )

        chat_call_count = 0
        captured_messages = []

        def fake_chat_with_tools(messages, tools):
            nonlocal chat_call_count
            chat_call_count += 1

            captured_messages.clear()
            captured_messages.extend(messages)

            assert captured_messages[-1]["role"] == "tool"
            assert captured_messages[-1]["tool_call_id"] == "call_resume_1"

            return final_response

        agent.ollama_client.chat_with_tools = fake_chat_with_tools  # type: ignore

        result = agent.resume_approved_action(
            approval.approval_id,
            messages,
        )

        assert result == "The file was created successfully."
        assert chat_call_count == 1

        updated_task = agent.task_manager.get(task.task_id)
        updated_step = agent.task_manager.get_step(task_step.step_id)
        updated_approval = agent.approval_manager.get(
            approval.approval_id
        )

        assert updated_task.status == TaskStatus.COMPLETED
        assert updated_step.status == TaskStepStatus.COMPLETED
        assert updated_approval.status == ApprovalStatus.EXECUTED

        assert captured_messages[-1]["role"] == "tool"
        assert captured_messages[-1]["tool_call_id"] == "call_resume_1"

        assert len(agent.task_manager.tasks) == 1

    finally:
        if test_file.exists():
            test_file.unlink()

def test_resume_approved_action_fails_task_when_llm_resume_fails():
    agent = ZebioAgent()

    test_file = (
        agent.tool_registry.tools.project_context.project_root
        / "backend/app/ai/resume_failure_test.py"
    )

    try:
        task = agent.task_manager.create(
            session_id="resume-failure-test",
            goal="Create a test file.",
        )
        agent.task_manager.start(task.task_id)

        task_step = agent.task_manager.create_step(
            task_id=task.task_id,
            tool_name="create_file",
            arguments={
                "relative_path": "backend/app/ai/resume_failure_test.py",
                "content": "def resume_failure_test():\n    return True",
            },
        )
        agent.task_manager.start_step(task_step.step_id)

        approval = agent.approval_manager.create(
            session_id="resume-failure-test",
            task_id=task.task_id,
            step_id=task_step.step_id,
            tool_name="create_file",
            arguments=task_step.arguments,
            risk=ToolRisk.LOW_RISK_WRITE,
        )

        agent.approval_manager.approve(approval.approval_id)

        messages = [
            {
                "role": "user",
                "content": "Create resume_failure_test.py.",
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_resume_failure_1",
                        "function": {
                            "name": "create_file",
                            "arguments": task_step.arguments,
                        },
                    }
                ],
            },
        ]

        def failing_chat_with_tools(messages, tools):
            raise RuntimeError("LLM unavailable")

        agent.ollama_client.chat_with_tools = failing_chat_with_tools  # type: ignore

        try:
            agent.resume_approved_action(
                approval.approval_id,
                messages,
            )
        except RuntimeError as exc:
            assert str(exc) == "LLM unavailable"
        else:
            raise AssertionError(
                "resume_approved_action() should propagate the LLM failure."
            )

        updated_task = agent.task_manager.get(task.task_id)
        updated_step = agent.task_manager.get_step(task_step.step_id)
        updated_approval = agent.approval_manager.get(
            approval.approval_id
        )

        assert updated_task.status == TaskStatus.FAILED
        assert updated_task.errors == ["LLM unavailable"]
        assert updated_step.status == TaskStepStatus.COMPLETED
        assert updated_approval.status == ApprovalStatus.EXECUTED

    finally:
        if test_file.exists():
            test_file.unlink()

def test_resume_approved_action_continues_when_llm_requests_another_tool():
    agent = ZebioAgent()

    test_file = (
        agent.tool_registry.tools.project_context.project_root
        / "backend/app/ai/resume_multi_step_test.py"
    )

    try:
        task = agent.task_manager.create(
            session_id="resume-multi-step-test",
            goal="Create a test file and inspect it.",
        )
        agent.task_manager.start(task.task_id)

        task_step = agent.task_manager.create_step(
            task_id=task.task_id,
            tool_name="create_file",
            arguments={
                "relative_path": "backend/app/ai/resume_multi_step_test.py",
                "content": "def resume_multi_step_test():\n    return True",
            },
        )
        agent.task_manager.start_step(task_step.step_id)

        approval = agent.approval_manager.create(
            session_id="resume-multi-step-test",
            task_id=task.task_id,
            step_id=task_step.step_id,
            tool_name="create_file",
            arguments=task_step.arguments,
            tool_call_id="call_resume_multi_1",
            risk=ToolRisk.LOW_RISK_WRITE,
        )

        agent.approval_manager.approve(approval.approval_id)

        messages = [
            {
                "role": "user",
                "content": "Create resume_multi_step_test.py and inspect it.",
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_resume_multi_1",
                        "function": {
                            "name": "create_file",
                            "arguments": task_step.arguments,
                        },
                    }
                ],
            },
        ]

        second_tool_call_response = SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="",
                tool_calls=[
                    SimpleNamespace(
                        id="call_resume_multi_2",
                        function=SimpleNamespace(
                            name="read_file",
                            arguments={
                                "relative_path": (
                                    "backend/app/ai/resume_multi_step_test.py"
                                )
                            },
                        ),
                    )
                ],
            )
        )

        final_response = SimpleNamespace(
            message=SimpleNamespace(
                role="assistant",
                content="The file was created and inspected successfully.",
                tool_calls=[],
            )
        )

        chat_call_count = 0

        captured_messages = []

        def fake_chat_with_tools(messages, tools):
            captured_messages.clear()
            captured_messages.extend(messages)
            nonlocal chat_call_count
            chat_call_count += 1

            if chat_call_count == 1:
                assert messages[-1]["role"] == "tool"
                assert messages[-1]["tool_call_id"] == "call_resume_multi_1"

                return second_tool_call_response

            if chat_call_count == 2:
                assert messages[-1]["role"] == "tool"
                assert messages[-1]["tool_call_id"] == "call_resume_multi_2"

                return final_response

            raise AssertionError("Unexpected extra LLM call")


        agent.ollama_client.chat_with_tools = fake_chat_with_tools  # type: ignore

        result = agent.resume_approved_action(
            approval.approval_id,
            messages,
        )

        assert result == "The file was created and inspected successfully."
        assert chat_call_count == 2

        assert captured_messages[-1]["role"] == "tool"
        assert captured_messages[-1]["tool_call_id"] == "call_resume_multi_2"

        updated_task = agent.task_manager.get(task.task_id)
        updated_step = agent.task_manager.get_step(task_step.step_id)
        updated_approval = agent.approval_manager.get(
            approval.approval_id
        )

        assert updated_task.status == TaskStatus.COMPLETED
        assert updated_step.status == TaskStepStatus.COMPLETED
        assert updated_approval.status == ApprovalStatus.EXECUTED

        steps = agent.task_manager.get_steps(task.task_id)

        assert len(steps) == 2
        assert steps[0].tool_name == "create_file"
        assert steps[0].status == TaskStepStatus.COMPLETED
        assert steps[1].tool_name == "read_file"
        assert steps[1].status == TaskStepStatus.COMPLETED

    finally:
        if test_file.exists():
            test_file.unlink()

def test_approval_request_can_be_linked_to_task():
    agent = ZebioAgent()

    task = agent.task_manager.create(
        session_id="approval-task-link-test",
        goal="Create a test file.",
    )

    approval = agent.approval_manager.create(
        session_id="approval-task-link-test",
        task_id=task.task_id,
        step_id="step-1",
        tool_name="create_file",
        arguments={
            "relative_path": "backend/app/ai/task_link_test.py",
            "content": "def task_link_test():\n    return True",
        },
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    assert approval.session_id == task.session_id
    assert approval.task_id == task.task_id

def test_approval_request_is_linked_to_the_specific_task_step():
    agent = ZebioAgent()

    task = agent.task_manager.create(
        session_id="approval-step-link-test",
        goal="Create a test file",
    )

    agent.task_manager.start(task.task_id)

    task_step = agent.task_manager.create_step(
        task_id=task.task_id,
        tool_name="create_file",
        arguments={
            "relative_path": "example.txt",
            "content": "hello",
        },
    )

    agent.task_manager.start_step(task_step.step_id)

    approval = agent.approval_manager.create(
        session_id=task.session_id,
        task_id=task.task_id,
        step_id=task_step.step_id,
        tool_name=task_step.tool_name,
        arguments=task_step.arguments,
        risk=ToolRisk.LOW_RISK_WRITE,
    )

    assert approval.task_id == task.task_id

    assert approval.step_id == task_step.step_id    

def test_execute_tool_does_not_change_task_step_lifecycle():
    agent = ZebioAgent()

    task = agent.task_manager.create(
        session_id="task-step-integration",
        goal="Inspect the project.",
    )
    agent.task_manager.start(task.task_id)

    step = agent.task_manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py",
        },
    )

    agent.task_manager.start_step(step.step_id)

    result = agent._execute_tool(
        "read_file",
        {
            "relative_path": "backend/app/ai/agent.py",
        },
        session_id="task-step-integration",
        task_id=task.task_id,
    )

    assert isinstance(result, str)

    updated_step = agent.task_manager.get_step(step.step_id)

    assert updated_step.status == TaskStepStatus.RUNNING

def test_run_creates_and_completes_task_step_for_native_tool_call():
    agent = ZebioAgent()

    tool_call = SimpleNamespace(
        id="call_step_1",
        function=SimpleNamespace(
            name="read_file",
            arguments={
                "relative_path": "backend/app/ai/agent.py",
            },
        ),
    )

    responses = [
        SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[tool_call],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="I inspected the agent implementation.",
                tool_calls=[],
            )
        ),
    ]

    def fake_chat_with_tools(messages, tools):
        return responses.pop(0)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools # type: ignore

    messages = [
        {
            "role": "user",
            "content": "Inspect the agent implementation.",
        }
    ]

    result = agent.run(
        messages,
        session_id="task-step-orchestration-test",
    )

    assert result == "I inspected the agent implementation."

    tasks = agent.task_manager.tasks

    assert len(tasks) == 1

    task = next(iter(tasks.values()))

    assert task.status.value == "completed"

    task_steps = [
        step
        for step in agent.task_manager.steps.values()
        if step.task_id == task.task_id
    ]

    assert len(task_steps) == 1

    step = task_steps[0]

    assert step.tool_name == "read_file"
    assert step.arguments == {
        "relative_path": "backend/app/ai/agent.py",
    }
    assert step.status == TaskStepStatus.COMPLETED
    assert step.completed_at is not None
    assert step.error is None    

def test_run_creates_and_completes_task_step_for_legacy_tool_call():
    agent = ZebioAgent()

    responses = [
        SimpleNamespace(
            message=SimpleNamespace(
                content=(
                    '{"name": "read_file", '
                    '"arguments": {"relative_path": "backend/app/ai/agent.py"}}'
                ),
                tool_calls=[],
            )
        ),
        SimpleNamespace(
            message=SimpleNamespace(
                content="I inspected the agent implementation.",
                tool_calls=[],
            )
        ),
    ]

    def fake_chat_with_tools(messages, tools):
        return responses.pop(0)

    agent.ollama_client.chat_with_tools = fake_chat_with_tools # type: ignore

    result = agent.run(
        [
            {
                "role": "user",
                "content": "Inspect the agent implementation.",
            }
        ],
        session_id="legacy-task-step-orchestration-test",
    )

    assert result == "I inspected the agent implementation."

    tasks = agent.task_manager.tasks

    assert len(tasks) == 1

    task = next(iter(tasks.values()))

    assert task.status.value == "completed"

    task_steps = [
        step
        for step in agent.task_manager.steps.values()
        if step.task_id == task.task_id
    ]

    assert len(task_steps) == 1

    step = task_steps[0]

    assert step.tool_name == "read_file"
    assert step.arguments == {
        "relative_path": "backend/app/ai/agent.py",
    }
    assert step.status == TaskStepStatus.COMPLETED
    assert step.completed_at is not None
    assert step.error is None    

def test_final_decision_requires_explicitly_requested_read_after_search():
    agent = ZebioAgent()

    task = agent.task_manager.create(
        session_id="explicit-read-test",
        goal=(
            "Find the file that defines the ZebioAgent class, "
            "then read that file and tell me the names of all "
            "tools registered by the agent. Do not modify any files."
        ),
        requires_verification=False,
    )

    context = AgentContext(task=task)

    agent.task_manager.start(task.task_id)

    context.loop_state.completed_actions.extend(
        [
            "search_code",
        ]
    )

    agent.task_manager.add_observation(
        task.task_id,
        {
            "type": "observation",
            "tool": "read_file",
            "arguments": {
                "relative_path": "backend/app/ai/agent.py",
            },
            "result": "class ZebioAgent:",
        },
    )

    agent._handle_final_decision(
        FinalDecision(
            type="final",
            message="I found the file.",
        ),
        context,
    )

    assert context.runtime_feedback is not None
    assert context.runtime_feedback.type == "requested_action_incomplete"
    assert "read_file" in context.runtime_feedback.message
    assert task.completed_at is None    

def test_final_decision_can_complete_after_requested_read():
    agent = ZebioAgent()

    task = agent.task_manager.create(
        session_id="explicit-read-complete-test",
        goal=(
            "Find the file that defines the ZebioAgent class, "
            "then read that file and tell me the names of all "
            "tools registered by the agent. Do not modify any files."
        ),
        requires_verification=False,
    )

    agent.task_manager.start(task.task_id)

    context = AgentContext(task=task)

    context.loop_state.completed_actions.extend(
        [
            "search_code",
            "read_file",
        ]
    )

    agent.task_manager.add_observation(
        task.task_id,
        {
            "type": "observation",
            "tool": "read_file",
            "arguments": {
                "relative_path": "backend/app/ai/agent.py",
            },
            "result": "class ZebioAgent:",
        },
    )

    finished, response = agent._handle_final_decision(
        FinalDecision(
            type="final",
            message="The file contains the registered tools.",
        ),
        context,
    )

    assert finished is True
    assert response == "The file contains the registered tools."
    assert task.completed_at is not None    

def test_final_decision_cannot_complete_verification_without_evidence():
    agent = ZebioAgent()

    task = agent.task_manager.create(
        session_id="verification-evidence-missing-test",
        goal="Modify the implementation and verify that the change works.",
        requires_verification=True,
    )

    agent.task_manager.start(task.task_id)

    context = AgentContext(task=task)

    # Simulate the agent already entering the verification phase.
    context.loop_state.verification_started = True

    agent.task_manager.add_observation(
        task.task_id,
        {
            "type": "observation",
            "tool": "read_file",
            "arguments": {
                "relative_path": "backend/app/ai/example.py",
            },
            "result": "Existing implementation inspected.",
        },
    )

    finished, response = agent._handle_final_decision(
        FinalDecision(
            type="final",
            message="The implementation is complete.",
        ),
        context,
    )

    assert finished is False
    assert response is None

    assert task.status == TaskStatus.RUNNING
    assert task.completed_at is None

    assert task.verification_status is None
    assert task.verification_evidence is None

    assert context.runtime_feedback is not None
    assert context.runtime_feedback.type == "verification_evidence_required"


def test_final_decision_can_complete_after_verification_evidence():
    agent = ZebioAgent()

    task = agent.task_manager.create(
        session_id="verification-evidence-test",
        goal="Modify the implementation and verify that the change works.",
        requires_verification=True,
    )

    agent.task_manager.start(task.task_id)

    context = AgentContext(task=task)

    # Simulate the agent entering verification and successfully
    # executing a verification command.
    context.loop_state.verification_started = True

    agent.task_manager.add_observation(
        task.task_id,
        {
            "type": "observation",
            "tool": "run_command",
            "arguments": {
                "command": "pytest .\\tests",
                "working_directory": ".",
            },
            "result": {
                "command": "pytest .\\tests",
                "return_code": 0,
                "stdout": "42 passed",
                "stderr": "",
                "timeout": False,
            },
        },
    )

    finished, response = agent._handle_final_decision(
        FinalDecision(
            type="final",
            message="The implementation was completed and verified successfully.",
        ),
        context,
    )

    assert finished is True
    assert response == (
        "The implementation was completed and verified successfully."
    )

    assert task.status == TaskStatus.COMPLETED
    assert task.completed_at is not None

    assert task.verification_status == "succeeded"
    assert task.verification_evidence
    assert task.verification_summary is not None

def test_parse_agent_decisions_converts_final_response():
    agent = ZebioAgent()

    response = type(
        "Response",
        (),
        {
            "message": type(
                "Message",
                (),
                {
                    "content": "The implementation is complete.",
                    "tool_calls": None,
                },
            )()
        },
    )()

    parsed = agent._parse_agent_decisions(response)

    assert len(parsed.decisions) == 1
    assert parsed.decisions[0].type == "final"
    assert parsed.decisions[0].message == "The implementation is complete."
    assert parsed.tool_call_ids == []


def test_parse_agent_decisions_converts_native_tool_call():
    agent = ZebioAgent()

    response = type(
        "Response",
        (),
        {
            "message": type(
                "Message",
                (),
                {
                    "content": "",
                    "tool_calls": [
                        type(
                            "ToolCall",
                            (),
                            {
                                "id": "call_1",
                                "function": type(
                                    "Function",
                                    (),
                                    {
                                        "name": "read_file",
                                        "arguments": {
                                            "relative_path": "test.py"
                                        },
                                    },
                                )(),
                            },
                        )()
                    ],
                },
            )()
        },
    )()

    parsed = agent._parse_agent_decisions(response)

    assert len(parsed.decisions) == 1
    assert parsed.decisions[0].type == "action"
    assert parsed.decisions[0].tool == "read_file"
    assert parsed.decisions[0].arguments == {
        "relative_path": "test.py"
    }
    assert parsed.tool_call_ids == ["call_1"]


def test_parse_agent_decisions_converts_legacy_text_tool_request():
    agent = ZebioAgent()

    response = type(
        "Response",
        (),
        {
            "message": type(
                "Message",
                (),
                {
                    "content": (
                        '{"name": "read_file", '
                        '"arguments": '
                        '{"relative_path": "test.py"}}'
                    ),
                    "tool_calls": None,
                },
            )()
        },
    )()

    parsed = agent._parse_agent_decisions(response)

    assert len(parsed.decisions) == 1
    assert parsed.decisions[0].type == "action"
    assert parsed.decisions[0].tool == "read_file"
    assert parsed.decisions[0].arguments == {
        "relative_path": "test.py"
    }
    assert parsed.tool_call_ids == [None]

def test_parse_agent_decisions_preserves_legacy_parse_error():
    agent = ZebioAgent()

    response = type(
        "Response",
        (),
        {
            "message": type(
                "Message",
                (),
                {
                    "content": '{"name": "read_file",',
                    "tool_calls": None,
                },
            )()
        },
    )()

    parsed = agent._parse_agent_decisions(response)

    assert parsed.decisions == []
    assert parsed.tool_call_ids == []
    assert parsed.parse_error is not None