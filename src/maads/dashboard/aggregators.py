"""Transform trace artifacts into dashboard-friendly JSON."""
from __future__ import annotations

from typing import Any

from maads.observability.agent_labels import resolve_maads_agent_id
from maads.observability.render.timeline import _TIMELINE_TYPES
from maads.observability.schema import TraceEvent, TraceRun

_NODE_LAYOUT: dict[str, tuple[float, float]] = {
    "orchestrator": (0, 200),
    "pm": (220, 80),
    "domain": (220, 160),
    "data_engineer": (220, 240),
    "data_scientist": (220, 320),
    "developer": (220, 400),
    "llm": (480, 200),
    "python_exec": (480, 320),
    "tool": (480, 400),
}

_AGENT_LABELS: dict[str, str] = {
    "pm": "Project Manager",
    "domain": "Domain Expert",
    "data_engineer": "Data Engineer",
    "data_scientist": "Data Scientist",
    "developer": "Developer",
}


def filter_timeline_events(events: list[TraceEvent]) -> list[TraceEvent]:
    return [e for e in events if e.type in _TIMELINE_TYPES]


def trace_summary(run: TraceRun) -> dict[str, Any]:
    filtered = filter_timeline_events(run.events)
    return {
        "run_id": run.run_id,
        "case_id": run.case_id,
        "started_at": run.started_at.isoformat(),
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "total_events": len(run.events),
        "filtered_event_count": len(filtered),
        "events": [_event_dict(e) for e in filtered],
    }


def trace_events_since(run: TraceRun, since_id: str | None) -> dict[str, Any]:
    filtered = filter_timeline_events(run.events)
    if since_id:
        start = 0
        for i, evt in enumerate(filtered):
            if evt.id == since_id:
                start = i + 1
                break
        filtered = filtered[start:]
    return {
        "run_id": run.run_id,
        "events": [_event_dict(e) for e in filtered],
    }


def _event_dict(evt: TraceEvent) -> dict[str, Any]:
    return {
        "id": evt.id,
        "parent_id": evt.parent_id,
        "ts": evt.ts.isoformat(),
        "ts_mono_ms": evt.ts_mono_ms,
        "duration_ms": evt.duration_ms,
        "type": evt.type,
        "source": evt.source,
        "name": evt.name,
        "attributes": evt.attributes,
    }


def _agent_from_event(evt: TraceEvent) -> str | None:
    if evt.type == "substep.dispatch":
        owner = evt.attributes.get("owner")
        if owner:
            return str(owner)
    return resolve_maads_agent_id(evt.attributes, event_name=evt.name)


