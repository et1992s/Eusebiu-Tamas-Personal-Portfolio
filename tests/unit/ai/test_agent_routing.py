from app.ai.agent import ZebioAgent


def test_empty_messages_are_simple_conversation():
    assert ZebioAgent._is_simple_conversation([]) is True


def test_normal_question_is_simple_conversation():
    messages = [
        {"role": "user", "content": "What is Python?"}
    ]

    assert ZebioAgent._is_simple_conversation(messages) is True


def test_read_file_request_is_engineering_task():
    messages = [
        {"role": "user", "content": "Read the file example.txt."}
    ]

    assert ZebioAgent._is_simple_conversation(messages) is False


def test_inspect_project_request_is_engineering_task():
    messages = [
        {"role": "user", "content": "Inspect the project."}
    ]

    assert ZebioAgent._is_simple_conversation(messages) is False


def test_fix_bug_request_is_engineering_task():
    messages = [
        {"role": "user", "content": "Fix this bug."}
    ]

    assert ZebioAgent._is_simple_conversation(messages) is False


def test_run_command_request_is_engineering_task():
    messages = [
        {"role": "user", "content": "Run the command to list the files."}
    ]

    assert ZebioAgent._is_simple_conversation(messages) is False


def test_modify_code_request_is_engineering_task():
    messages = [
        {"role": "user", "content": "Modify this file."}
    ]

    assert ZebioAgent._is_simple_conversation(messages) is False


def test_case_and_whitespace_do_not_change_routing():
    messages = [
        {"role": "user", "content": "  INSPECT THE PROJECT  "}
    ]

    assert ZebioAgent._is_simple_conversation(messages) is False