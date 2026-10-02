from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id, id);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    status TEXT NOT NULL,
    requires_verification INTEGER NOT NULL DEFAULT 0,
    plan_json TEXT,
    verification_status TEXT,
    verification_summary TEXT,
    verification_evidence_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    current_step TEXT,
    errors_json TEXT
);

CREATE TABLE IF NOT EXISTS task_steps (
    step_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_steps_task ON task_steps(task_id);

CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_id TEXT,
    tool TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    purpose TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_obs_task ON observations(task_id, created_at);

CREATE TABLE IF NOT EXISTS engineering_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eng_task ON engineering_messages(task_id, seq);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    tool_call_id TEXT,
    risk TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolution TEXT,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_appr_task ON approvals(task_id);

CREATE TABLE IF NOT EXISTS projects (
    name TEXT PRIMARY KEY,
    root TEXT NOT NULL,
    ingested_at TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    path TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    content TEXT NOT NULL,
    embedding_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_project ON chunks(project);

CREATE TABLE IF NOT EXISTS loop_state (
    task_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _j(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _jd(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


class MemoryStore:
    """SQLite-backed long-term memory for Zebio."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._lock, self._conn() as conn:
            conn.executescript(SCHEMA)

    # --- conversations -------------------------------------------------

    def append_conversation(self, session_id: str, message: dict[str, Any]) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO conversations(session_id, payload_json, created_at) "
                "VALUES(?,?,?)",
                (session_id, _j(message), _now()),
            )

    def get_conversation(self, session_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM conversations WHERE session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    def replace_conversation(self, session_id: str, messages: Iterable[dict[str, Any]]) -> None:
        with self._lock, self._conn() as conn:
            conn.execute("DELETE FROM conversations WHERE session_id=?", (session_id,))
            for m in messages:
                conn.execute(
                    "INSERT INTO conversations(session_id, payload_json, created_at) "
                    "VALUES(?,?,?)",
                    (session_id, _j(m), _now()),
                )

    # --- tasks ---------------------------------------------------------

    def save_task(self, task: dict[str, Any]) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO tasks(
                    task_id, session_id, goal, status, requires_verification,
                    plan_json, verification_status, verification_summary,
                    verification_evidence_json, created_at, updated_at,
                    completed_at, current_step, errors_json
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status=excluded.status,
                    plan_json=excluded.plan_json,
                    verification_status=excluded.verification_status,
                    verification_summary=excluded.verification_summary,
                    verification_evidence_json=excluded.verification_evidence_json,
                    updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at,
                    current_step=excluded.current_step,
                    errors_json=excluded.errors_json
                """,
                (
                    task["task_id"], task["session_id"], task["goal"], task["status"],
                    1 if task.get("requires_verification") else 0,
                    _j(task.get("plan")) if task.get("plan") is not None else None,
                    task.get("verification_status"),
                    task.get("verification_summary"),
                    _j(task.get("verification_evidence")) if task.get("verification_evidence") is not None else None,
                    task["created_at"], task["updated_at"],
                    task.get("completed_at"), task.get("current_step"),
                    _j(task.get("errors")) if task.get("errors") is not None else None,
                ),
            )

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            return None
        return {
            "task_id": row["task_id"],
            "session_id": row["session_id"],
            "goal": row["goal"],
            "status": row["status"],
            "requires_verification": bool(row["requires_verification"]),
            "plan": _jd(row["plan_json"]),
            "verification_status": row["verification_status"],
            "verification_summary": row["verification_summary"],
            "verification_evidence": _jd(row["verification_evidence_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
            "current_step": row["current_step"],
            "errors": _jd(row["errors_json"]),
        }

    def find_resumable_task(self, session_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE session_id=? AND status='running' "
                "ORDER BY updated_at DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return self.get_task(row["task_id"])

    # --- observations --------------------------------------------------

    def append_observation(self, task_id: str, step_id: str | None,
                           tool: str, arguments: dict, result: Any,
                           purpose: str | None = None) -> str:
        obs_id = str(uuid4())
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO observations(observation_id, task_id, step_id, tool, "
                "arguments_json, result_json, purpose, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (obs_id, task_id, step_id, tool, _j(arguments), _j(result), purpose, _now()),
            )
        return obs_id

    def get_observations(self, task_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM observations WHERE task_id=? ORDER BY created_at",
                (task_id,),
            ).fetchall()
        return [
            {
                "observation_id": r["observation_id"],
                "task_id": r["task_id"],
                "step_id": r["step_id"],
                "tool": r["tool"],
                "arguments": _jd(r["arguments_json"]),
                "result": _jd(r["result_json"]),
                "purpose": r["purpose"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # --- engineering messages ------------------------------------------

    def append_engineering_message(self, task_id: str, seq: int, message: dict[str, Any]) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO engineering_messages(task_id, seq, payload_json, created_at) "
                "VALUES(?,?,?,?)",
                (task_id, seq, _j(message), _now()),
            )

    def get_engineering_messages(self, task_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM engineering_messages WHERE task_id=? ORDER BY seq",
                (task_id,),
            ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    # --- loop state ----------------------------------------------------

    def save_loop_state(self, task_id: str, state: dict[str, Any]) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO loop_state(task_id, state_json, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(task_id) DO UPDATE SET state_json=excluded.state_json, "
                "updated_at=excluded.updated_at",
                (task_id, _j(state), _now()),
            )

    def get_loop_state(self, task_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT state_json FROM loop_state WHERE task_id=?", (task_id,)
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["state_json"])

    # --- approvals -----------------------------------------------------

    def save_approval(self, req: dict[str, Any]) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO approvals(approval_id, session_id, task_id, step_id, tool_name,
                    arguments_json, tool_call_id, risk, status, created_at, resolved_at,
                    resolution, error)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(approval_id) DO UPDATE SET
                    status=excluded.status,
                    resolved_at=excluded.resolved_at,
                    resolution=excluded.resolution,
                    error=excluded.error
                """,
                (
                    req["approval_id"], req["session_id"], req["task_id"], req["step_id"],
                    req["tool_name"], _j(req["arguments"]), req.get("tool_call_id"),
                    req["risk"], req["status"], req["created_at"],
                    req.get("resolved_at"), req.get("resolution"), req.get("error"),
                ),
            )

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "approval_id": row["approval_id"],
            "session_id": row["session_id"],
            "task_id": row["task_id"],
            "step_id": row["step_id"],
            "tool_name": row["tool_name"],
            "arguments": _jd(row["arguments_json"]),
            "tool_call_id": row["tool_call_id"],
            "risk": row["risk"],
            "status": row["status"],
            "created_at": row["created_at"],
            "resolved_at": row["resolved_at"],
            "resolution": row["resolution"],
            "error": row["error"],
        }

    def save_step(self, step: dict[str, Any]) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                INSERT INTO task_steps(
                    step_id, task_id, tool_name, arguments_json, status,
                    created_at, updated_at, completed_at, error
                ) VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(step_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    completed_at=excluded.completed_at,
                    error=excluded.error
                """,
                (
                    step["step_id"], step["task_id"], step["tool_name"],
                    _j(step["arguments"]), step["status"],
                    step["created_at"], step["updated_at"],
                    step.get("completed_at"), step.get("error"),
                ),
            )

    def get_steps(self, task_id: str) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM task_steps WHERE task_id=? ORDER BY created_at",
                (task_id,),
            ).fetchall()
        return [
            {
                "step_id": r["step_id"],
                "task_id": r["task_id"],
                "tool_name": r["tool_name"],
                "arguments": _jd(r["arguments_json"]),
                "status": r["status"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "completed_at": r["completed_at"],
                "error": r["error"],
            }
            for r in rows
        ]

    # --- projects & chunks (RAG) ---------------------------------------

    def upsert_project(self, name: str, root: str) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO projects(name, root, ingested_at) VALUES(?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET root=excluded.root, "
                "ingested_at=excluded.ingested_at",
                (name, root, _now()),
            )

    def list_projects(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("SELECT name, root, ingested_at FROM projects ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    def clear_project_chunks(self, project: str) -> None:
        with self._lock, self._conn() as conn:
            conn.execute("DELETE FROM chunks WHERE project=?", (project,))

    def insert_chunk(self, project: str, path: str, line_start: int | None,
                     line_end: int | None, content: str,
                     embedding: list[float]) -> None:
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT INTO chunks(chunk_id, project, path, line_start, line_end, "
                "content, embedding_json, created_at) VALUES(?,?,?,?,?,?,?,?)",
                (str(uuid4()), project, path, line_start, line_end, content,
                 _j(embedding), _now()),
            )

    def iter_chunks(self, project: str | None = None):
        with self._conn() as conn:
            if project is None:
                rows = conn.execute(
                    "SELECT project, path, line_start, line_end, content, embedding_json FROM chunks"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT project, path, line_start, line_end, content, embedding_json "
                    "FROM chunks WHERE project=?",
                    (project,),
                ).fetchall()
        for r in rows:
            yield {
                "project": r["project"],
                "path": r["path"],
                "line_start": r["line_start"],
                "line_end": r["line_end"],
                "content": r["content"],
                "embedding": json.loads(r["embedding_json"]),
            }