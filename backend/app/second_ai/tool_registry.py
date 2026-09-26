from typing import Callable

from .tools import ProjectTools


class ToolRegistry:
    def __init__(self, tools: ProjectTools):
        self.tools = tools

        self._tools: dict[str, Callable[..., object]] = {
            "project_overview": tools.project_overview,
            "list_directory": tools.list_directory,
            "read_file": tools.read_file,
            "search_code": tools.search_code,
        }

    def get(self, name: str) -> Callable[..., object]:
        try:
            return self._tools[name]
        except KeyError:
            raise ValueError(f"Unknown tool: {name}")

    def names(self) -> list[str]:
        return list(self._tools)