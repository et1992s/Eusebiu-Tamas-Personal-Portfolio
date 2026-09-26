from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio

from app.ai.agent import ZebioAgent
from app.ai.conversation_store import ConversationStore
from app.ai.prompts import ZEBIO_SYSTEM_PROMPT
from app.ai.project_context import ProjectContext


router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI"],
)

agent = ZebioAgent()

CHAT_HISTORY_FILE = str(
    ProjectContext().project_root / "backend" / "data" / "chat_history.pkl"
)

# Temporary in-memory conversation storage.
# This will later be replaced by proper persistent/project state.
conversation_store = ConversationStore()
conversation_store.load(CHAT_HISTORY_FILE)

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


@router.get("/approvals/{approval_id}")
async def get_approval(approval_id: str):
    try:
        approval = agent.approval_manager.get(approval_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Approval request not found: {approval_id}",
        )

    return {
        "approval_id": approval.approval_id,
        "session_id": approval.session_id,
        "task_id": approval.task_id,
        "step_id": approval.step_id,
        "tool_name": approval.tool_name,
        "arguments": approval.arguments,
        "risk": approval.risk.value,
        "status": approval.status.value,
        "created_at": approval.created_at,
        "resolved_at": approval.resolved_at,
        "resolution": approval.resolution,
        "error": approval.error,
    }


@router.get("/tasks/{task_id}")
async def get_task_state(task_id: str):
    try:
        task = agent.task_manager.get(task_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Task not found: {task_id}",
        )

    steps = agent.task_manager.get_steps(task_id)

    approvals_by_step = {
        approval.step_id: approval
        for approval in agent.approval_manager.get_for_task(task_id)
    }

    return {
        "task_id": task.task_id,
        "session_id": task.session_id,
        "goal": task.goal,
        "status": task.status.value,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
        "current_step": task.current_step,
        "observations": task.observations or [],
        "verification_status": task.verification_status,
        "verification_summary": task.verification_summary,
        "verification_evidence": task.verification_evidence or [],
        "errors": task.errors or [],
        "steps": [
            {
                "step_id": step.step_id,
                "task_id": step.task_id,
                "tool_name": step.tool_name,
                "arguments": step.arguments,
                "status": step.status.value,
                "created_at": step.created_at,
                "updated_at": step.updated_at,
                "completed_at": step.completed_at,
                "error": step.error,
                "approval_id": (
                    approvals_by_step[step.step_id].approval_id
                    if step.step_id in approvals_by_step
                    else None
                ),
                "approval_status": (
                    approvals_by_step[step.step_id].status.value
                    if step.step_id in approvals_by_step
                    else None
                ),
                "risk": (
                    approvals_by_step[step.step_id].risk.value
                    if step.step_id in approvals_by_step
                    else None
                ),
            }
            for step in steps
        ],
    }


@router.post("/approvals/{approval_id}/approve")
async def approve_approval(approval_id: str):
    try:
        approval = agent.approval_manager.approve(approval_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Approval request not found: {approval_id}",
        )

    session_lock = conversation_store.get_lock(approval.session_id)

    with session_lock:
        conversation = conversation_store.conversations.get(
            approval.session_id
        )

        if conversation is None:
            return {
                "approval_id": approval.approval_id,
                "session_id": approval.session_id,
                "task_id": approval.task_id,
                "step_id": approval.step_id,
                "tool_name": approval.tool_name,
                "arguments": approval.arguments,
                "risk": approval.risk.value,
                "status": approval.status.value,
                "created_at": approval.created_at,
                "resolved_at": approval.resolved_at,
                "resolution": approval.resolution,
                "error": approval.error,
            }

        try:
            response = await asyncio.to_thread(
                agent.resume_approved_action,
                approval_id,
                conversation,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )

        conversation.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        conversation_store.save(CHAT_HISTORY_FILE)

    approval = agent.approval_manager.get(approval_id)

    return {
        "approval_id": approval.approval_id,
        "session_id": approval.session_id,
        "task_id": approval.task_id,
        "step_id": approval.step_id,
        "tool_name": approval.tool_name,
        "arguments": approval.arguments,
        "risk": approval.risk.value,
        "status": approval.status.value,
        "created_at": approval.created_at,
        "resolved_at": approval.resolved_at,
        "resolution": approval.resolution,
        "error": approval.error,
        "response": response,
    }

@router.post("/approvals/{approval_id}/reject")
async def reject_approval(approval_id: str):
    try:
        approval = agent.reject_action(approval_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Approval request not found: {approval_id}",
        )

    try:
        agent.task_manager.cancel_task_step(approval.step_id)
        agent.task_manager.cancel(approval.task_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    return {
        "approval_id": approval.approval_id,
        "session_id": approval.session_id,
        "task_id": approval.task_id,
        "step_id": approval.step_id,
        "tool_name": approval.tool_name,
        "arguments": approval.arguments,
        "risk": approval.risk.value,
        "status": approval.status.value,
        "created_at": approval.created_at,
        "resolved_at": approval.resolved_at,
        "resolution": approval.resolution,
        "error": approval.error,
    }

@router.post("/chat")
async def chat_with_ai(request: ChatRequest):
    import time

    total_start = time.perf_counter()

    print(f"[ZEBIO API] Request received: {request.session_id}")

    session_lock = conversation_store.get_lock(request.session_id)

    with session_lock:
        step_start = time.perf_counter()

        conversation = conversation_store.get_or_create(
            request.session_id,
            ZEBIO_SYSTEM_PROMPT,
        )

        print(
            f"[ZEBIO TIMING] session setup: "
            f"{time.perf_counter() - step_start:.3f}s"
        )

        conversation.append(
            {
                "role": "user",
                "content": request.message,
            }
        )

        print(
            f"[ZEBIO TIMING] before agent: "
            f"{time.perf_counter() - total_start:.3f}s"
        )

        agent_start = time.perf_counter()

        task_id = None

        def on_task_created(created_task_id: str) -> None:
            nonlocal task_id
            task_id = created_task_id

        response = await asyncio.to_thread(
            agent.run,
            conversation,
            session_id=request.session_id,
            on_task_created=on_task_created,
        )

        print(
            f"[ZEBIO TIMING] agent: "
            f"{time.perf_counter() - agent_start:.3f}s"
        )

        conversation.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        conversation_store.save(CHAT_HISTORY_FILE)

    result = {
        "status": "success",
        "model": agent.ollama_client.model,
        "session_id": request.session_id,
        "response": response,
        "task_id": task_id,
    }

    print(
        f"[ZEBIO TIMING] TOTAL: "
        f"{time.perf_counter() - total_start:.3f}s"
    )

    return result