from pathlib import Path


class ProjectContext:
    """Provides cached context about the Zebio project."""

    def __init__(self, project_root: str | Path | None = None):
        if project_root is None:
            self.project_root = Path(__file__).resolve().parents[3]
        else:
            self.project_root = Path(project_root).resolve()

        self._project_structure: str | None = None

    def get_project_structure(self) -> str:
        """Return the cached project structure."""

        if self._project_structure is not None:
            return self._project_structure

        ignored_directories = {
            ".git",
            ".venv",
            "__pycache__",
            "node_modules",
            ".pytest_cache",
        }

        lines = [f"Project root: {self.project_root}"]

        for path in sorted(self.project_root.rglob("*")):
            relative_path = path.relative_to(self.project_root)

            if any(
                part in ignored_directories
                for part in relative_path.parts
            ):
                continue

            depth = len(relative_path.parts) - 1
            prefix = "    " * depth

            if path.is_dir():
                lines.append(f"{prefix}{path.name}/")
            else:
                lines.append(f"{prefix}{path.name}")

        self._project_structure = "\n".join(lines)

        return self._project_structure

    def read_file(self, relative_path: str) -> str:
        """Read a text file inside the ZEBIO project."""

        file_path = (
            self.project_root / relative_path
        ).resolve()

        try:
            file_path.relative_to(self.project_root)
        except ValueError:
            raise ValueError(
                "Access denied: path is outside the project."
            )

        if not file_path.is_file():
            raise FileNotFoundError(
                f"File not found: {relative_path}"
            )

        return file_path.read_text(
            encoding="utf-8"
        )