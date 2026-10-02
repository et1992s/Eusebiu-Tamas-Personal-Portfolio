from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from .memory import MemoryStore
from .ollama_client import OllamaClient

INGEST_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
    ".rb", ".php", ".cs", ".c", ".h", ".cpp", ".hpp", ".sql", ".sh",
    ".md", ".txt", ".toml", ".yaml", ".yml", ".json", ".html", ".css",
}

IGNORED_DIRS = {
    ".git", ".venv", "venv", "env", "__pycache__", "node_modules",
    ".pytest_cache", "dist", "build", ".next", ".mypy_cache", ".ruff_cache",
}

IGNORED_FILES = {
    ".env", ".env.local", ".env.production", ".env.development",
    "credentials.json", "secrets.json", "package-lock.json", "poetry.lock",
}

CHUNK_LINES = 80
CHUNK_OVERLAP = 10
MAX_FILE_BYTES = 400_000


def _iter_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.name in IGNORED_FILES:
            continue
        if path.suffix.lower() not in INGEST_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield path


def _chunk_text(text: str) -> Iterable[tuple[int, int, str]]:
    lines = text.splitlines()
    if not lines:
        return
    step = CHUNK_LINES - CHUNK_OVERLAP
    for start in range(0, len(lines), step):
        end = min(start + CHUNK_LINES, len(lines))
        chunk = "\n".join(lines[start:end])
        if chunk.strip():
            yield start + 1, end, chunk
        if end == len(lines):
            break


def ingest_project(store: MemoryStore, client: OllamaClient,
                   name: str, root: str | Path,
                   embedding_model: str = "nomic-embed-text",
                   progress: bool = True) -> dict:
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    store.upsert_project(name, str(root))
    store.clear_project_chunks(name)

    files = 0
    chunks = 0
    for path in _iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = str(path.relative_to(root))
        files += 1
        for start, end, chunk in _chunk_text(text):
            try:
                vector = client.embed(model=embedding_model, text=chunk)
            except Exception as exc:
                if progress:
                    print(f"[ingest] embed failed for {rel}:{start}-{end}: {exc}")
                continue
            store.insert_chunk(name, rel, start, end, chunk, vector)
            chunks += 1
        if progress and files % 25 == 0:
            print(f"[ingest] {files} files, {chunks} chunks...")

    if progress:
        print(f"[ingest] done: {files} files, {chunks} chunks -> project '{name}'")

    return {"project": name, "files": files, "chunks": chunks, "root": str(root)}


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def semantic_search(store: MemoryStore, client: OllamaClient,
                    query: str, project: str | None = None,
                    top_k: int = 8,
                    embedding_model: str = "nomic-embed-text") -> list[dict]:
    if not query.strip():
        return []
    qvec = client.embed(model=embedding_model, text=query)
    scored: list[tuple[float, dict]] = []
    for chunk in store.iter_chunks(project=project):
        score = _cosine(qvec, chunk["embedding"])
        scored.append((score, chunk))
    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, chunk in scored[:top_k]:
        results.append({
            "project": chunk["project"],
            "path": chunk["path"],
            "line_start": chunk["line_start"],
            "line_end": chunk["line_end"],
            "score": round(score, 4),
            "content": chunk["content"],
        })
    return results