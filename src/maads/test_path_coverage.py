"""Path-coverage scenarios: mocked LLM, real sklearn snippets, no hour-long runs."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from maads.agents import Plan, ProjectManagerAgent
from maads.config import load_case_config
from maads.crew import CrewKickoffError
from maads.orchestrator import Orchestrator
from maads.paths import resolve_path
from maads.state import SUBSTEPS, CrispDMState, Phase
from maads.testing.fake_llm import fake_llm_response


@pytest.fixture
def titanic_state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


@pytest.fixture(autouse=True)
def fast_run(monkeypatch: pytest.MonkeyPatch):
    """Disable trace I/O during coverage runs."""
    monkeypatch.setenv("MAADS_TRACE", "0")
    monkeypatch.setenv("MAADS_PROGRESS", "0")
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    # DE/DS author code via run_text_task; without a live LLM, return no code so
    # run_authored_code deterministically falls back to the fixed sklearn snippets
    # (the "real snippets" these path-coverage tests already rely on).
    monkeypatch.setattr("maads.codegen.run_text_task", lambda *a, **k: "")


def _artifact_dir(tmp_path: Path) -> Path:
    d = tmp_path / "artifacts" / "titanic"
    d.mkdir(parents=True)
    return d


def _all_substeps() -> list[str]:
    out: list[str] = []
    for phase in Phase:
        out.extend(SUBSTEPS[phase])
    return out


@patch("maads.agents.run_json_task")
def test_happy_path_all_substeps(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    mock_llm.side_effect = fake_llm_response
    artifact_dir = _artifact_dir(tmp_path)
    dispatched: list[str] = []

    orch = Orchestrator(titanic_state, artifact_dir)
    orig_dispatch = orch._dispatch

    def track(substep: str) -> None:
        dispatched.append(substep)
        orig_dispatch(substep)

    orch._dispatch = track  # type: ignore[method-assign]

    plans = [Plan(action="advance", reason="ok") for _ in range(60)]
    plan_iter = iter(plans)
    orch.pm.plan = lambda _s: next(plan_iter, Plan(action="halt", reason="done"))  # type: ignore[method-assign]

    orch.run()

    assert titanic_state.dep.submission_path
    assert titanic_state.dep.experience_documentation
    assert set(dispatched) == set(_all_substeps())
    assert dispatched == _all_substeps()


@patch("maads.agents.run_json_task")
def test_loop_back_fires_and_records_history(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    mock_llm.side_effect = fake_llm_response
    artifact_dir = _artifact_dir(tmp_path)
    orch = Orchestrator(titanic_state, artifact_dir)

    plans = iter([
        Plan(action="advance", reason="run 1.1"),
        Plan(
            action="loop_back",
            loop_label="B",
            loop_to_phase=3,
            target_substep="3.1",
            reason="revisit prep",
        ),
        Plan(action="halt", reason="stop after loop"),
    ])
    orch.pm.plan = lambda _s: next(plans)  # type: ignore[method-assign]

    orch.run()

    assert titanic_state.loop_history
    assert titanic_state.loop_history[0].label == "B"
    assert titanic_state.phase == Phase.DATA_PREPARATION
    assert titanic_state.substep == "3.1"


@patch("maads.agents.run_json_task")
def test_pm_halt_stops_run(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    mock_llm.side_effect = fake_llm_response
    artifact_dir = _artifact_dir(tmp_path)
    orch = Orchestrator(titanic_state, artifact_dir)
    orch.pm.plan = lambda _s: Plan(action="halt", reason="user stop")  # type: ignore[method-assign]

    orch.run()

    assert titanic_state.halted
    assert titanic_state.halt_reason == "user stop"


@patch("maads.agents.run_json_task")
def test_dispatch_exception_halts(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    mock_llm.side_effect = fake_llm_response
    artifact_dir = _artifact_dir(tmp_path)
    orch = Orchestrator(titanic_state, artifact_dir)

    def boom(_substep: str) -> None:
        raise RuntimeError("snippet failed")

    orch._dispatch = boom  # type: ignore[method-assign]
    orch.pm.plan = lambda _s: Plan(action="advance", reason="ok")  # type: ignore[method-assign]

    orch.run()

    assert titanic_state.halted
    assert "dispatch failed" in (titanic_state.halt_reason or "")


@patch("maads.agents.run_json_task")
def test_hard_cap_halts(mock_llm, titanic_state: CrispDMState, tmp_path: Path, monkeypatch):
    mock_llm.side_effect = fake_llm_response
    monkeypatch.setattr("maads.orchestrator.MAX_PHASE_TRANSITIONS", 0)
    artifact_dir = _artifact_dir(tmp_path)
    orch = Orchestrator(titanic_state, artifact_dir)
    orch.pm.plan = lambda _s: Plan(action="advance", reason="ok")  # type: ignore[method-assign]

    orch.run()

    assert titanic_state.halted
    assert titanic_state.halt_reason == "hard cap exceeded"


@patch("maads.agents.run_json_task")
def test_token_budget_halts(mock_llm, titanic_state: CrispDMState, tmp_path: Path, monkeypatch):
    mock_llm.side_effect = fake_llm_response
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "100")
    titanic_state.token_spend["pm"] = 100
    artifact_dir = _artifact_dir(tmp_path)
    orch = Orchestrator(titanic_state, artifact_dir)
    orch.pm.plan = lambda _s: Plan(action="advance", reason="ok")  # type: ignore[method-assign]

    orch.run()

    assert titanic_state.halted
    assert titanic_state.halt_reason == "token budget exceeded"


@patch("maads.agents.run_json_task")
def test_prereq_skip_does_not_run_agent(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    mock_llm.side_effect = fake_llm_response
    titanic_state.substep = "1.4"
    assert titanic_state.substep_prereqs_satisfied("1.4") is False
    artifact_dir = _artifact_dir(tmp_path)
    orch = Orchestrator(titanic_state, artifact_dir)
    plans = iter([
        Plan(action="advance", reason="try 1.4"),
        Plan(action="halt", reason="stop"),
    ])
    orch.pm.plan = lambda _s: next(plans)  # type: ignore[method-assign]

    orch.run()

    assert not titanic_state.bu.project_plan
    assert any("prereqs not satisfied for 1.4" in e.message for e in titanic_state.log)


@patch("maads.agents.run_json_task")
def test_pm_plan_halts_on_llm_failure(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    mock_llm.side_effect = CrewKickoffError("timeout")
    pm = ProjectManagerAgent(artifact_dir=_artifact_dir(tmp_path))
    plan = pm.plan(titanic_state)
    assert plan.action == "halt"
    assert "PM LLM call failed" in plan.reason


@patch("maads.agents.run_json_task")
def test_pm_halt_before_6_4_runs_review(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    """PM must not skip 6.4 when submission and report already exist."""
    mock_llm.side_effect = fake_llm_response
    artifact_dir = _artifact_dir(tmp_path)
    titanic_state.phase = Phase.DEPLOYMENT
    titanic_state.substep = "6.4"
    titanic_state.dep.submission_path = str(artifact_dir / "submission.csv")
    titanic_state.dep.final_report_path = str(artifact_dir / "final_report.md")
    orch = Orchestrator(titanic_state, artifact_dir)
    orch.pm.plan = lambda _s: Plan(  # type: ignore[method-assign]
        action="halt",
        reason="Phase 6 completion requirements are met: phase_6_ready is true.",
    )

    orch.run()

    assert titanic_state.dep.experience_documentation
    assert any("ignored PM halt" in e.message for e in titanic_state.log)
    assert titanic_state.halted
    assert titanic_state.halt_reason == "completed phase 6"


@patch("maads.agents.run_json_task")
def test_loop_blocked_when_cap_reached(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    mock_llm.side_effect = fake_llm_response
    artifact_dir = _artifact_dir(tmp_path)
    orch = Orchestrator(titanic_state, artifact_dir)
    orch._inner_loop_count = 3  # at MAX_INNER_LOOP_ITERATIONS

    plans = iter([
        Plan(
            action="loop_back",
            loop_label="B",
            loop_to_phase=3,
            reason="should block",
        ),
        Plan(action="halt", reason="stop"),
    ])
    orch.pm.plan = lambda _s: next(plans)  # type: ignore[method-assign]

    orch.run()

    assert not titanic_state.loop_history
    assert any("loop blocked" in e.message for e in titanic_state.log)
