import json
from pathlib import Path

from ollama import Client

from .executor import ToolExecutor
from .prompts import SYSTEM_PROMPT
from .schemas import Action, Decision, Final
from .task import TaskManager


class SecondAI:
    def __init__(
        self,
        project_root: str | Path,
        model: str = "qwen2.5-coder:14b",
        ollama_host: str = "http://localhost:11434",
    ):
        from .tools import ProjectTools
        from .tool_registry import ToolRegistry

        tools = ProjectTools(project_root)
        registry = ToolRegistry(tools)

        self.executor = ToolExecutor(registry)
        self.tasks = TaskManager()
        self.client = Client(host=ollama_host)
        self.model = model

    def _parse_decision(self, content: str) -> Decision:
        content = content.strip()

        if content.startswith("```"):
            lines = content.splitlines()

            if lines[0].startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            content = "\n".join(lines).strip()

        data = json.loads(content)

        if data.get("type") == "action":
            return Action.model_validate(data)

        if data.get("type") == "final":
            return Final.model_validate(data)

        raise ValueError("Invalid decision type")

    def run(self, goal: str, max_steps: int = 20) -> str:
        task = self.tasks.create(goal)
        self.tasks.start(task)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": goal},
        ]

        for step in range(max_steps):
            print(f"\n[SECOND_AI STEP {step + 1}]")

            response = self.client.chat(
                model=self.model,
                messages=messages,
            )

            content = response["message"]["content"]

            print("[MODEL]")
            print(content)

            decision = self._parse_decision(content)

            if isinstance(decision, Final):
                print("[FINAL]")
                print(decision.message)

                self.tasks.complete(task)
                return decision.message

            print("[ACTION]")
            print(decision.model_dump())

            observation = self.executor.execute(decision)

            print("[OBSERVATION]")
            print(observation.model_dump())

            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                }
            )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "TOOL OBSERVATION\n"
                        + json.dumps(
                            observation.model_dump(),
                            ensure_ascii=False,
                        )
                    ),
                }
            )

        self.tasks.fail(task)
        raise RuntimeError("Maximum agent steps reached")