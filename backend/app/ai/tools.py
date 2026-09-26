import json
import subprocess
from enum import Enum

from .project_context import ProjectContext


class ToolRisk(str, Enum):
    READ = "read"
    LOW_RISK_WRITE = "low_risk_write"
    COMMAND = "command"
    SYSTEM_CHANGE = "system_change"
    DESTRUCTIVE = "destructive"

TOOL_DEFINITIONS = {
    "read_file": {
        "description": (
            "Read a text file inside the project. "
            "For large files, use start_line and end_line "
            "to read only the relevant section."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": (
                        "Project-relative path of "
                        "the file to read."
                    ),
                },
                "start_line": {
                    "type": "integer",
                    "description": (
                        "Optional 1-based first line to read."
                    ),
                },
                "end_line": {
                    "type": "integer",
                    "description": (
                        "Optional 1-based last line to read."
                    ),
                },
            },
            "required": [
                "relative_path",
            ],
        },
    },
    "list_directory": {
        "description": (
            "List files and directories inside "
            "the project."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                    "description": (
                        "Project-relative directory "
                        "path. Defaults to the project root."
                    ),
                },
            },
        },
    },
    "search_code": {
        "description": (
            "Search project files for a class, function, "
            "symbol, import, configuration value, or text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Text or symbol to search for."
                    ),
                },
                "relative_path": {
                    "type": "string",
                    "description": (
                        "Project-relative directory "
                        "to search."
                    ),
                },
            },
            "required": [
                "query",
            ],
        },
    },
    "write_file": {
        "description": (
            "Modify an existing project file. "
            "Use read_file first when the current "
            "contents need to be inspected."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                },
                "content": {
                    "type": "string",
                },
            },
            "required": [
                "relative_path",
                "content",
            ],
        },
    },
    "create_file": {
        "description": (
            "Create a new project file."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "relative_path": {
                    "type": "string",
                },
                "content": {
                    "type": "string",
                },
            },
            "required": [
                "relative_path",
                "content",
            ],
        },
    },
    "run_command": {
        "description": (
            "Run a development command inside the project. "
            "Use this for tests, validation, builds, linters, "
            "package installation, and other short-lived engineering "
            "commands. Do not use this tool to start persistent "
            "development servers or other long-running processes. "
            "The working_directory is relative to the project root "
            "and defaults to the project root."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": (
                        "The short-lived development command to execute."
                    ),
                },
                "working_directory": {
                    "type": "string",
                    "description": (
                        "Project-relative directory in which to run "
                        "the command. Defaults to '.'. For example, "
                        "'backend' for backend Python commands or "
                        "'frontend' for frontend commands."
                    ),
                },
            },
            "required": [
                "command",
            ],
        },
    },
}


