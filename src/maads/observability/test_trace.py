"""Tests for Runtime Execution Intelligence."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maads.config import load_case_config
from maads.observability.bootstrap import auto_enable, begin_run, end_run
from maads.observability.collector import reset_collector
from maads.observability.exporter import export_trace
from maads.observability.render.agent_interaction import render_agent_interaction
from maads.observability.render.call_tree import render_call_tree
from maads.observability.render.mermaid_flowchart import render_flowchart
from maads.observability.render.mermaid_sequence import render_sequence
from maads.observability.render.narrative import render_narrative
from maads.observability.render.timeline import render_timeline
from maads.observability.schema import TraceEvent, TraceRun
from maads.orchestrator import Orchestrator
from maads.state import CrispDMState

REPO_ROOT = Path(__file__).resolve().parents[3]


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


def test_export_writes_all_artefacts(tmp_path: Path):
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
    data = json.loads(path.read_text())
    assert data["case_id"] == "titanic"
    assert len(data["events"]) >= 2


@patch("maads.agents.run_json_task")
def test_integration_orchestrator_trace(mock_llm, tmp_path: Path):
    def _fake_llm(agent_name, instruction, state, schema_hint):
        if state.substep == "1.1":
            return {
                "background": "test",
                "business_objectives": "obj",
                "business_success_criteria": "crit",
            }
        if state.substep == "1.3":
            return {
                "data_mining_goals": "goal",
                "data_mining_success_criteria": "crit",
            }
        return {}

    mock_llm.side_effect = _fake_llm

    auto_enable()
    cfg = load_case_config(REPO_ROOT / "configs" / "titanic.yaml")
    state = CrispDMState.from_config(cfg)
    artifact_dir = tmp_path / "artifacts" / "titanic"
    artifact_dir.mkdir(parents=True)

    begin_run(cfg.case_id, artifact_dir)
    state = Orchestrator(state, artifact_dir).run()
    end_run(artifact_dir)

    trace_dir = artifact_dir / "trace"
    trace_path = trace_dir / "trace.json"
    assert trace_path.exists()
    data = json.loads(trace_path.read_text())
    types = {e["type"] for e in data["events"]}
    assert "run.start" in types
    assert "substep.dispatch" in types
    assert "python.subprocess" in types

    timeline = (trace_dir / "timeline.md").read_text()
    assert "1.1" in timeline
    assert "6.1" in timeline or any(
        e.get("attributes", {}).get("substep") == "6.1" for e in data["events"]
    )

    assert state.dep.submission_path


def test_smoke_with_trace_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE", "0")
    from maads.observability.bootstrap import is_enabled
    assert is_enabled() is False
