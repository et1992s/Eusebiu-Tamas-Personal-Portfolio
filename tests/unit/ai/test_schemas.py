from pydantic import TypeAdapter, ValidationError

from app.ai.schemas import (
    ActionDecision,
    AgentDecision,
    FinalDecision,
    Observation,
    ParsedAgentResponse,
)


def test_action_decision_is_valid():
    decision = ActionDecision(
        type="action",
        tool="read_file",
        arguments={"relative_path": "test.py"},
        intent="Inspect the implementation.",
    )

    assert decision.type == "action"
    assert decision.tool == "read_file"


def test_final_decision_is_valid():
    decision = FinalDecision(
        type="final",
        message="The implementation is complete.",
    )

    assert decision.type == "final"
    assert decision.message == "The implementation is complete."


def test_observation_is_valid():
    observation = Observation(
        tool="run_command",
        result={
            "command": "pytest",
            "return_code": 0,
            "stdout": "1 passed",
            "stderr": "",
        },
    )

    assert observation.type == "observation"
    assert observation.result["return_code"] == 0

def test_parsed_agent_response_preserves_decisions_and_protocol_ids():
    action = ActionDecision(
        type="action",
        tool="read_file",
        arguments={"relative_path": "test.py"},
        intent="Inspect the implementation.",
    )

    response = ParsedAgentResponse(
        decisions=[action],
        tool_call_ids=["call_123"],
    )

    assert len(response.decisions) == 1
    assert isinstance(response.decisions[0], ActionDecision)
    assert response.decisions[0].tool == "read_file"
    assert response.tool_call_ids == ["call_123"]

def test_invalid_action_is_rejected():
    adapter = TypeAdapter(AgentDecision)

    try:
        adapter.validate_python(
            {
                "type": "action",
                "arguments": {},
            }
        )
    except ValidationError:
        return

    raise AssertionError("Invalid action decision was accepted")


def test_invalid_final_is_rejected():
    adapter = TypeAdapter(AgentDecision)

    try:
        adapter.validate_python(
            {
                "type": "final",
            }
        )
    except ValidationError:
        return

    raise AssertionError("Invalid final decision was accepted")


def test_unknown_decision_type_is_rejected():
    adapter = TypeAdapter(AgentDecision)

    try:
        adapter.validate_python(
            {
                "type": "something_else",
                "message": "x",
            }
        )
    except ValidationError:
        return

    raise AssertionError("Unknown decision type was accepted")