def build_graph(run: TraceRun) -> dict[str, Any]:
    """Build React Flow nodes and edges from trace events."""
    agents_seen: set[str] = set()
    dispatch_edges: set[tuple[str, str]] = set()
    interaction_edges: list[dict[str, Any]] = []
    node_states: dict[str, str] = {"orchestrator": "idle"}
    active_llm_by_agent: dict[str, str] = {}
    open_llm_comm: str | None = None

    has_llm = False
    has_py = False
    has_tool = False
    current_agent: str | None = None

    for evt in run.events:
        agent_id = _agent_from_event(evt)
        if agent_id:
            agents_seen.add(agent_id)
            node_states.setdefault(agent_id, "idle")

        if evt.type == "substep.dispatch" and agent_id:
            dispatch_edges.add(("orchestrator", agent_id))
            node_states[agent_id] = "active"
            current_agent = agent_id
            for aid in agents_seen:
                if aid != agent_id and node_states.get(aid) == "active":
                    node_states[aid] = "done"

        elif evt.type == "agent.activate":
            if agent_id:
                current_agent = agent_id
                node_states[agent_id] = "active"

        elif evt.type == "agent.complete":
            if agent_id:
                node_states[agent_id] = "done"
            elif current_agent:
                node_states[current_agent] = "done"

        elif evt.type == "substep.end":
            if current_agent:
                node_states[current_agent] = "done"

        elif evt.type == "llm.start":
            has_llm = True
            comm = evt.attributes.get("communication_id")
            agent = current_agent or agent_id
            if agent:
                edge_id = f"llm-{agent}-{comm or evt.id}"
                active_llm_by_agent[agent] = edge_id
                open_llm_comm = comm
                interaction_edges.append({
                    "id": edge_id,
                    "source": agent,
                    "target": "llm",
                    "animated": True,
                    "communication_id": comm,
                })

        elif evt.type == "llm.end":
            comm = evt.attributes.get("communication_id")
            agent = current_agent or agent_id
            if agent and agent in active_llm_by_agent:
                for edge in interaction_edges:
                    if edge["id"] == active_llm_by_agent[agent]:
                        edge["animated"] = False
                del active_llm_by_agent[agent]
            if comm and open_llm_comm == comm:
                open_llm_comm = None

        elif evt.type == "python.subprocess":
            has_py = True
            agent = current_agent or agent_id
            if agent:
                interaction_edges.append({
                    "id": f"py-{agent}-{evt.id}",
                    "source": agent,
                    "target": "python_exec",
                    "animated": False,
                    "communication_id": None,
                })

        elif evt.type == "tool.start":
            has_tool = True
            agent = current_agent or agent_id
            if agent:
                interaction_edges.append({
                    "id": f"tool-{agent}-{evt.id}",
                    "source": agent,
                    "target": "tool",
                    "animated": False,
                    "communication_id": None,
                })

        elif evt.type == "exception":
            if current_agent:
                node_states[current_agent] = "error"

    nodes: list[dict[str, Any]] = [{
        "id": "orchestrator",
        "type": "agentNode",
        "position": {"x": _NODE_LAYOUT["orchestrator"][0], "y": _NODE_LAYOUT["orchestrator"][1]},
        "data": {"label": "Orchestrator", "state": node_states.get("orchestrator", "idle")},
    }]

    for agent_id in sorted(agents_seen):
        pos = _NODE_LAYOUT.get(agent_id, (220, 200))
        nodes.append({
            "id": agent_id,
            "type": "agentNode",
            "position": {"x": pos[0], "y": pos[1]},
            "data": {
                "label": _AGENT_LABELS.get(agent_id, agent_id),
                "state": node_states.get(agent_id, "idle"),
            },
        })

    if has_llm:
        nodes.append({
            "id": "llm",
            "type": "serviceNode",
            "position": {"x": _NODE_LAYOUT["llm"][0], "y": _NODE_LAYOUT["llm"][1]},
            "data": {"label": "LLM", "state": "active" if open_llm_comm else "idle"},
        })
    if has_py:
        nodes.append({
            "id": "python_exec",
            "type": "serviceNode",
            "position": {"x": _NODE_LAYOUT["python_exec"][0], "y": _NODE_LAYOUT["python_exec"][1]},
            "data": {"label": "PythonExec", "state": "idle"},
        })
    if has_tool:
        nodes.append({
            "id": "tool",
            "type": "serviceNode",
            "position": {"x": _NODE_LAYOUT["tool"][0], "y": _NODE_LAYOUT["tool"][1]},
            "data": {"label": "Tool", "state": "idle"},
        })

    edges: list[dict[str, Any]] = []
    for src, tgt in sorted(dispatch_edges):
        edges.append({
            "id": f"dispatch-{src}-{tgt}",
            "source": src,
            "target": tgt,
            "animated": False,
            "edgeType": "dispatch",
        })

    seen_interaction: set[str] = set()
    for edge in interaction_edges:
        if edge["id"] in seen_interaction:
            continue
        seen_interaction.add(edge["id"])
        edges.append({
            "id": edge["id"],
            "source": edge["source"],
            "target": edge["target"],
            "animated": edge["animated"],
            "edgeType": "interaction",
            "communication_id": edge.get("communication_id"),
        })

    return {"nodes": nodes, "edges": edges}
