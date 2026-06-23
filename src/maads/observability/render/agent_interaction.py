"""Render agent interaction diagram."""
from __future__ import annotations

from maads.observability.agent_labels import resolve_maads_agent_id
from maads.observability.schema import TraceEvent, TraceRun


def _agent_id_from_event(evt: TraceEvent) -> str | None:
    if evt.type == "substep.dispatch":
        owner = evt.attributes.get("owner")
        if owner:
            return str(owner)
    return resolve_maads_agent_id(evt.attributes, event_name=evt.name)


def render_agent_interaction(run: TraceRun) -> str:
    lines = [
        "flowchart LR",
        "    subgraph orchestrator [Orchestrator]",
        "        Orch[Orchestrator]",
        "    end",
    ]
    agents: set[str] = set()
    for evt in run.events:
        if evt.type in {"agent.activate", "substep.dispatch"}:
            aid = _agent_id_from_event(evt)
            if aid:
                agents.add(aid)

    for agent in sorted(agents):
        lines.append(f"    subgraph {agent} [{agent}]")
        lines.append(f"        A_{agent}[{agent}]")
        lines.append("    end")
        lines.append(f"    Orch --> A_{agent}")

    lines.append("")
    lines.append("    subgraph tools [Tools_and_LLM]")
    has_llm = any(e.type.startswith("llm.") for e in run.events)
    has_tool = any(e.type.startswith("tool.") for e in run.events)
    has_py = any(e.type == "python.subprocess" for e in run.events)
    if has_llm:
        lines.append("        LLM[LLM]")
    if has_tool:
        lines.append("        Tool[Tool]")
    if has_py:
        lines.append("        PyExec[PythonExec]")
    lines.append("    end")

    current_agent: str | None = None
    seen_edges: set[str] = set()
    for evt in run.events:
        agent_id = _agent_id_from_event(evt)
        if evt.type == "agent.activate" and agent_id:
            current_agent = agent_id
        elif evt.type == "substep.dispatch":
            current_agent = evt.attributes.get("owner") or agent_id
        elif current_agent and evt.type == "llm.start" and has_llm:
            edge = f"A_{current_agent} --> LLM"
            if edge not in seen_edges:
                seen_edges.add(edge)
                lines.append(f"    {edge}")
        elif current_agent and evt.type == "tool.start" and has_tool:
            edge = f"A_{current_agent} --> Tool"
            if edge not in seen_edges:
                seen_edges.add(edge)
                lines.append(f"    {edge}")
        elif current_agent and evt.type == "python.subprocess" and has_py:
            edge = f"A_{current_agent} --> PyExec"
            if edge not in seen_edges:
                seen_edges.add(edge)
                lines.append(f"    {edge}")

    return "\n".join(lines) + "\n"
