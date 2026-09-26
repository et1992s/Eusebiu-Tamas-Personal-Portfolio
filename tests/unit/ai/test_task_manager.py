from datetime import datetime, timezone
import pytest

from app.ai.task_manager import (Task, TaskManager, TaskStatus, TaskStepStatus)


def test_task_status_values():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.COMPLETED.value == "completed"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.CANCELLED.value == "cancelled"


def test_task_can_represent_initial_state():
    task = Task(
        task_id="task-1",
        session_id="session-1",
        goal="Inspect the project",
        status=TaskStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    assert task.task_id == "task-1"
    assert task.session_id == "session-1"
    assert task.goal == "Inspect the project"
    assert task.status == TaskStatus.PENDING
    assert task.completed_at is None
    assert task.current_step is None
    assert task.observations is None
    assert task.errors is None

def test_task_manager_creates_pending_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    assert task.task_id
    assert task.session_id == "session-1"
    assert task.goal == "Inspect the project"
    assert task.status == TaskStatus.PENDING
    assert task.created_at.tzinfo == timezone.utc
    assert task.updated_at.tzinfo == timezone.utc
    assert task.completed_at is None
    assert manager.tasks[task.task_id] is task    

def test_task_manager_get_returns_existing_task():
    manager = TaskManager()

    created = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    retrieved = manager.get(created.task_id)

    assert retrieved is created

def test_task_manager_get_rejects_unknown_task():
    manager = TaskManager()

    with pytest.raises(KeyError, match="Unknown task: missing-task"):
        manager.get("missing-task")

def test_task_manager_starts_pending_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    updated = manager.start(task.task_id)

    assert updated is task
    assert task.status == TaskStatus.RUNNING
    assert task.updated_at >= task.created_at     

def test_task_manager_cannot_start_non_pending_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    manager.start(task.task_id)

    with pytest.raises(
        ValueError,
        match="Cannot start task in state: running",
    ):
        manager.start(task.task_id)   

def test_task_manager_completes_running_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    manager.start(task.task_id)

    manager.set_verification(
        task.task_id,
        "succeeded",
        "Verified during test",
        [{"test": "evidence"}],
    )

    updated = manager.complete(task.task_id)

    assert updated is task
    assert task.status == TaskStatus.COMPLETED
    assert task.completed_at is not None
    assert task.updated_at == task.completed_at

def test_task_manager_cannot_complete_non_running_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    with pytest.raises(
        ValueError,
        match="Cannot complete task in state: pending",
    ):
        manager.complete(task.task_id)

def test_task_manager_fails_running_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    manager.start(task.task_id)

    updated = manager.fail(
        task.task_id,
        error="Tool execution failed",
    )

    assert updated is task
    assert task.status == TaskStatus.FAILED
    assert task.errors == ["Tool execution failed"]
    assert task.completed_at is None

def test_task_manager_cannot_fail_non_running_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    with pytest.raises(
        ValueError,
        match="Cannot fail task in state: pending",
    ):
        manager.fail(
            task.task_id,
            error="Tool execution failed",
        )

def test_task_manager_cancels_pending_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    updated = manager.cancel(task.task_id)

    assert updated is task
    assert task.status == TaskStatus.CANCELLED
    assert task.completed_at is None

def test_task_manager_cancels_running_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    manager.start(task.task_id)

    updated = manager.cancel(task.task_id)

    assert updated is task
    assert task.status == TaskStatus.CANCELLED
    assert task.completed_at is None

def test_task_manager_cannot_cancel_completed_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    manager.start(task.task_id)

    manager.set_verification(
        task.task_id,
        "succeeded",
        "Verified during test",
        [{"test": "evidence"}],
    )

    manager.complete(task.task_id)

    with pytest.raises(
        ValueError,
        match="Cannot cancel task in state: completed",
    ):
        manager.cancel(task.task_id)

def test_task_manager_sets_current_step():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    manager.start(task.task_id)

    updated = manager.set_current_step(
        task.task_id,
        "Inspect project structure",
    )

    assert updated is task
    assert task.current_step == "Inspect project structure"

def test_task_manager_cannot_set_step_for_non_running_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    with pytest.raises(
        ValueError,
        match="Cannot update step for task in state: pending",
    ):
        manager.set_current_step(
            task.task_id,
            "Inspect project structure",
        )

def test_task_manager_adds_observation():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    manager.start(task.task_id)

    observation = {
        "type": "observation",
        "tool": "read_file",
        "arguments": {
            "path": "agent.py",
        },
        "result": {
            "content": "agent.py contents",
        },
    }

    updated = manager.add_observation(
        task.task_id,
        observation,
    )

    assert updated is task
    assert task.observations is not None
    assert len(task.observations) == 1

    stored_observation = task.observations[0]

    assert stored_observation["type"] == observation["type"]
    assert stored_observation["tool"] == observation["tool"]
    assert stored_observation["arguments"] == observation["arguments"]
    assert stored_observation["result"] == observation["result"]

def test_task_manager_cannot_add_observation_for_non_running_task():
    manager = TaskManager()

    task = manager.create(
        session_id="session-1",
        goal="Inspect the project",
    )

    observation = {
        "type": "observation",
        "tool": "read_file",
        "arguments": {
            "path": "agent.py",
        },
        "result": {
            "content": "agent.py contents",
        },
    }

    with pytest.raises(
        ValueError,
        match="Cannot add observation for task in state: pending",
    ):
        manager.add_observation(
            task.task_id,
            observation,
        )

def test_task_manager_concurrent_creation():
    import threading

    manager = TaskManager()
    created_tasks = []

    def create_task():
        task = manager.create(
            session_id="session-1",
            goal="Concurrent task",
        )
        created_tasks.append(task)

    threads = [
        threading.Thread(target=create_task)
        for _ in range(20)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert len(created_tasks) == 20
    assert len(manager.tasks) == 20
    assert len({task.task_id for task in created_tasks}) == 20

def test_task_step_can_represent_initial_state():
    from app.ai.task_manager import TaskStep, TaskStepStatus

    step = TaskStep(
        step_id="step-1",
        task_id="task-1",
        tool_name="read_file",
        arguments={"relative_path": "backend/app/ai/agent.py"},
        status=TaskStepStatus.PENDING,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    assert step.step_id == "step-1"
    assert step.task_id == "task-1"
    assert step.tool_name == "read_file"
    assert step.arguments == {
        "relative_path": "backend/app/ai/agent.py"
    }
    assert step.status == TaskStepStatus.PENDING
    assert step.completed_at is None
    assert step.error is None


def test_task_step_status_values():
    from app.ai.task_manager import TaskStepStatus

    assert TaskStepStatus.PENDING.value == "pending"
    assert TaskStepStatus.RUNNING.value == "running"
    assert TaskStepStatus.COMPLETED.value == "completed"
    assert TaskStepStatus.FAILED.value == "failed"
    assert TaskStepStatus.CANCELLED.value == "cancelled"    

def test_task_manager_creates_pending_task_step():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py"
        },
    )

    assert step.task_id == task.task_id
    assert step.tool_name == "read_file"
    assert step.arguments == {
        "relative_path": "backend/app/ai/agent.py"
    }
    assert step.status == TaskStepStatus.PENDING
    assert step.completed_at is None
    assert step.error is None
    assert step.step_id


def test_task_manager_get_step_returns_existing_step():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py"
        },
    )

    retrieved = manager.get_step(step.step_id)

    assert retrieved is step    