class ZebioTools:
    """Tools that Zebio can use to inspect and modify the project."""

    def __init__(self):
        self.project_context = ProjectContext()

    def _resolve_path(self, relative_path: str):
        """Resolve a path while keeping it inside the project."""

        path = (self.project_context.project_root / relative_path).resolve()

        try:
            path.relative_to(self.project_context.project_root)
        except ValueError as exc:
            raise ValueError("Access denied: path is outside the project.") from exc

        return path

    def read_file(
        self,
        relative_path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """Read a text file, optionally restricted to a line range."""

        file_path = self._resolve_path(relative_path)

        if not file_path.is_file():
            raise FileNotFoundError(f"File not found: {relative_path}")

        content = file_path.read_text(encoding="utf-8")

        lines = content.splitlines()

        # Return small files in full.
        if start_line is None and end_line is None and len(lines) <= 200:
            return content

        # For large files, return the first 200 lines and tell the agent
        # how to retrieve the rest with targeted line ranges.
        if start_line is None:
            start_line = 1

        if end_line is None:
            end_line = min(start_line + 199, len(lines))

        lines = content.splitlines()

        if start_line is None:
            start_line = 1

        if end_line is None:
            end_line = len(lines)

        if start_line < 1:
            raise ValueError("start_line must be >= 1")

        if end_line < start_line:
            raise ValueError("end_line must be >= start_line")

        selected_lines = lines[start_line - 1:end_line]

        return "\n".join(
            f"{line_number}: {line}"
            for line_number, line in enumerate(
                selected_lines,
                start=start_line,
            )
        )

    def list_directory(self, relative_path: str = ".") -> list[dict[str, str]]:
        """List files and directories inside the project."""

        directory = self._resolve_path(relative_path)

        if not directory.is_dir():
            raise NotADirectoryError(
                f"Directory not found: {relative_path}"
            )

        entries: list[dict[str, str]] = []

        for item in sorted(directory.iterdir(), key=lambda path: path.name.lower()):
            entries.append(
                {
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                }
            )

        return entries

    def search_code(
        self,
        query: str,
        relative_path: str = ".",
    ) -> list[dict[str, str | int]]:
        """Search project files for text and prioritise relevant matches."""

        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        search_root = self._resolve_path(relative_path)

        if not search_root.is_dir():
            raise NotADirectoryError(
                f"Search path is not a directory: {relative_path}"
            )

        ignored_directories = {
            ".git",
            ".venv",
            "__pycache__",
            "node_modules",
            ".pytest_cache",
        }

        ignored_files = {
            ".env",
            ".env.local",
            ".env.development",
            ".env.production",
            ".env.test",
            "credentials.json",
            "secrets.json",
        }

        query_lower = query.strip().lower()

        results: list[tuple[int, dict[str, str | int]]] = []

        for file_path in search_root.rglob("*"):
            if not file_path.is_file():
                continue

            if file_path.suffix.lower() in {
                ".pem",
                ".key",
                ".p12",
                ".pfx",
            }:
                continue

            if file_path.name in ignored_files:
                continue

            relative_file_path = file_path.relative_to(
                self.project_context.project_root
            )

            if any(
                part in ignored_directories
                for part in relative_file_path.parts
            ):
                continue

            try:
                content = file_path.read_text(
                    encoding="utf-8"
                )
            except (UnicodeDecodeError, OSError):
                continue

            relative_path_string = str(relative_file_path)
            relative_path_lower = relative_path_string.lower()

            for line_number, line in enumerate(
                content.splitlines(),
                start=1,
            ):
                line_lower = line.lower()

                if query_lower not in line_lower:
                    continue

                score = 0

                stripped_line = line.strip()

                # Highest priority: an actual class/function definition.
                if (
                    stripped_line == f"class {query.strip()}:"
                    or stripped_line.startswith(
                        f"class {query.strip()}("
                    )
                ):
                    score += 1000

                if (
                    stripped_line.startswith(
                        f"def {query.strip()}("
                    )
                    or stripped_line.startswith(
                        f"async def {query.strip()}("
                    )
                ):
                    score += 1000

                # Exact symbol match as a standalone token.
                if query_lower in line_lower:
                    score += 100

                # Prefer the canonical source file over tests/backups.
                if relative_path_lower.endswith(
                    f"{query_lower}.py"
                ):
                    score += 200

                if "/tests/" in relative_path_lower.replace(
                    "\\",
                    "/",
                ):
                    score -= 100

                if (
                    ".backup" in relative_path_lower
                    or "routing-backup" in relative_path_lower
                    or ".bak" in relative_path_lower
                ):
                    score -= 300

                # Prefer source files over test files when the match
                # is otherwise equivalent.
                if "/backend/app/" in relative_path_lower.replace(
                    "\\",
                    "/",
                ):
                    score += 50

                
                results.append(
                    (
                        score,
                        {
                            "file": relative_path_string,
                            "line": line_number,
                            "content": stripped_line,
                        },
                    )
                )

        if not results and relative_path.strip() not in {
            "",
            ".",
        }:
            fallback_results = self.search_code(
                query=query,
                relative_path=".",
            )

            if fallback_results:
                return [
                    {
                        **result,
                        "search_scope": "project_root_fallback",
                        "requested_scope": relative_path,
                    }
                    for result in fallback_results
                ]

        results.sort(
            key=lambda item: (
                -item[0],
                str(item[1]["file"]).lower(),
                int(item[1]["line"]),
            )
        )

        return [ 
            result 
            for _, result in results 
        ]

    def write_file(self, relative_path: str,  content: str) -> str:
        """Overwrite an existing project file."""

        file_path = self._resolve_path( relative_path)

        if not file_path.is_file():
            raise FileNotFoundError(f"File does not exist: {relative_path}")

        file_path.write_text(content, encoding="utf-8")

        return f"Updated {relative_path}"

    def create_file(self, relative_path: str, content: str) -> str:
        """Create a new file inside the project."""

        file_path = self._resolve_path(relative_path)

        if file_path.exists():
            raise FileExistsError(f"File already exists: {relative_path}")

        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding="utf-8")

        return f"Created {relative_path}"

    def run_command(self, command: str, working_directory: str = ".") -> dict:
        """Run a shell command from the project root."""

        if not command.strip():
            raise ValueError("Command cannot be empty.")

        command_directory = self._resolve_path(working_directory)

        if not command_directory.is_dir():
            raise NotADirectoryError(
                f"Working directory is not a directory: "
                f"{working_directory}")

        long_running_patterns = (
            "uvicorn",
            "npm run dev",
            "npm start",
            "vite",
            "python -m http.server")

        command_lower = command.strip().lower()

        if any(pattern in command_lower for pattern in long_running_patterns):
            return {
                "command": command,
                "return_code": None,
                "stdout": "",
                "stderr": (
                    "Long-running command blocked. "
                    "This command starts a persistent process and "
                    "must not be executed by the autonomous agent."),

                "timeout": False,
                "blocked": True}

        try:
            result = subprocess.run(
                command,
                cwd=command_directory,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120)
            
        except subprocess.TimeoutExpired as exc:
            return {
                "command": command,
                "return_code": None,
                "stdout": exc.stdout or "",
                "stderr": (exc.stderr or "") + "\nCommand timed out after 120 seconds.", # type: ignore
                "timeout": True}

        return {
            "command": command,
            "return_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timeout": False}

