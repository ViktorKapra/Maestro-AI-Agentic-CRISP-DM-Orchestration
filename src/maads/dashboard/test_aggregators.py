"""Tests for dashboard aggregators."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from maads.dashboard.aggregators import build_graph, filter_timeline_events, trace_summary
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
    assert "orchestrator" in node_ids
    assert "llm" in node_ids
    llm_edges = [e for e in graph["edges"] if e["target"] == "llm"]
    assert any(e["source"] == "pm" for e in llm_edges)


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
