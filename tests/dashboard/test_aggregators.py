"""Tests for dashboard aggregators."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from maads.dashboard.aggregators import (
    build_graph,
    build_process_view,
    filter_timeline_events,
    trace_summary,
)
from maads.observability.schema import TraceEvent, TraceRun


def _evt(
    eid: str,
    etype: str,
    *,
    attrs: dict | None = None,
    name: str = "",
    mono: float = 0,
) -> TraceEvent:
    return TraceEvent(
        id=eid,
        ts=datetime.now(timezone.utc),
        ts_mono_ms=mono,
        type=etype,
        name=name,
        attributes=attrs or {},
    )


def test_filter_timeline_events_excludes_python_calls():
    run = TraceRun(
        run_id="r1",
        events=[
            _evt("evt_0001", "run.start"),
            _evt("evt_0002", "python.call"),
            _evt("evt_0003", "llm.start", attrs={"communication_id": "comm_0001"}),
        ],
    )
    filtered = filter_timeline_events(run.events)
    types = {e.type for e in filtered}
    assert "python.call" not in types
    assert "run.start" in types
    assert "llm.start" in types


def test_trace_summary_shape():
    run = TraceRun(run_id="abc", case_id="titanic", events=[_evt("evt_0001", "run.start")])
    summary = trace_summary(run)
    assert summary["run_id"] == "abc"
    assert summary["case_id"] == "titanic"
    assert summary["filtered_event_count"] == 1


def test_build_graph_agent_edges_use_owner_ids():
    run = TraceRun(
        run_id="r1",
        events=[
            _evt("evt_0001", "substep.dispatch", attrs={"owner": "pm", "substep": "1.1"}, mono=10),
            _evt("evt_0002", "agent.activate", attrs={"role": "Project Manager", "maads_agent": "pm"}, mono=20),
            _evt("evt_0003", "llm.start", attrs={"communication_id": "comm_0001"}, mono=30),
            _evt("evt_0004", "llm.end", attrs={"communication_id": "comm_0001"}, mono=40),
        ],
    )
    graph = build_graph(run)
    node_ids = {n["id"] for n in graph["nodes"]}
    assert "pm" in node_ids
    assert "crisp_dm_flow" in node_ids
    flow_node = next(n for n in graph["nodes"] if n["id"] == "crisp_dm_flow")
    assert flow_node["data"]["label"] == "CrispDM Flow"
    assert flow_node["type"] == "flowNode"
    assert "llm" in node_ids
    llm_edges = [e for e in graph["edges"] if e["target"] == "llm"]
    assert any(e["source"] == "pm" for e in llm_edges)
    dispatch_edges = [e for e in graph["edges"] if e["edgeType"] == "dispatch"]
    assert any(e["source"] == "crisp_dm_flow" and e["target"] == "pm" for e in dispatch_edges)


def test_build_graph_active_llm_edge():
    run = TraceRun(
        run_id="r1",
        events=[
            _evt("evt_0001", "substep.dispatch", attrs={"owner": "domain"}, mono=10),
            _evt("evt_0002", "llm.start", attrs={"communication_id": "comm_0002"}, mono=20),
        ],
    )
    graph = build_graph(run)
    animated = [e for e in graph["edges"] if e.get("animated")]
    assert len(animated) >= 1


def test_build_graph_developer_debug_llm_edge():
    """Developer LLM during DEBUG must not be attributed to the substep owner."""
    run = TraceRun(
        run_id="r1",
        events=[
            _evt("evt_0001", "substep.dispatch", attrs={"owner": "data_engineer"}, mono=10),
            _evt(
                "evt_0002",
                "agent.activate",
                name="Senior Developer & On-Call Debugger",
                attrs={
                    "role": "Senior Developer & On-Call Debugger",
                    "maads_agent": "data_engineer",
                    "agent_name": "data_engineer",
                },
                mono=20,
            ),
            _evt(
                "evt_0003",
                "llm.start",
                attrs={
                    "role": "Senior Developer & On-Call Debugger",
                    "maads_agent": "data_engineer",
                    "communication_id": "comm_debug",
                },
                mono=30,
            ),
        ],
    )
    graph = build_graph(run)
    node_ids = {n["id"] for n in graph["nodes"]}
    assert "developer" in node_ids
    llm_edges = [e for e in graph["edges"] if e["target"] == "llm"]
    assert any(e["source"] == "developer" for e in llm_edges)
    assert not any(e["source"] == "data_engineer" for e in llm_edges)


def test_build_graph_layout_centers_flow_among_agents():
    run = TraceRun(
        run_id="r1",
        events=[
            _evt("evt_0001", "substep.dispatch", attrs={"owner": "pm", "substep": "1.4"}, mono=10),
            _evt("evt_0002", "substep.dispatch", attrs={"owner": "domain", "substep": "1.1"}, mono=20),
            _evt("evt_0003", "llm.start", attrs={"communication_id": "comm_0001", "maads_agent": "pm"}, mono=30),
        ],
    )
    graph = build_graph(run)
    positions = {n["id"]: n["position"] for n in graph["nodes"]}
    assert positions["crisp_dm_flow"]["x"] < positions["pm"]["x"] < positions["llm"]["x"]
    pm_y = positions["pm"]["y"]
    domain_y = positions["domain"]["y"]
    flow_y = positions["crisp_dm_flow"]["y"]
    assert pm_y < domain_y
    assert pm_y <= flow_y <= domain_y


@pytest.mark.skipif(
    not Path("artifacts/titanic/trace/trace.json").is_file(),
    reason="titanic trace artifact not present",
)
def test_build_graph_from_titanic_artifact():
    raw = Path("artifacts/titanic/trace/trace.json").read_text(encoding="utf-8")
    run = TraceRun.model_validate_json(raw)
    graph = build_graph(run)
    assert graph["nodes"]
    assert graph["edges"]


def test_build_process_view_substep_status():
    run = TraceRun(
        run_id="r1",
        case_id="titanic",
        events=[
            _evt("evt_0001", "substep.dispatch", attrs={"substep": "1.1", "owner": "domain"}, mono=10),
            _evt("evt_0002", "substep.end", attrs={"substep": "1.1"}, mono=100),
            _evt("evt_0003", "substep.dispatch", attrs={"substep": "1.2", "owner": "domain"}, mono=200),
        ],
    )
    status = {
        "substep": "1.2",
        "substep_name": "Assess Situation",
        "phase": 1,
        "activity": "working",
        "token_spend": {"domain": 100},
    }
    snapshot = {
        "outputs_status": {"phase_1_ready": False},
        "conclusions": {},
        "config": {"problem_statement": "test"},
        "recent_log": [{"agent": "domain", "message": "ran 1.1 -> notes", "level": "info"}],
        "loop_history": [],
        "validator_findings": [],
    }
    view = build_process_view(status, run, snapshot)
    by_id = {s["id"]: s for s in view["substeps"]}
    assert by_id["1.1"]["status"] == "done"
    assert by_id["1.2"]["status"] == "active"
    assert by_id["1.3"]["status"] == "pending"
    assert view["team"][1]["id"] == "domain"  # domain is second in _AGENT_IDS
    domain = next(t for t in view["team"] if t["id"] == "domain")
    assert domain["status"] == "active"
    assert domain["current_substep"] == "1.2"
    assert len(view["phases"]) == 6
    assert view["phases"][0]["status"] == "active"


def test_build_process_view_includes_workbook_deliverable(tmp_path: Path):
    from maads.dashboard.aggregators import build_process_view
    from maads.observability.schema import TraceRun

    run_dir = tmp_path / "runs" / "agg-run"
    reports = run_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "case_workbook.ipynb").write_text("{}", encoding="utf-8")

    status = {"case_id": "titanic", "substep": "6.4", "phase": 6, "token_spend": {}}
    snapshot = {
        "outputs_status": {},
        "conclusions": {},
        "config": {},
        "recent_log": [],
        "loop_history": [],
        "validator_findings": [],
    }
    view = build_process_view(status, TraceRun(run_id="r1"), snapshot, artifact_dir=run_dir)
    wb = next(d for d in view["deliverables"] if d["label"] == "Case workbook")
    assert wb["exists"] is True
    assert wb["url"] == "/api/cases/titanic/reports/case_workbook.ipynb"
    run = TraceRun(
        run_id="r1",
        events=[
            _evt(
                "evt_0001",
                "loop",
                attrs={"label": "B", "from_phase": 4, "to_phase": 3, "reason": "low CV"},
            ),
        ],
    )
    status = {"substep": "3.1", "phase": 3, "token_spend": {}}
    snapshot = {
        "loop_history": [{
            "label": "B",
            "from_phase": 4,
            "to_phase": 3,
            "reason": "validator findings",
            "t": "2025-01-01T00:00:00+00:00",
        }],
        "outputs_status": {},
        "conclusions": {},
        "config": {},
        "recent_log": [],
        "validator_findings": ["missing train.parquet"],
    }
    view = build_process_view(status, run, snapshot)
    assert len(view["loops"]) == 2
    assert view["validator_findings"] == ["missing train.parquet"]
