from __future__ import annotations

import os
import sys
from pathlib import Path

from .agent import ZebioAgent
from .memory import MemoryStore
from .ollama_client import OllamaClient
from .project_context import ProjectRegistry
from .retrieval import ingest_project


def _build_agent() -> ZebioAgent:
    memory_path = os.environ.get("ZEBIO_MEMORY_DB", str(Path.home() / ".zebio" / "memory.db"))
    memory = MemoryStore(memory_path)
    projects = ProjectRegistry()

    # Optional: load additional project roots from env: ZEBIO_PROJECTS="name=path,name=path"
    extra = os.environ.get("ZEBIO_PROJECTS", "")
    for pair in extra.split(","):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        name, root = pair.split("=", 1)
        projects.register(name.strip(), root.strip())

    client = OllamaClient()
    return ZebioAgent(memory_store=memory, projects=projects, ollama_client=client)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    if not argv or argv[0] in {"-h", "--help", "help"}:
        print("Usage:")
        print("  zebio chat [session_id]           Start an interactive session")
        print("  zebio ingest <name> <path>        Ingest a project for semantic search")
        print("  zebio projects                    List ingested projects")
        return 0

    cmd = argv[0]

    if cmd == "ingest":
        if len(argv) < 3:
            print("Usage: zebio ingest <name> <path>")
            return 2
        agent = _build_agent()
        info = ingest_project(agent.memory, agent.ollama_client, argv[1], argv[2])
        print(info)
        return 0

    if cmd == "projects":
        agent = _build_agent()
        for p in agent.memory.list_projects():
            print(f"{p['name']}\t{p['root']}\tingested={p['ingested_at']}")
        return 0

    if cmd == "chat":
        session_id = argv[1] if len(argv) > 1 else "default"
        agent = _build_agent()
        print(f"Zebio session '{session_id}'. Type 'exit' to quit.")
        while True:
            try:
                user = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not user:
                continue
            if user.lower() in {"exit", "quit"}:
                return 0

            reply = agent.run(session_id=session_id, user_message=user)

            # Detect paused-for-approval text and prompt the user
            if "Approval required" in reply and "Approval ID:" in reply:
                print(f"\nzebio> {reply}")
                approval_id = reply.split("Approval ID:", 1)[1].strip()
                decision = input(f"Approve action {approval_id}? [y/N] ").strip().lower()
                if decision == "y":
                    agent.approve_action(approval_id)
                    reply = agent.resume_after_approval(approval_id)
                else:
                    reason = input("Reason (optional): ").strip() or None
                    reply = agent.resume_after_rejection(approval_id, reason)

            print(f"\nzebio> {reply}")

        return 0

    print(f"Unknown command: {cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())