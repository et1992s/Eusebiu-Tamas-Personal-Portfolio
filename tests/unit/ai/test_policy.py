from app.ai.policy import PolicyDecision, PolicyEngine
from app.ai.tools import ToolRisk


def test_read_tools_are_allowed():
    policy = PolicyEngine()

    assert (
        policy.evaluate("read_file", ToolRisk.READ, {})
        == PolicyDecision.ALLOW
    )


def test_low_risk_writes_require_approval():
    policy = PolicyEngine()

    assert (
        policy.evaluate("write_file", ToolRisk.LOW_RISK_WRITE, {})
        == PolicyDecision.REQUIRE_APPROVAL
    )


def test_commands_require_approval():
    policy = PolicyEngine()

    assert (
        policy.evaluate("run_command", ToolRisk.COMMAND, {})
        == PolicyDecision.REQUIRE_APPROVAL
    )


def test_system_changes_require_approval():
    policy = PolicyEngine()

    assert (
        policy.evaluate("install_package", ToolRisk.SYSTEM_CHANGE, {})
        == PolicyDecision.REQUIRE_APPROVAL
    )


def test_destructive_actions_are_denied():
    policy = PolicyEngine()

    assert (
        policy.evaluate("delete_data", ToolRisk.DESTRUCTIVE, {})
        == PolicyDecision.DENY
    )

def test_read_only_command_is_allowed():
    policy = PolicyEngine()

    assert (
        policy.evaluate("run_command", ToolRisk.READ, {"command": "git status"})
        == PolicyDecision.ALLOW
    )


def test_low_risk_command_requires_approval():
    policy = PolicyEngine()

    assert (
        policy.evaluate(
            "run_command",
            ToolRisk.LOW_RISK_WRITE,
            {"command": "git add ."},
        )
        == PolicyDecision.REQUIRE_APPROVAL
    )


def test_system_change_command_requires_approval():
    policy = PolicyEngine()

    assert (
        policy.evaluate(
            "run_command",
            ToolRisk.SYSTEM_CHANGE,
            {"command": "pip install pandas"},
        )
        == PolicyDecision.REQUIRE_APPROVAL
    )


def test_destructive_command_is_denied():
    policy = PolicyEngine()

    assert (
        policy.evaluate(
            "run_command",
            ToolRisk.DESTRUCTIVE,
            {"command": "git reset --hard"},
        )
        == PolicyDecision.DENY
    )    