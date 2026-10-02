from __future__ import annotations

import json
from typing import Any

from .ollama_client import OllamaClient
from .schemas import Plan, Reflection


REFLECTOR_SYSTEM_PROMPT = """You are Zebio's reflection module.

You are given:
- the user's goal,
- the current plan with step statuses,
- the recent tool observations.

Judge the agent's trajectory and answer:
1. On track? (true/false)
2. If off track, what is the single most important issue?
3. Should the plan be revised? (true/false)
4. What single next action would most advance the goal?

Ground every judgement in the observations. Do not invent facts.

Respond with ONLY a JSON object:
{
  "on_track": true|false,
  "issue": "...",
  "revise_plan": true|false,
  "next_action_hint": "..."
}
"""


def reflect(client: OllamaClient, goal: str, plan: Plan,
            observations: list[dict[str, Any]],
            runtime_feedback: str | None = None) -> Reflection:
    recent = observations[-10:]

    user = (
        f"Goal:\n{goal}\n\n"
        f"Plan:\n{json.dumps([{'title': s.title, 'status': s.status} for s in plan.steps], indent=2)}\n\n"
        f"Recent observations:\n"
        f"{json.dumps(_trim(recent), indent=2, ensure_ascii=False, default=str)}\n\n"
    )
    if runtime_feedback:
        user += f"\nRuntime feedback:\n{runtime_feedback}\n"

    response = client.chat([
        {"role": "system", "content": REFLECTOR_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ])

    data = _parse_json(response)
    if not data:
        return Reflection(on_track=True, issue=None, revise_plan=False, next_action_hint=None)

    return Reflection(
        on_track=bool(data.get("on_track", True)),
        issue=(str(data["issue"]) if data.get("issue") else None),
        revise_plan=bool(data.get("revise_plan", False)),
        next_action_hint=(str(data["next_action_hint"]) if data.get("next_action_hint") else None),
    )


def _trim(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for obs in observations:
        result = obs.get("result")
        text = json.dumps(result, ensure_ascii=False, default=str)
        if len(text) > 1200:
            text = text[:1200] + "...[truncated]"
        out.append({
            "tool": obs.get("tool"),
            "arguments": obs.get("arguments"),
            "result_preview": text,
        })
    return out


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if "```" in text:
        if "```json" in text:
            text = text.split("```json", 1)[1]
        else:
            text = text.split("```", 1)[1]
        if "```" in text:
            text = text.split("```", 1)[0]
    start = text.find("{")
    if start == -1:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None