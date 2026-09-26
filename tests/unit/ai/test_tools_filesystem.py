from pathlib import Path

import pytest

from app.ai.tools import ZebioTools


def create_tools(project_root: Path) -> ZebioTools:
    tools = ZebioTools()
    tools.project_context.project_root = project_root
    return tools


def test_read_file_reads_existing_file(tmp_path: Path):
    tools = create_tools(tmp_path)

    test_file = tmp_path / "example.txt"
    test_file.write_text("hello zebios", encoding="utf-8")

    result = tools.read_file("example.txt")

    assert result == "hello zebios"


def test_read_file_raises_for_missing_file(tmp_path: Path):
    tools = create_tools(tmp_path)

    with pytest.raises(FileNotFoundError, match="File not found"):
        tools.read_file("missing.txt")

def test_read_file_supports_line_ranges(tmp_path: Path):
    tools = create_tools(tmp_path)

    test_file = tmp_path / "example.py"
    test_file.write_text(
        "line one\n"
        "line two\n"
        "line three\n"
        "line four\n",
        encoding="utf-8",
    )

    result = tools.read_file(
        "example.py",
        start_line=2,
        end_line=3,
    )

    assert result == "2: line two\n3: line three"

def test_list_directory_lists_files(tmp_path: Path):
    tools = create_tools(tmp_path)

    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    (tmp_path / "two.txt").write_text("two", encoding="utf-8")

    result = tools.list_directory(".")

    assert result == [
        {"name": "one.txt", "type": "file"},
        {"name": "two.txt", "type": "file"},
    ]

def test_list_directory_identifies_files_and_directories(tmp_path: Path):
    tools = create_tools(tmp_path)

    (tmp_path / "file.txt").write_text("file", encoding="utf-8")
    (tmp_path / "folder").mkdir()

    result = tools.list_directory(".")

    assert result == [
        {"name": "file.txt", "type": "file"},
        {"name": "folder", "type": "directory"},
    ]

def test_list_directory_raises_for_missing_directory(tmp_path: Path):
    tools = create_tools(tmp_path)

    with pytest.raises(NotADirectoryError, match="Directory not found"):
        tools.list_directory("missing")


def test_create_file_creates_file(tmp_path: Path):
    tools = create_tools(tmp_path)

    result = tools.create_file("new_file.txt", "created by Zebios")
    
    assert result == "Created new_file.txt"
    assert (tmp_path / "new_file.txt").read_text(encoding="utf-8") == "created by Zebios"

def test_create_file_raises_if_file_exists(tmp_path: Path):
    tools = create_tools(tmp_path)

    existing_file = tmp_path / "existing.txt"
    existing_file.write_text(
        "original",
        encoding="utf-8")

    with pytest.raises(
        FileExistsError,
        match="File already exists"):
        tools.create_file(
            "existing.txt",
            "replacement")

def test_write_file_updates_existing_file(tmp_path: Path):
    tools = create_tools(tmp_path)

    test_file = tmp_path / "example.txt"
    test_file.write_text("original", encoding="utf-8")

    result = tools.write_file("example.txt", "updated")

    assert result == "Updated example.txt"
    assert test_file.read_text(encoding="utf-8") == "updated"


def test_write_file_raises_for_missing_file(tmp_path: Path):
    tools = create_tools(tmp_path)

    with pytest.raises(
        FileNotFoundError,
        match="File does not exist"):
        tools.write_file(
            "missing.txt",
            "content")


def test_search_code_finds_matching_text(tmp_path: Path):
    tools = create_tools(tmp_path)

    source_file = tmp_path / "example.py"
    source_file.write_text(
        "def calculate_profit():\n"
        "    return 42\n",
        encoding="utf-8")

    result = tools.search_code("calculate_profit")

    assert result == [
        {
            "file": "example.py",
            "line": 1,
            "content": "def calculate_profit():",
        }
    ]


def test_search_code_is_case_insensitive(tmp_path: Path):
    tools = create_tools(tmp_path)

    source_file = tmp_path / "example.py"
    source_file.write_text(
        "def Calculate_Profit():\n"
        "    return 42\n",
        encoding="utf-8")

    result = tools.search_code("calculate_profit")

    assert len(result) == 1
    assert result[0]["file"] == "example.py"
    assert result[0]["line"] == 1


def test_search_code_rejects_empty_query(tmp_path: Path,):
    tools = create_tools(tmp_path)

    with pytest.raises(
        ValueError,
        match="Search query cannot be empty"):
        tools.search_code("")


def test_search_code_rejects_whitespace_query(tmp_path: Path,):
    tools = create_tools(tmp_path)

    with pytest.raises(
        ValueError,
        match="Search query cannot be empty"):
        tools.search_code("   ")