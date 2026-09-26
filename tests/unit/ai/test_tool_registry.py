from pathlib import Path

import pytest

from app.ai.tools import ToolRegistry, ToolRisk


def test_list_tools_returns_all_registered_tools():
    registry = ToolRegistry()

    assert registry.list_tools() == [
        "create_file",
        "list_directory",
        "read_file",
        "run_command",
        "search_code",
        "write_file"]

def test_registered_tools_have_expected_risk_levels():
    registry = ToolRegistry()

    assert registry.registry["read_file"]["risk"] == ToolRisk.READ
    assert registry.registry["list_directory"]["risk"] == ToolRisk.READ
    assert registry.registry["search_code"]["risk"] == ToolRisk.READ

    assert registry.registry["write_file"]["risk"] == ToolRisk.LOW_RISK_WRITE
    assert registry.registry["create_file"]["risk"] == ToolRisk.LOW_RISK_WRITE

    assert registry.registry["run_command"]["risk"] == ToolRisk.COMMAND    

def test_ollama_tool_schemas_match_registered_tool_contract():
    registry = ToolRegistry()

    tools = registry.get_ollama_tools()

    assert [tool["function"]["name"] for tool in tools] == [
        "read_file",
        "list_directory",
        "search_code",
        "write_file",
        "create_file",
        "run_command",
    ]

    schemas = {
        tool["function"]["name"]: tool["function"]["parameters"]
        for tool in tools
    }

    assert schemas["read_file"]["required"] == [
        "relative_path",
    ]
    assert set(schemas["read_file"]["properties"]) == {
        "relative_path",
        "start_line",
        "end_line",
    }

    assert "required" not in schemas["list_directory"]
    assert set(schemas["list_directory"]["properties"]) == {
        "relative_path",
    }

    assert schemas["search_code"]["required"] == [
        "query",
    ]
    assert set(schemas["search_code"]["properties"]) == {
        "query",
        "relative_path",
    }

    for tool_name in ("write_file", "create_file"):
        assert schemas[tool_name]["required"] == [
            "relative_path",
            "content",
        ]
        assert set(schemas[tool_name]["properties"]) == {
            "relative_path",
            "content",
        }

    assert schemas["run_command"]["required"] == [
        "command",
    ]
    assert set(schemas["run_command"]["properties"]) == {
        "command",
        "working_directory",
    }

def test_execute_dispatches_to_registered_tool(tmp_path: Path):
    registry = ToolRegistry()
    registry.tools.project_context.project_root = tmp_path

    test_file = tmp_path / "example.txt"
    test_file.write_text("hello zebios", encoding="utf-8")

    result = registry.execute("read_file", {"relative_path": "example.txt"})

    assert result == "hello zebios"

def test_execute_rejects_unknown_tool():
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="Unknown tool"):
        registry.execute("delete_everything", {})

def test_parse_tool_request_parses_valid_json():
    registry = ToolRegistry()

    result = registry.parse_tool_request('{"name": "read_file", "arguments": {"relative_path": "README.md"}}')

    assert result == {"name": "read_file", "arguments": {"relative_path": "README.md"}}

def test_parse_tool_request_parses_json_code_fence():
    registry = ToolRegistry()

    result = registry.parse_tool_request("""```json{"name": "read_file", "arguments": {"relative_path": "README.md"}}```""")

    assert result == {"name": "read_file", "arguments": {"relative_path": "README.md"}}

def test_parse_tool_request_extracts_json_from_normal_text():
    registry = ToolRegistry()

    result = registry.parse_tool_request("""I will inspect the file now. {"name": "read_file", "arguments": {"relative_path": "README.md"}}""")

    assert result == {"name": "read_file", "arguments": {"relative_path": "README.md"}}

def test_parse_tool_request_handles_escaped_tool_name():
    registry = ToolRegistry()

    result = registry.parse_tool_request(r'{"name": "write\_file", "arguments": {"relative_path": "test.txt", "content": "hello"}}')

    assert result == {"name": "write_file", "arguments": {"relative_path": "test.txt", "content": "hello"}}

def test_parse_tool_request_rejects_empty_response():
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="Model response is empty"):
        registry.parse_tool_request("")

def test_parse_tool_request_rejects_response_without_json():
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="does not contain a tool request"):
        registry.parse_tool_request("I will inspect the project now.")

def test_parse_tool_request_rejects_invalid_json():
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="contains invalid tool JSON"):
        registry.parse_tool_request( '{"name": "read_file", "arguments": ')

def test_parse_tool_request_rejects_unknown_tool():
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="Unknown tool"):
        registry.parse_tool_request('{"name": "delete_everything", "arguments": {}}')

def test_parse_tool_request_rejects_non_object_arguments():
    registry = ToolRegistry()

    with pytest.raises(ValueError, match="Tool arguments must be a JSON object"):
        registry.parse_tool_request('{"name": "read_file", "arguments": "README.md"}')        