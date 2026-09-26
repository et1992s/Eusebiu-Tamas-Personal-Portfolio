from pathlib import Path

import pytest

from app.ai.project_context import ProjectContext

def test_read_file_accepts_file_inside_project(tmp_path: Path):
    project_root = tmp_path
    test_file = project_root /"example.txt"
    test_file.write_text("hello zebios", encoding="utf-8")

    context = ProjectContext(project_root=project_root)

    result = context.read_file("example.txt")

    assert result == "hello zebios"

def test_read_file_rejects_path_outside_project(tmp_path: Path):
    project_root = tmp_path / "project"
    outside_file = tmp_path /"outside.txt"

    project_root.mkdir()
    outside_file.write_text("secret", encoding="utf-8")

    context = ProjectContext(project_root=project_root)

    with pytest.raises(ValueError, match="Access denied"):
        context.read_file("../outside.txt")

def test_read_file_rejects_absolute_path_outside_project(tmp_path: Path):
    project_root = tmp_path / "project"
    outside_file = tmp_path / "outside.txt"

    project_root.mkdir()
    outside_file.write_text("secret", encoding="utf-8")

    context = ProjectContext(project_root=project_root)

    with pytest.raises(ValueError, match="Access denied"):
        context.read_file(str(outside_file))

def test_read_file_rejects_nonexistent_file(tmp_path: Path):
    context = ProjectContext(project_root=tmp_path)

    with pytest.raises(FileNotFoundError):
        context.read_file("does_not_exist.txt")            
        