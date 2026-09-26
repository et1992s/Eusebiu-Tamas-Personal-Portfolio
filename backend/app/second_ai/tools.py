from pathlib import Path


class ProjectTools:
    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root).resolve()

    def project_overview(self) -> dict[str, object]:
        return {
            "project_root": str(self.project_root),
            "entries": sorted(item.name for item in self.project_root.iterdir()),
        }

    def _resolve(self, path: str) -> Path:
        target = (self.project_root / path).resolve()

        if target != self.project_root and self.project_root not in target.parents:
            raise ValueError("Path is outside the project root")

        return target

    def list_directory(self, path: str = ".") -> list[str]:
        target = self._resolve(path)

        if not target.is_dir():
            raise NotADirectoryError(path)

        return sorted(item.name for item in target.iterdir())

    def read_file(self, path: str) -> str:
        target = self._resolve(path)

        if not target.is_file():
            raise FileNotFoundError(path)

        return target.read_text(encoding="utf-8")

    def search_code(self, query: str, path: str = ".") -> list[str]:
        target = self._resolve(path)

        if not target.exists():
            raise FileNotFoundError(path)

        matches = []

        for file in target.rglob("*"):
            if not file.is_file():
                continue

            if any(
                ignored in file.parts
                for ignored in (".git", ".venv", "node_modules", "__pycache__")
            ):
                continue

            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            if query.lower() in content.lower():
                matches.append(str(file.relative_to(self.project_root)))

        return sorted(matches)