def test_task_manager_get_steps_returns_steps_for_task_in_creation_order():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    first_step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py"
        },
    )

    second_step = manager.create_step(
        task_id=task.task_id,
        tool_name="search_code",
        arguments={
            "query": "TaskManager",
        },
    )

    steps = manager.get_steps(task.task_id)

    assert steps == [first_step, second_step]
    assert steps[0].step_id == first_step.step_id
    assert steps[1].step_id == second_step.step_id

def test_task_manager_get_steps_rejects_unknown_task():
    manager = TaskManager()

    with pytest.raises(
        KeyError,
        match="Unknown task: missing-task",
    ):
        manager.get_steps("missing-task")

def test_task_manager_starts_pending_task_step():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py"
        },
    )

    updated_step = manager.start_step(step.step_id)

    assert updated_step.status == TaskStepStatus.RUNNING
    assert updated_step.updated_at >= updated_step.created_at
    assert updated_step.completed_at is None
    assert updated_step.error is None    

def test_task_manager_completes_running_task_step():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py"
        },
    )

    manager.start_step(step.step_id)

    updated_step = manager.complete_task_step(step.step_id)

    assert updated_step.status == TaskStepStatus.COMPLETED
    assert updated_step.completed_at is not None
    assert updated_step.updated_at >= updated_step.created_at
    assert updated_step.error is None    

