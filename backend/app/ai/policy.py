from enum import Enum

from .tools import ToolRisk


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyEngine:
    """Determines whether a tool action may be executed."""

    def evaluate(
        self,
        tool_name: str,
        risk: ToolRisk,
        arguments: dict,
    ) -> PolicyDecision:
        """Evaluate a proposed tool action."""

        if risk == ToolRisk.READ:
            return PolicyDecision.ALLOW

        if risk == ToolRisk.LOW_RISK_WRITE:
            return PolicyDecision.REQUIRE_APPROVAL

        if risk == ToolRisk.COMMAND:
            return PolicyDecision.REQUIRE_APPROVAL

        if risk == ToolRisk.SYSTEM_CHANGE:
            return PolicyDecision.REQUIRE_APPROVAL

        if risk == ToolRisk.DESTRUCTIVE:
            return PolicyDecision.DENY

        return PolicyDecision.DENY