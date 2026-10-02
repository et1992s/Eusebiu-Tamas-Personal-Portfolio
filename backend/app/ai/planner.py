from __future__ import annotations

import json
from typing import Any

from .ollama_client import OllamaClient
from .schemas import Plan, PlanStep


PLANNER_SYSTEM_PROMPT = """You are Zebio's planning module.

Produce a SHORT, actionable plan for the user's engineering goal on THIS project.

Rules:
- Maximum 8 steps.
- Each step must be concrete and independently verifiable.
- Prefer read/inspect steps first, then change steps, then verify steps.
- Never invent files, directories, or modules you have not seen.
- Do NOT include tool names. Steps describe WHAT to achieve, not HOW.
- If the goal is a question (e.g. "where is X"), the plan is investigation + answer.
- If the goal requires code changes, the final step MUST be a verification step.

Respond with ONLY a JSON object of the form:
{"steps": [{"title": "...", "detail": "..."}, ...]}
"""


def generate_plan(client: OllamaClient, goal: str, project_structure: str | None = None) -> Plan:
    user_parts = [f"Goal:\n{goal}"]
    if project_structure:
        user_parts.append(f"Project structure (truncated):\n{project_structure[:4000]}")
    user = "\n\n".join(user_parts)

    response = client.chat([
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])

    steps = _parse_steps(response)

    if not steps:
        steps = [
            PlanStep(index=0, title="Investigate the relevant project area",
                     detail="Locate the files and code paths related to the goal.", status="pending"),
            PlanStep(index=1, title="Apply the required changes",
                     detail="Make the minimal change that achieves the goal.", status="pending"),
            PlanStep(index=2, title="Verify the outcome",
                     detail="Run or inspect evidence that the goal is achieved.", status="pending"),
        ]

    return Plan(steps=steps, revision=0, goal=goal)


def revise_plan(client: OllamaClient, plan: Plan, feedback: str) -> Plan:
    current = [
        {"index": s.index, "title": s.title, "detail": s.detail,
         "status": s.status, "note": s.note}
        for s in plan.steps
    ]

    user = (
        f"Original goal:\n{plan.goal}\n\n"
        f"Current plan:\n{json.dumps(current, indent=2)}\n\n"
        f"Reflection / feedback:\n{feedback}\n\n"
        "Revise the plan. You may reorder, drop, split, or add steps. "
        "Keep completed steps marked 'completed' unless they are invalid. "
        "Respond with ONLY a JSON object: {\"steps\": [{\"title\": \"...\", \"detail\": \"...\", \"status\": \"pending|completed\"}]}"
    )

    response = client.chat([
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])

    steps = _parse_steps(response, previous=plan.steps)

    if not steps:
        return plan

    return Plan(steps=steps, revision=plan.revision + 1, goal=plan.goal)


def _parse_steps(text: str, previous: list[PlanStep] | None = None) -> list[PlanStep]:
    text = text.strip()
    if "```" in text:
        # strip code fences if present
        if "```json" in text:
            text = text.split("```json", 1)[1]
        elif "```" in text:
            text = text.split("```", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]
        text = text.strip()

    start = text.find("{")
    if start == -1:
        return []

    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return []

    if not isinstance(data, dict):
        return []

    raw_steps = data.get("steps", [])
    if not isinstance(raw_steps, list):
        return []

    prev_by_title = {s.title: s for s in (previous or [])}

    steps: list[PlanStep] = []
    for idx, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        detail = str(raw.get("detail", "")).strip()
        status = str(raw.get("status", "pending")).strip().lower()
        if status not in {"pending", "in_progress", "completed", "skipped"}:
            status = "pending"
        note = prev_by_title.get(title).note if title in prev_by_title else None
        steps.append(PlanStep(index=idx, title=title, detail=detail,
                              status=status, note=note))

    return steps