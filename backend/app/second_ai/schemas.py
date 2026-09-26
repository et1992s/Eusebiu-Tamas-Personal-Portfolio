from typing import Literal

from pydantic import BaseModel, Field


class Task(BaseModel):
    task_id: str
    goal: str
    status: Literal["pending", "running", "completed", "failed"] = "pending"


class Action(BaseModel):
    type: Literal["action"] = "action"
    tool: str
    arguments: dict[str, object] = Field(default_factory=dict)


class Final(BaseModel):
    type: Literal["final"] = "final"
    message: str


class Observation(BaseModel):
    tool: str
    arguments: dict[str, object] = Field(default_factory=dict)
    success: bool
    result: object


Decision = Action | Final