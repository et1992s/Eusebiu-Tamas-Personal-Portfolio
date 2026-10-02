from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ActionDecision(BaseModel):
    """The agent requests one concrete engineering action."""

    type: Literal["action"]
    tool: str
    arguments: dict[str, object] = Field(default_factory=dict)
    intent: str


class FinalDecision(BaseModel):
    """The agent decides that it has enough information to respond."""

    type: Literal["final"]
    message: str


AgentDecision = Annotated[
    ActionDecision | FinalDecision,
    Field(discriminator="type"),
]

class ParsedAgentResponse(BaseModel):
    """
    Provider-neutral representation of one model response.

    The decisions describe what the agent wants to do.
    Protocol metadata remains separate from the decision itself.
    """

    decisions: list[ActionDecision | FinalDecision] = []

    tool_call_ids: list[str | None] = Field(
        default_factory=list,
    )

    parse_error: str | None = None

class Observation(BaseModel):
    """A factual result returned by the runtime after an action."""

    type: Literal["observation"] = "observation"
    tool: str
    arguments: dict[str, object] = Field(default_factory=dict)
    result: object

class ParsedAgentResponse(BaseModel):
    decisions: list[ActionDecision | FinalDecision] = []
    tool_call_ids: list[str | None] = Field(default_factory=list)
    parse_error: str | None = None
    thought_only: str | None = None