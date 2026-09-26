from pathlib import Path

import pytest

from app.ai.tools import ZebioTools

def test_resolve_path_accepts_path_inside_project(tmp_path: Path):
    tools = ZebioTools()
    tools.project_context.project_root = tmp_path

    test_file = tmp_path / "example.txt"
    test_file.write_text("hello zebios", encoding="utf-8")

    result = tools._resolve_path("example.txt")

    assert result == test_file.resolve()

def test_resolve_path_accepts_nested_path_inside_project(tmp_path: Path):
    tools = ZebioTools()
    tools.project_context.project_root = tmp_path

    nested_directory = tmp_path / "backend" / "app"
    nested_directory.mkdir(parents=True)

    result = tools._resolve_path("backend/app")

    assert result == nested_directory.resolve()

def test_resolve_path_rejects_parent_directory_traversal(tmp_path: Path):
    tools = ZebioTools()
    tools.project_context.project_root = tmp_path / "project"
    tools.project_context.project_root.mkdir()

    outside_file = tmp_path /"outside.txt"
    outside_file.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="outside the project"):
        tools._resolve_path(str(outside_file))

def test_read_file_limits_large_full_file_read(tmp_path: Path):
    tools = ZebioTools()
    tools.project_context.project_root = tmp_path

    test_file = tmp_path / "large.txt"
    test_file.write_text(
        "\n".join(f"line {number}" for number in range(1, 301)),
        encoding="utf-8",
    )

    result = tools.read_file("large.txt")

    lines = result.splitlines()

    assert len(lines) == 200
    assert lines[0] == "1: line 1"
    assert lines[-1] == "200: line 200"


def test_read_file_preserves_explicit_line_range(tmp_path: Path):
    tools = ZebioTools()
    tools.project_context.project_root = tmp_path

    test_file = tmp_path / "large.txt"
    test_file.write_text(
        "\n".join(f"line {number}" for number in range(1, 301)),
        encoding="utf-8",
    )

    result = tools.read_file(
        "large.txt",
        start_line=250,
        end_line=255,
    )

    assert result.splitlines() == [
        "250: line 250",
        "251: line 251",
        "252: line 252",
        "253: line 253",
        "254: line 254",
        "255: line 255",
    ]