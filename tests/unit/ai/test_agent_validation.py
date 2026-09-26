from app.ai.agent import ZebioAgent


def test_run_command_accepts_command():
    error = ZebioAgent._validate_tool_arguments( "run_command", {"command": "pytest"})

    assert error is None

def test_run_command_accepts_working_directory():
    error = ZebioAgent._validate_tool_arguments("run_command", {"command": "pytest", "working_directory": "backend"})

    assert error is None

def test_run_command_requires_command():
    error = ZebioAgent._validate_tool_arguments("run_command", {"working_directory": "backend"})

    assert error is not None
    assert "command" in error

def test_run_command_rejects_unexpected_arguments():
    error = ZebioAgent._validate_tool_arguments("run_command", {"command": "pytest", "invalid_argument": True})

    assert error is not None
    assert "invalid_argument" in error