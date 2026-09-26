from pathlib import Path

import pytest
import subprocess
from unittest.mock import patch

from app.ai.tools import ZebioTools


def create_tools(project_root: Path) -> ZebioTools:
    tools = ZebioTools()
    tools.project_context.project_root = project_root
    return tools


def test_run_command_executes_successfully(tmp_path: Path):
    tools = create_tools(tmp_path)

    result = tools.run_command("python -c \"print('hello zebios')\"")

    assert result["return_code"] == 0
    assert result["stdout"].strip() == "hello zebios"
    assert result["stderr"] == ""
    assert result["timeout"] is False

def test_run_command_uses_working_directory(tmp_path: Path):
    tools = create_tools(tmp_path)

    working_directory = tmp_path / "workspace"
    working_directory.mkdir()

    result = tools.run_command(
        "python -c \"import os; print(os.getcwd())\"",
        working_directory="workspace")

    assert result["return_code"] == 0
    assert (Path(result["stdout"].strip()).resolve() == working_directory.resolve())
    assert result["timeout"] is False

def test_run_command_returns_nonzero_exit_code(tmp_path: Path):
    tools = create_tools(tmp_path)

    result = tools.run_command("python -c \"import sys; print('failure'); sys.exit(3)\"")

    assert result["return_code"] == 3
    assert result["stdout"].strip() == "failure"
    assert result["timeout"] is False

def test_run_command_captures_stderr(tmp_path: Path):
    tools = create_tools(tmp_path)

    result = tools.run_command("python -c \"import sys; print('error', file=sys.stderr)\"")

    assert result["return_code"] == 0
    assert result["stdout"] == ""
    assert result["stderr"].strip() == "error"
    assert result["timeout"] is False

def test_run_command_blocks_long_running_command(tmp_path: Path):
    tools = create_tools(tmp_path)

    result = tools.run_command("uvicorn app.main:app --reload")

    print(result)

    assert result["return_code"] is None
    assert result["stdout"] == ""
    assert result["timeout"] is False
    assert result["blocked"] is True
    assert "Long-running command blocked" in result["stderr"]

def test_run_command_blocks_npm_dev_command(tmp_path: Path):
    tools = create_tools(tmp_path)

    result = tools.run_command("npm run dev")

    assert result["return_code"] is None
    assert result["stdout"] == ""
    assert result["timeout"] is False
    assert result["blocked"] is True
    assert "Long-running command blocked" in result["stderr"]

def test_run_command_rejects_empty_command(tmp_path: Path):
    tools = create_tools(tmp_path)

    with pytest.raises(ValueError, match="Command cannot be empty"):
        tools.run_command("")

def test_run_command_rejects_whitespace_command(tmp_path: Path):
    tools = create_tools(tmp_path)

    with pytest.raises(ValueError, match="Command cannot be empty"):
        tools.run_command("   ")

def test_run_command_rejects_working_directory_outside_project(tmp_path: Path):
    tools = create_tools(tmp_path)

    with pytest.raises(ValueError, match="outside the project"):
        tools.run_command("python -c \"print('should not run')\"", working_directory="..")

def test_run_command_handles_timeout(tmp_path: Path):
    tools = create_tools(tmp_path)

    timeout_error = subprocess.TimeoutExpired(cmd="python -c \"import time; time.sleep(999)\"", timeout=120)

    with patch("app.ai.tools.subprocess.run", side_effect=timeout_error):
        result = tools.run_command("python -c \"import time; time.sleep(999)\"")

    assert result["return_code"] is None
    assert result["stdout"] == ""
    assert result["timeout"] is True
    assert "timed out" in result["stderr"].lower()

def test_run_command_blocks_npm_start_command(tmp_path: Path):
    tools = create_tools(tmp_path)

    result = tools.run_command("npm start")

    assert result["return_code"] is None
    assert result["stdout"] == ""
    assert result["timeout"] is False
    assert result["blocked"] is True
    assert "Long-running command blocked" in result["stderr"]

