"""Resolve MAADS agent ids and display labels for trace rendering."""
from __future__ import annotations

from typing import Any

from maads.prompts import AGENT_PROMPTS

_GENERIC_EVENT_NAMES = frozenset({
    "CrewKickoffStarted",
    "CrewKickoffCompleted",
    "CrewKickoffFailed",
    "LLMCall",
    "TaskStarted",
    "TaskCompleted",
})


def maads_id_for_role(role: str | None) -> str | None:
    if not role:
        return None
    for agent_id, meta in AGENT_PROMPTS.items():
        if meta["role"] == role:
            return agent_id
    return None


def agent_role_from_crew(event: Any) -> str | None:
    crew = getattr(event, "crew", None)
    if crew is None:
        return None
    agents = getattr(crew, "agents", None) or []
    if not agents:
        return None
    agent = agents[0]
    return getattr(agent, "role", None) or str(agent)


def resolve_maads_agent_id(attrs: dict[str, Any], *, event_name: str = "") -> str | None:
    """Best-effort MAADS agent id (``pm``, ``domain``, …) from trace attributes."""
    role = attrs.get("role")
    if role:
        mapped = maads_id_for_role(str(role))
        if mapped:
            return mapped
    for key in ("agent_name", "maads_agent", "agent"):
        raw = attrs.get(key)
        if not raw:
            continue
        text = str(raw)
        if text in AGENT_PROMPTS:
            return text
        mapped = maads_id_for_role(text)
        if mapped:
            return mapped
        if text not in _GENERIC_EVENT_NAMES:
            return text
    if event_name and event_name not in _GENERIC_EVENT_NAMES:
        if event_name in AGENT_PROMPTS:
            return event_name
        mapped = maads_id_for_role(event_name)
        if mapped:
            return mapped
    return None


def format_agent_label(attrs: dict[str, Any], *, event_name: str = "") -> str:
    """Human-readable agent for narratives and diagrams."""
    agent_id = resolve_maads_agent_id(attrs, event_name=event_name)
    role = attrs.get("role")
    if agent_id and agent_id in AGENT_PROMPTS:
        role = AGENT_PROMPTS[agent_id]["role"]
    elif not role and agent_id:
        role = agent_id
    elif role and not agent_id:
        agent_id = maads_id_for_role(str(role))

    if role and agent_id:
        return f"{role} (`{agent_id}`)"
    if role:
        return str(role)
    if agent_id:
        return str(agent_id)
    return "unknown agent"