class ToolRegistry:
    """Registry for Zebio's available tools."""

    def __init__(self):
        self.tools = ZebioTools()

        self.registry = {
            "read_file": {
                "handler": self.tools.read_file,
                "risk": ToolRisk.READ,
            },
            "list_directory": {
                "handler": self.tools.list_directory,
                "risk": ToolRisk.READ,
            },
            "search_code": {
                "handler": self.tools.search_code,
                "risk": ToolRisk.READ,
            },
            "write_file": {
                "handler": self.tools.write_file,
                "risk": ToolRisk.LOW_RISK_WRITE,
            },
            "create_file": {
                "handler": self.tools.create_file,
                "risk": ToolRisk.LOW_RISK_WRITE,
            },
            "run_command": {
                "handler": self.tools.run_command,
                "risk": ToolRisk.COMMAND,
            },
        }

    def list_tools(self) -> list[str]:
        """Return the names of all registered tools."""

        return sorted(self.registry.keys())

    def parse_tool_request(self,content: str) -> dict:
        """
        Extract a tool request from model output.

        Supports JSON embedded in normal model text and JSON wrapped
        in Markdown code fences.

        Also tolerates Qwen output such as:

            write\\_file

        where the underscore has incorrectly been escaped.
        """
        content = content.strip()

        if not content:
            raise ValueError("Model response is empty.")

        # Remove Markdown JSON fences.
        if "```json" in content:
            content = content.split("```json", 1)[1]

            if "```" in content:
                content = content.split("```", 1)[0]

            content = content.strip()

        # Some models escape Markdown characters inside JSON-like
        # output, for example write\_file.
        content = content.replace("\\_", "_")

        decoder = json.JSONDecoder()

        # Find the beginning of a JSON object anywhere in the
        # response.
        start = content.find("{")

        if start == -1:
            raise ValueError("Model response does not contain a tool request.")

        try:
            request, _ = decoder.raw_decode(content[start:])
        except json.JSONDecodeError as exc:
            raise ValueError("Model response contains invalid tool JSON.") from exc

        if not isinstance(request, dict):
            raise ValueError("Tool request must be a JSON object.")

        tool_name = request.get("name",  request.get("function_name"))

        arguments = request.get("arguments", {})

        if tool_name not in self.registry:
            raise ValueError(f"Unknown tool: {tool_name}")

        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object.")

        return {"name": tool_name, "arguments": arguments}

    def get_ollama_tools(self) -> list[dict]:
        """Return tool definitions for the local model."""

        return [
            {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": definition["description"],
                    "parameters": definition["parameters"],
                },
            }
            for tool_name, definition in TOOL_DEFINITIONS.items()
        ]

    def execute(self, tool_name: str, arguments: dict):
        """Execute a registered tool."""

        if tool_name not in self.registry:
            raise ValueError(f"Unknown tool: {tool_name}")

        handler = self.registry[tool_name]["handler"]

        return handler(**arguments)