def test_task_manager_fails_running_task_step():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/missing.py"
        },
    )

    manager.start_step(step.step_id)

    updated_step = manager.fail_task_step(
        step.step_id,
        "File does not exist.",
    )

    assert updated_step.status == TaskStepStatus.FAILED
    assert updated_step.error == "File does not exist."
    assert updated_step.completed_at is None
    assert updated_step.updated_at >= updated_step.created_at  

def test_task_manager_cancels_task_step():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py"
        },
    )

    manager.start_step(step.step_id)

    updated_step = manager.cancel_task_step(step.step_id)

    assert updated_step.status == TaskStepStatus.CANCELLED
    assert updated_step.completed_at is None
    assert updated_step.error is None
    assert updated_step.updated_at >= updated_step.created_at    

def test_task_manager_cannot_cancel_completed_task_step():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py"
        },
    )

    manager.start_step(step.step_id)
    manager.complete_task_step(step.step_id)

    with pytest.raises(ValueError, match="Cannot cancel task step"):
        manager.cancel_task_step(step.step_id)      

def test_task_manager_cannot_fail_completed_task_step():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py"
        },
    )

    manager.start_step(step.step_id)
    manager.complete_task_step(step.step_id)

    with pytest.raises(ValueError, match="Cannot fail task step"):
        manager.fail_task_step(step.step_id, "Late failure.")

def test_task_manager_cannot_complete_failed_task_step():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/missing.py"
        },
    )

    manager.start_step(step.step_id)
    manager.fail_task_step(step.step_id, "File does not exist.")

    with pytest.raises(ValueError, match="Cannot complete task step"):
        manager.complete_task_step(step.step_id)         

def test_task_manager_rejects_unknown_task_step():
    manager = TaskManager()

    with pytest.raises(KeyError, match="Unknown task step"):
        manager.start_step("missing-step")

    with pytest.raises(KeyError, match="Unknown task step"):
        manager.complete_task_step("missing-step")

    with pytest.raises(KeyError, match="Unknown task step"):
        manager.fail_task_step(
            "missing-step",
            "Test error.",
        )

    with pytest.raises(KeyError, match="Unknown task step"):
        manager.cancel_task_step("missing-step")               

def test_task_manager_copies_task_step_arguments():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )

    arguments = {
        "relative_path": "backend/app/ai/agent.py",
    }

    step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments=arguments,
    )

    arguments["relative_path"] = "backend/app/ai/modified.py"

    assert step.arguments == {
        "relative_path": "backend/app/ai/agent.py",
    }        

def test_task_step_is_authoritative_for_concrete_tool_execution():
    manager = TaskManager()

    task = manager.create(
        session_id="step-test",
        goal="Inspect the project.",
    )
    manager.start(task.task_id)

    first_step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/agent.py"
        },
    )

    second_step = manager.create_step(
        task_id=task.task_id,
        tool_name="read_file",
        arguments={
            "relative_path": "backend/app/ai/task_manager.py"
        },
    )

    manager.start_step(first_step.step_id)
    manager.complete_task_step(first_step.step_id)

    manager.start_step(second_step.step_id)

    assert first_step.status == TaskStepStatus.COMPLETED
    assert second_step.status == TaskStepStatus.RUNNING

    assert first_step.step_id != second_step.step_id
    assert first_step.tool_name == second_step.tool_name
    assert first_step.arguments != second_step.arguments    