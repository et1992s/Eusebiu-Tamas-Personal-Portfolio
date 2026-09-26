from .schemas import Action, Observation
from .tool_registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, action: Action) -> Observation:
        try:
            tool = self.registry.get(action.tool)
            result = tool(**action.arguments)

            return Observation(
                tool=action.tool,
                arguments=action.arguments,
                success=True,
                result=result,
            )

        except Exception as exc:
            return Observation(
                tool=action.tool,
                arguments=action.arguments,
                success=False,
                result=f"{type(exc).__name__}: {exc}",
            )