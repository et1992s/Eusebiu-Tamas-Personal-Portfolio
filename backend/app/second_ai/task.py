from uuid import uuid4

from .schemas import Task


class TaskManager:
    def create(self, goal: str) -> Task:
        return Task(
            task_id=str(uuid4()),
            goal=goal,
        )

    def start(self, task: Task) -> Task:
        if task.status != "pending":
            raise ValueError(f"Cannot start task in status: {task.status}")

        task.status = "running"
        return task

    def complete(self, task: Task) -> Task:
        if task.status != "running":
            raise ValueError(f"Cannot complete task in status: {task.status}")

        task.status = "completed"
        return task

    def fail(self, task: Task) -> Task:
        if task.status != "running":
            raise ValueError(f"Cannot fail task in status: {task.status}")

        task.status = "failed"
        return task