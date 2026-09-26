from .tools import ToolRisk


class CommandRiskClassifier:
    """Classifies shell commands according to their potential impact."""

    def classify(self, command: str) -> ToolRisk:
        """Return the risk category for a shell command."""

        normalized = command.strip().lower()

        if not normalized:
            raise ValueError("Command cannot be empty")

        read_only_commands = {
            "git status",
            "git status --short",
            "git diff",
            "git diff --cached",
            "git diff --stat",
            "git log",
            "git log --oneline",
            "git show",
            "git show head",
            "git branch --show-current",
            "git rev-parse --show-toplevel",
            "pytest",
            "pytest .\\tests",
            "pytest .\\tests -q",
            "python -m pytest .\\tests",
            "python -m pytest .\\tests -q",
            "python --version",
        }

        if normalized in read_only_commands:
            return ToolRisk.READ

        if normalized == "git add .":
            return ToolRisk.LOW_RISK_WRITE

        if normalized.startswith("pip install "):
            return ToolRisk.SYSTEM_CHANGE

        if normalized == "git reset --hard":
            return ToolRisk.DESTRUCTIVE

        return ToolRisk.COMMAND