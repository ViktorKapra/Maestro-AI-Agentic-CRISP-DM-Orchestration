"""Tests for Runtime Execution Intelligence."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maads.agents import Plan
from maads.config import load_case_config
from maads.observability.bootstrap import auto_enable, begin_run, end_run, flush_trace
from maads.observability.collector import reset_collector
from maads.observability.exporter import export_trace, write_trace_artifacts
from maads.observability.render.agent_interaction import render_agent_interaction
from maads.observability.render.call_tree import render_call_tree
from maads.observability.render.mermaid_flowchart import render_flowchart
from maads.observability.render.mermaid_sequence import render_sequence
from maads.observability.render.narrative import render_narrative
from maads.observability.render.timeline import render_timeline
from maads.observability.schema import TraceEvent, TraceRun
from maads.flow.crisp_dm_flow import CrispDMFlow
from maads.state import CrispDMState
from maads.paths import repo_root
from maads.testing.fake_llm import fake_llm_response

REPO_ROOT = repo_root()


@pytest.fixture(autouse=True)
def enable_trace(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE", "1")
    monkeypatch.setenv("MAADS_TRACE_PYTHON_DEPTH", "3")
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")


def _sample_run() -> TraceRun:
    events = [
        TraceEvent(id="evt_0001", type="run.start", name="Orchestrator.run", ts_mono_ms=0),
        TraceEvent(
            id="evt_0002", parent_id="evt_0001", type="substep.dispatch",
            name="Determine Business Objectives", ts_mono_ms=10,
            attributes={"substep": "1.1", "owner": "domain"},
        ),
        TraceEvent(
            id="evt_0003", parent_id="evt_0002", type="crew.start",
            name="Crew kickoff", ts_mono_ms=15,
            attributes={"agent_name": "domain", "substep": "1.1"},
        ),
        TraceEvent(
            id="evt_0004", parent_id="evt_0003", type="llm.end",
            name="LLMCall", ts_mono_ms=100, duration_ms=85,
            attributes={"total_tokens": 42},
        ),
        TraceEvent(
            id="evt_0005", parent_id="evt_0001", type="python.subprocess",
            name="PythonExec.run", ts_mono_ms=200,
            attributes={"return_code": 0, "ok": True},
        ),
        TraceEvent(
            id="evt_0006", parent_id="evt_0001", type="substep.dispatch",
            name="Plan Deployment", ts_mono_ms=500,
            attributes={"substep": "6.1", "owner": "developer"},
        ),
        TraceEvent(id="evt_0007", parent_id="evt_0001", type="run.end", name="done", ts_mono_ms=600),
    ]
    return TraceRun(run_id="test-run", case_id="titanic", events=events)


def test_emit_end_survives_different_context():
    """CrewAI callbacks can end spans outside the context where they started."""
    import contextvars

    coll = reset_collector()
    coll.start_run("titanic")
    coll.emit_start("llm.start", span_key="crewai.llm.x", name="LLM")

    other_ctx = contextvars.copy_context()
    other_ctx.run(lambda: coll.emit_end("llm.end", span_key="crewai.llm.x"))

    run = coll.to_trace_run()
    assert len(run.events) == 2
    assert run.events[1].type == "llm.end"


def test_collector_parent_child():
    coll = reset_collector()
    coll.start_run("titanic")
    parent = coll.emit("run.start", name="test")
    child = coll.emit("substep.dispatch", parent_id=parent, name="1.1")
    run = coll.to_trace_run()
    assert run.case_id == "titanic"
    assert len(run.events) == 2
    assert run.events[1].parent_id == parent
    assert run.events[1].id == child


def test_renderers_produce_output():
    run = _sample_run()
    assert "run.start" in render_timeline(run)
    assert "evt_0001" in render_call_tree(run) or "run.start" in render_call_tree(run)
    assert "sequenceDiagram" in render_sequence(run)
    assert "flowchart TD" in render_flowchart(run)
    assert "flowchart LR" in render_agent_interaction(run)
    assert "workflow started" in render_narrative(run).lower()


def test_flush_trace_keeps_run_open(tmp_path: Path):
    coll = reset_collector()
    coll.start_run("titanic")
    coll.emit("run.start", name="Orchestrator.run")
    out = tmp_path / "trace"

    write_trace_artifacts(coll, out, finalize=False)
    assert (out / "trace.json").exists()
    assert coll.run is not None
    assert coll.run.ended_at is None

    coll.emit("substep.dispatch", name="1.1", attributes={"substep": "1.1"})
    flush_trace(out)
    data = json.loads((out / "trace.json").read_text())
    assert len(data["events"]) == 2
    assert data["ended_at"] is None

    export_trace(coll, out)
    data = json.loads((out / "trace.json").read_text())
    assert data["ended_at"] is not None


def test_export_writes_all_artefacts(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MAADS_WRITE_RENDERS", "1")
    coll = reset_collector()
    coll.start_run("titanic")
    coll.emit("run.start", name="Orchestrator.run")
    coll.emit("substep.dispatch", name="1.1", attributes={"substep": "1.1", "owner": "domain"})
    out = tmp_path / "trace"
    path = export_trace(coll, out)
    assert path.exists()
    for name in (
        "trace.json", "timeline.md", "call_tree.txt",
        "sequence.mmd", "flowchart.mmd", "agent_interaction.mmd", "narrative.md",
    ):
        assert (out / name).exists(), f"missing {name}"
    assert (tmp_path / "derived" / "trace.json").is_file()
    data = json.loads(path.read_text())
    assert data["case_id"] == "titanic"
    assert len(data["events"]) >= 2


@patch("maads.agents.run_json_task")
def test_integration_flow_trace(mock_llm, tmp_path: Path):
    mock_llm.side_effect = fake_llm_response

    auto_enable()
    cfg = load_case_config(REPO_ROOT / "configs" / "titanic.yaml")
    state = CrispDMState.from_config(cfg)
    artifact_dir = tmp_path / "artifacts" / "titanic"
    artifact_dir.mkdir(parents=True)

    begin_run(cfg.case_id, artifact_dir)
    flow = CrispDMFlow(state, artifact_dir)
    plans = [Plan(action="advance", reason="ok") for _ in range(60)]
    plan_iter = iter(plans)
    flow._pm.plan = lambda _s: next(plan_iter, Plan(action="halt", reason="done"))  # type: ignore[method-assign]
    state = flow.run()
    end_run(artifact_dir)

    trace_dir = artifact_dir / "trace"
    trace_path = trace_dir / "trace.json"
    assert trace_path.exists()
    data = json.loads(trace_path.read_text())
    types = {e["type"] for e in data["events"]}
    assert "run.start" in types
    assert "substep.dispatch" in types
    assert "python.subprocess" in types

    substeps = {
        e.get("attributes", {}).get("substep")
        for e in data["events"]
        if e.get("attributes", {}).get("substep")
    }
    assert "5.1" in substeps or "6.1" in substeps

    assert state.dep.submission_path


def test_smoke_with_trace_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE", "0")
    from maads.observability.bootstrap import is_enabled
    assert is_enabled() is False
