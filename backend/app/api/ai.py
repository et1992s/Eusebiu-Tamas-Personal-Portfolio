import asyncio
import json
import os
import threading
import time
from pathlib import Path

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.ai.agent import ZebioAgent
from app.ai.conversation_store import ConversationStore
from app.ai.memory import MemoryStore
from app.ai.prompts import (
    PORTFOLIO_ABOUT_CONTEXT,
    PORTFOLIO_ABOUT_SYSTEM_PROMPT,
    ZEBIO_SYSTEM_PROMPT,
)
from app.ai.project_context import ProjectContext


router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI"],
)


# ---------------------------------------------------------------------------
# Core AI/runtime services
# ---------------------------------------------------------------------------

agent = ZebioAgent()

PROJECT_ROOT = ProjectContext().project_root

MEMORY_DB_FILE = Path(
    os.environ.get(
        "ZEBIO_MEMORY_DB",
        str(PROJECT_ROOT / "backend" / "data" / "zebio.db"),
    )
)

MEMORY_DB_WAS_EXISTING = MEMORY_DB_FILE.exists()

memory_store = MemoryStore(MEMORY_DB_FILE)


# ---------------------------------------------------------------------------
# Runtime conversation cache
# ---------------------------------------------------------------------------
#
# ConversationStore owns in-process conversations and session locks.
# MemoryStore owns durable persistence.
#
# The agent receives a plain list[dict] conversation. It is not
# responsible for persistence.
#

conversation_store = ConversationStore()


# ---------------------------------------------------------------------------
# Legacy pickle migration
# ---------------------------------------------------------------------------

LEGACY_CHAT_HISTORY_FILE = (
    PROJECT_ROOT / "backend" / "data" / "chat_history.pkl"
)


def _migrate_legacy_chat_history() -> None:
    """
    One-time migration from the old pickle conversation store.

    The legacy pickle is only read when the new SQLite database does
    not yet exist. Once SQLite exists, pickle is no longer part of
    normal operation.
    """
    if MEMORY_DB_WAS_EXISTING:
        return

    if not LEGACY_CHAT_HISTORY_FILE.exists():
        return

    print(
        "[ZEBIO MEMORY] Migrating legacy chat history "
        f"from {LEGACY_CHAT_HISTORY_FILE}"
    )

    legacy_store = ConversationStore()

    try:
        legacy_conversations = legacy_store.load(
            str(LEGACY_CHAT_HISTORY_FILE)
        )
    except Exception as exc:
        print(
            f"[ZEBIO MEMORY] Legacy migration failed: {exc}"
        )
        return

    migrated = 0

    for session_id, messages in legacy_conversations.items():
        if not isinstance(messages, list):
            continue

        try:
            memory_store.replace_conversation(
                session_id,
                messages,
            )
            migrated += 1
        except Exception as exc:
            print(
                "[ZEBIO MEMORY] Failed to migrate session "
                f"{session_id}: {exc}"
            )

    print(
        "[ZEBIO MEMORY] Legacy migration complete: "
        f"{migrated} session(s)"
    )


_migrate_legacy_chat_history()


# ---------------------------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------------------------

def _get_conversation(session_id: str) -> list[dict[str, str]]:
    """
    Return the runtime conversation for a session.

    Loading order:
        1. in-memory runtime cache
        2. SQLite persistent storage
        3. new system-prompt conversation
    """
    conversation = conversation_store.conversations.get(session_id)

    if conversation is not None:
        return conversation

    persisted = memory_store.get_conversation(session_id)

    if persisted:
        conversation_store.conversations[session_id] = persisted
        return persisted

    return conversation_store.get_or_create(
        session_id,
        ZEBIO_SYSTEM_PROMPT,
    )


def _persist_conversation(
    session_id: str,
    conversation: list[dict[str, str]],
) -> None:
    """Persist the complete current conversation to SQLite."""
    memory_store.replace_conversation(
        session_id,
        conversation,
    )


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


# ---------------------------------------------------------------------------
# Task serialization
# ---------------------------------------------------------------------------

