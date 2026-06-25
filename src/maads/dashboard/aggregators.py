"""Transform trace artifacts into dashboard-friendly JSON."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from maads.observability.agent_labels import resolve_maads_agent_id
from maads.observability.render.timeline import _TIMELINE_TYPES
from maads.observability.schema import TraceEvent, TraceRun
from maads.run_status import PHASE_NAMES
from maads.state import SUBSTEP_NAMES, SUBSTEP_OWNER, SUBSTEPS, Phase

_AGENT_IDS = ("pm", "domain", "data_engineer", "data_scientist", "developer", "storyteller")

_FLOW_NODE_ID = "crisp_dm_flow"
_FLOW_LABEL = "CrispDM Flow"

_COL_FLOW = 0
_COL_AGENTS = 300
_COL_SERVICES = 600
_AGENT_ROW_GAP = 96
_SERVICE_ROW_GAP = 88

_AGENT_LABELS: dict[str, str] = {
    "pm": "Project Manager",
    "domain": "Domain Expert",
    "data_engineer": "Data Engineer",
    "data_scientist": "Data Scientist",
    "developer": "Developer",
    "storyteller": "Storyteller",
}


def filter_timeline_events(events: list[TraceEvent]) -> list[TraceEvent]:
    return [e for e in events if e.type in _TIMELINE_TYPES]


def trace_summary(run: TraceRun, *, tail_limit: int | None = None) -> dict[str, Any]:
    filtered = filter_timeline_events(run.events)
    if tail_limit is not None and len(filtered) > tail_limit:
        filtered = filtered[-tail_limit:]
    return {
        "run_id": run.run_id,
        "case_id": run.case_id,
        "started_at": run.started_at.isoformat(),
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "total_events": len(run.events),
        "filtered_event_count": len(filter_timeline_events(run.events)),
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


def _stack_positions(ids: list[str], x: float, gap: float) -> dict[str, tuple[float, float]]:
    """Vertically center a column of nodes around y=200."""
    if not ids:
        return {}
    span = (len(ids) - 1) * gap
    start_y = 200 - span / 2
    return {node_id: (x, start_y + i * gap) for i, node_id in enumerate(ids)}


def _graph_layout(
    agents_seen: set[str],
    *,
    has_llm: bool,
    has_py: bool,
    has_tool: bool,
) -> dict[str, tuple[float, float]]:
    ordered_agents = [a for a in _AGENT_IDS if a in agents_seen]
    positions = _stack_positions(ordered_agents, _COL_AGENTS, _AGENT_ROW_GAP)

    services: list[str] = []
    if has_llm:
        services.append("llm")
    if has_py:
        services.append("python_exec")
    if has_tool:
        services.append("tool")
    positions.update(_stack_positions(services, _COL_SERVICES, _SERVICE_ROW_GAP))

    if ordered_agents:
        agent_ys = [positions[a][1] for a in ordered_agents]
        flow_y = sum(agent_ys) / len(agent_ys)
    elif services:
        service_ys = [positions[s][1] for s in services]
        flow_y = sum(service_ys) / len(service_ys)
    else:
        flow_y = 200.0
    positions[_FLOW_NODE_ID] = (_COL_FLOW, flow_y)
    return positions


def build_graph(run: TraceRun) -> dict[str, Any]:
    """Build React Flow nodes and edges from trace events."""
    agents_seen: set[str] = set()
    dispatch_edges: set[tuple[str, str]] = set()
    interaction_edges: list[dict[str, Any]] = []
    node_states: dict[str, str] = {_FLOW_NODE_ID: "idle"}
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
            dispatch_edges.add((_FLOW_NODE_ID, agent_id))
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

    layout = _graph_layout(agents_seen, has_llm=has_llm, has_py=has_py, has_tool=has_tool)
    flow_pos = layout[_FLOW_NODE_ID]

    nodes: list[dict[str, Any]] = [{
        "id": _FLOW_NODE_ID,
        "type": "flowNode",
        "position": {"x": flow_pos[0], "y": flow_pos[1]},
        "data": {"label": _FLOW_LABEL, "state": node_states.get(_FLOW_NODE_ID, "idle")},
    }]

    for agent_id in sorted(agents_seen):
        pos = layout.get(agent_id, (_COL_AGENTS, 200))
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
        pos = layout["llm"]
        nodes.append({
            "id": "llm",
            "type": "serviceNode",
            "position": {"x": pos[0], "y": pos[1]},
            "data": {"label": "LLM", "state": "active" if open_llm_comm else "idle"},
        })
    if has_py:
        pos = layout["python_exec"]
        nodes.append({
            "id": "python_exec",
            "type": "serviceNode",
            "position": {"x": pos[0], "y": pos[1]},
            "data": {"label": "PythonExec", "state": "idle"},
        })
    if has_tool:
        pos = layout["tool"]
        nodes.append({
            "id": "tool",
            "type": "serviceNode",
            "position": {"x": pos[0], "y": pos[1]},
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


def _canonical_substeps() -> list[str]:
    out: list[str] = []
    for phase in Phase:
        out.extend(SUBSTEPS[phase])
    return out


def _substep_trace_state(
    run: TraceRun,
    current_substep: str,
) -> tuple[set[str], set[str], set[str], dict[str, int | None]]:
    """Return (ended, skipped, dispatched, duration_by_substep)."""
    ended: set[str] = set()
    skipped: set[str] = set()
    dispatched: set[str] = set()
    dispatch_mono: dict[str, float] = {}
    end_mono: dict[str, float] = {}

    for evt in run.events:
        sub = evt.attributes.get("substep")
        if evt.type == "substep.dispatch" and sub:
            dispatched.add(str(sub))
            dispatch_mono[str(sub)] = evt.ts_mono_ms
        elif evt.type == "substep.end" and sub:
            ended.add(str(sub))
            end_mono[str(sub)] = evt.ts_mono_ms
        elif evt.type == "branch" and sub:
            skipped.add(str(sub))

    durations: dict[str, int | None] = {}
    for sub in ended:
        if sub in dispatch_mono and sub in end_mono:
            durations[sub] = int(end_mono[sub] - dispatch_mono[sub])

    return ended, skipped, dispatched, durations


def _substep_status(
    substep: str,
    current_substep: str,
    ended: set[str],
    skipped: set[str],
    canonical: list[str],
) -> str:
    if substep == current_substep:
        return "active"
    if substep in skipped:
        return "skipped"
    if substep in ended:
        return "done"
    try:
        cur_idx = canonical.index(current_substep)
        sub_idx = canonical.index(substep)
    except ValueError:
        return "pending"
    if sub_idx < cur_idx:
        return "done"
    return "pending"


def build_process_view(
    status: dict[str, Any],
    run: TraceRun,
    snapshot: dict[str, Any],
    *,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    """Merge status, trace, and process snapshot into a CRISP-DM team view."""
    current_substep = str(status.get("substep", "1.1"))
    current_phase = int(status.get("phase", 1))
    outputs_status = snapshot.get("outputs_status") or {}
    conclusions = snapshot.get("conclusions") or {}
    config = snapshot.get("config") or {}
    recent_log: list[dict[str, Any]] = snapshot.get("recent_log") or []
    token_spend: dict[str, int] = status.get("token_spend") or {}
    token_spend_by_provider: dict[str, int] = status.get("token_spend_by_provider") or {}

    canonical = _canonical_substeps()
    ended, skipped, _dispatched, durations = _substep_trace_state(run, current_substep)

    substeps: list[dict[str, Any]] = []
    for sub in canonical:
        owner = SUBSTEP_OWNER[sub]
        substeps.append({
            "id": sub,
            "name": SUBSTEP_NAMES.get(sub, sub),
            "owner": owner,
            "owner_label": _AGENT_LABELS.get(owner, owner),
            "phase": int(sub.split(".")[0]),
            "status": _substep_status(sub, current_substep, ended, skipped, canonical),
            "duration_ms": durations.get(sub),
        })

    phases: list[dict[str, Any]] = []
    for phase in Phase:
        phase_num = int(phase)
        ready_key = f"phase_{phase_num}_ready"
        phase_ready = bool(outputs_status.get(ready_key))
        if phase_ready:
            phase_status = "complete"
        elif phase_num == current_phase:
            phase_status = "active"
        elif phase_num < current_phase:
            phase_status = "complete"
        else:
            phase_status = "pending"
        phases.append({
            "id": phase_num,
            "name": PHASE_NAMES.get(phase_num, ""),
            "status": phase_status,
            "ready": phase_ready,
            "substeps": [s for s in substeps if s["phase"] == phase_num],
        })

    current_owner = SUBSTEP_OWNER.get(current_substep)
    owned_by_agent: dict[str, list[str]] = {a: [] for a in _AGENT_IDS}
    for sub, owner in SUBSTEP_OWNER.items():
        if owner in owned_by_agent:
            owned_by_agent[owner].append(sub)

    team: list[dict[str, Any]] = []
    for agent_id in _AGENT_IDS:
        agent_log = [e for e in recent_log if e.get("agent") == agent_id]
        team.append({
            "id": agent_id,
            "label": _AGENT_LABELS.get(agent_id, agent_id),
            "status": "active" if agent_id == current_owner else "idle",
            "current_substep": current_substep if agent_id == current_owner else None,
            "owned_substeps": owned_by_agent[agent_id],
            "recent_work": agent_log[-3:],
            "tokens": token_spend.get(agent_id, 0),
        })

    loops: list[dict[str, Any]] = []
    for le in snapshot.get("loop_history") or []:
        loops.append({
            "label": le.get("label"),
            "from_phase": le.get("from_phase"),
            "to_phase": le.get("to_phase"),
            "reason": le.get("reason"),
            "ts": le.get("t"),
        })
    for evt in run.events:
        if evt.type != "loop":
            continue
        attrs = evt.attributes
        loops.append({
            "label": attrs.get("label"),
            "from_phase": attrs.get("from_phase"),
            "to_phase": attrs.get("to_phase"),
            "reason": attrs.get("reason"),
            "ts": evt.ts.isoformat(),
        })

    deliverables: list[dict[str, Any]] = []
    for label, path in (conclusions.get("dataset_paths") or {}).items():
        deliverables.append(_deliverable(f"Dataset ({label})", path, artifact_dir))
    for label, path in (
        ("Submission", conclusions.get("submission_path")),
        ("Final report", conclusions.get("final_report_path")),
    ):
        if path:
            deliverables.append(_deliverable(label, path, artifact_dir))

    return {
        "updated_at": snapshot.get("updated_at") or status.get("updated_at"),
        "current_phase": current_phase,
        "current_substep": current_substep,
        "current_substep_name": status.get("substep_name", ""),
        "activity": status.get("activity", ""),
        "phases": phases,
        "substeps": substeps,
        "team": team,
        "conclusions": conclusions,
        "config": config,
        "loops": loops,
        "deliverables": deliverables,
        "validator_findings": snapshot.get("validator_findings") or [],
        "outputs_status": outputs_status,
        "token_spend_by_provider": token_spend_by_provider,
    }


def _deliverable(label: str, path: str, artifact_dir: Path | None) -> dict[str, Any]:
    exists = Path(path).is_file() if path else False
    if not exists and artifact_dir and path:
        rel = Path(path)
        if not rel.is_absolute():
            exists = (artifact_dir / rel).is_file()
    return {"label": label, "path": path, "exists": exists}