def _serialize_task_snapshot(
    task,
    steps,
    approvals_by_step,
) -> dict:
    """
    Build a JSON-safe snapshot of task state.

    Used by both the JSON endpoint and the SSE `snapshot` / `done`
    frames so the client sees an identical shape in both paths.
    """
    return {
        "task_id": task.task_id,
        "session_id": task.session_id,
        "goal": task.goal,
        "status": task.status.value,
        "created_at": (
            task.created_at.isoformat() if task.created_at else None
        ),
        "updated_at": (
            task.updated_at.isoformat() if task.updated_at else None
        ),
        "completed_at": (
            task.completed_at.isoformat() if task.completed_at else None
        ),
        "current_step": task.current_step,
        "current_thought": task.current_thought,
        "final_response": task.final_response,
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
                "created_at": (
                    step.created_at.isoformat()
                    if step.created_at
                    else None
                ),
                "updated_at": (
                    step.updated_at.isoformat()
                    if step.updated_at
                    else None
                ),
                "completed_at": (
                    step.completed_at.isoformat()
                    if step.completed_at
                    else None
                ),
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


def _snapshot_for_task(task_id: str) -> dict:
    """Convenience wrapper used by the JSON and stream endpoints."""
    task = agent.task_manager.get(task_id)
    steps = agent.task_manager.get_steps(task_id)
    approvals_by_step = {
        approval.step_id: approval
        for approval in agent.approval_manager.get_for_task(task_id)
    }

    return _serialize_task_snapshot(
        task,
        steps,
        approvals_by_step,
    )


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

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
        conversation = _get_conversation(approval.session_id)

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

        _persist_conversation(
            approval.session_id,
            conversation,
        )

    approval = agent.approval_manager.get(approval_id)

    agent.task_manager.publish_event(
        approval.task_id,
        "step",
        {
            "step_id": approval.step_id,
            "approval_status": "approved",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
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
        agent.task_manager.publish_event(
            approval.task_id,
            "step",
            {
                "step_id": approval.step_id,
                "approval_status": "rejected",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
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


# ---------------------------------------------------------------------------
# Task snapshot
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}")
async def get_task_state(task_id: str):
    try:
        return _snapshot_for_task(task_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Task not found: {task_id}",
        )


# ---------------------------------------------------------------------------
# Task streaming
# ---------------------------------------------------------------------------

@router.get("/tasks/{task_id}/stream")
async def stream_task(task_id: str):
    """
    Server-Sent Events stream of task state changes.

    Frames:

        event: snapshot          once on connect, full task state
        event: status            task status transitions
        event: thought           model's current reasoning
        event: current_step      agent's current step label
        event: step              step created / started / completed
        event: observation       tool result recorded
        event: verification      verification state change
        event: final_response    assistant's final reply
        event: done              terminal snapshot; stream closes

    The stream emits a fresh snapshot on connect, then tails the
    per-task event log. Reconnects are safe: the client receives the
    snapshot again and starts tailing from the current sequence.
    """
    try:
        agent.task_manager.get(task_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Task not found: {task_id}",
        )

    TERMINAL_STATUSES = {"completed", "failed", "cancelled"}

    async def event_generator():
        # 1. Initial snapshot.
        snapshot = _snapshot_for_task(task_id)
        yield f"event: snapshot\ndata: {json.dumps(snapshot)}\n\n"

        # 2. Tail new events only. Everything before now was
        # already included in the snapshot.
        last_seq = agent.task_manager.get_max_seq(task_id)
        keepalive_counter = 0

        while True:
            events = agent.task_manager.get_events_since(
                task_id,
                last_seq,
            )

            for event in events:
                last_seq = event["seq"]

                yield (
                    f"event: {event['type']}\n"
                    f"data: {json.dumps(event['data'])}\n\n"
                )

                keepalive_counter = 0

            try:
                current = agent.task_manager.get(task_id)
                is_terminal = (
                    current.status.value in TERMINAL_STATUSES
                )
            except KeyError:
                # Task was removed while streaming. Terminate.
                return

            if is_terminal:
                # Drain any events published between the last read
                # and the terminal status check.
                for event in agent.task_manager.get_events_since(
                    task_id,
                    last_seq,
                ):
                    last_seq = event["seq"]

                    yield (
                        f"event: {event['type']}\n"
                        f"data: {json.dumps(event['data'])}\n\n"
                    )

                final_snapshot = _snapshot_for_task(task_id)

                yield (
                    "event: done\n"
                    f"data: {json.dumps(final_snapshot)}\n\n"
                )

                return

            keepalive_counter += 1

            if keepalive_counter >= 150:  # ~15 s at 100 ms tick
                yield ": keepalive\n\n"
                keepalive_counter = 0

            await asyncio.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@router.get("/model")
async def get_model():
    return {"model": agent.ollama_client.model}

# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@router.post("/chat")
async def chat_with_ai(request: ChatRequest):
    """
    Entry point for user messages.

    Routing:

        Simple conversation
            -> run inline, return the reply and a null task_id.

        Engineering request
            -> create the task synchronously, return the task_id
               immediately, then run the agent loop in a background
               thread. The client subscribes to
               /tasks/{task_id}/stream for live updates.
    """
    total_start = time.perf_counter()

    print(
        f"[ZEBIO API] Request received: {request.session_id}"
    )

    session_lock = conversation_store.get_lock(request.session_id)

    with session_lock:
        conversation = _get_conversation(request.session_id)

        conversation.append(
            {
                "role": "user",
                "content": request.message,
            }
        )

        _persist_conversation(request.session_id, conversation)

        is_engineering = agent.is_engineering_request(conversation)

        if not is_engineering:
            # -------------------------------------------------------
            # Simple conversation: run inline.
            # -------------------------------------------------------
            print("[ZEBIO API] Simple conversation — inline")

            try:
                response = await asyncio.to_thread(
                    agent._run_conversation,
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

            _persist_conversation(request.session_id, conversation)

            return {
                "status": "success",
                "model": agent.ollama_client.model,
                "session_id": request.session_id,
                "response": response,
                "task_id": None,
            }

        # -----------------------------------------------------------
        # Engineering: create the task now, hand its ID back, then
        # run the loop in a background thread.
        # -----------------------------------------------------------
        task_id = agent.create_task_for(
            conversation,
            request.session_id,
        )

        print(
            f"[ZEBIO API] Engineering task created: {task_id}"
        )

    def _run_task_in_background() -> None:
        """Run the loop and finalise conversation state."""
        try:
            response = agent.execute_task(
                task_id=task_id,
                messages=conversation,
                session_id=request.session_id,
            )
        except Exception as exc:
            print(
                f"[ZEBIO API] Background task failed: "
                f"{type(exc).__name__}: {exc}"
            )

            try:
                agent.task_manager.fail(task_id, str(exc))
            except (KeyError, ValueError):
                pass

            return

        # Record the assistant reply on the task so the SSE stream
        # can deliver it via the `final_response` / `done` frames.
        try:
            agent.task_manager.set_final_response(task_id, response)
        except (KeyError, ValueError) as exc:
            print(
                f"[ZEBIO API] Could not set final response: {exc}"
            )

        # Append the assistant reply to the persisted conversation.
        with session_lock:
            current = _get_conversation(request.session_id)
            current.append(
                {
                    "role": "assistant",
                    "content": response,
                }
            )
            _persist_conversation(request.session_id, current)

        print(
            f"[ZEBIO API] Background task finished in "
            f"{time.perf_counter() - total_start:.3f}s"
        )

    threading.Thread(
        target=_run_task_in_background,
        daemon=True,
    ).start()

    return {
        "status": "accepted",
        "model": agent.ollama_client.model,
        "session_id": request.session_id,
        "response": None,
        "task_id": task_id,
    }

class PortfolioAboutRequest(BaseModel):
    message: str


@router.post("/about/stream")
async def stream_portfolio_about(request: PortfolioAboutRequest):
    """
    Stream a portfolio-facing response from Zebio.

    This endpoint is intentionally separate from the engineering assistant.
    It uses dedicated portfolio instructions and authoritative Eusebiu
    context, with no engineering tools or task execution.
    """
    if not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty.",
        )

    messages = [
        {
            "role": "system",
            "content": (
                f"{PORTFOLIO_ABOUT_SYSTEM_PROMPT}\n\n"
                "AUTHORITATIVE PORTFOLIO CONTEXT:\n"
                f"{PORTFOLIO_ABOUT_CONTEXT}"
            ),
        },
        {
            "role": "user",
            "content": request.message.strip(),
        },
    ]

    async def event_generator():
        try:
            for chunk in agent.ollama_client.chat_stream(messages):
                yield (
                    "event: token\n"
                    f"data: {json.dumps({'content': chunk})}\n\n"
                )

            yield "event: done\ndata: {}\n\n"

        except Exception as exc:
            print(
                "[ZEBIO API] Portfolio stream failed: "
                f"{type(exc).__name__}: {exc}"
            )

            yield (
                "event: error\n"
                f"data: {json.dumps({'error': str(exc)})}\n\n"
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )