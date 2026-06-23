"""Tests for orchestrator advance semantics and related fixes."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maads.agents import Plan
from maads.config import load_case_config
from maads.crew import _check_token_budget
from maads.orchestrator import Orchestrator
from maads.paths import repo_root, resolve_path
from maads.state import CrispDMState, Phase


@pytest.fixture
def titanic_state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


def test_advance_recovers_desynced_phase_substep(titanic_state: CrispDMState, tmp_path: Path):
    """Phase/substep mismatch must not crash _advance_substep."""
    titanic_state.phase = Phase.DATA_PREPARATION
    titanic_state.substep = "4.1"
    artifact_dir = tmp_path / "artifacts" / "titanic"
    artifact_dir.mkdir(parents=True)
    orch = Orchestrator(titanic_state, artifact_dir)

    orch._advance_substep()

    assert titanic_state.phase == Phase.MODELING
    assert titanic_state.substep == "4.2"


def test_advance_dispatches_current_substep_not_pm_target(
    titanic_state: CrispDMState, tmp_path: Path,
):
    """PM target_substep on advance must not skip the current substep."""
    artifact_dir = tmp_path / "artifacts" / "titanic"
    artifact_dir.mkdir(parents=True)
    orch = Orchestrator(titanic_state, artifact_dir)
    dispatched: list[str] = []

    def track_dispatch(substep: str) -> None:
        dispatched.append(substep)

    plans = iter([
        Plan(action="advance", target_substep="1.2", reason="PM tried to skip"),
        Plan(action="halt", reason="stop after one iteration"),
    ])
    orch.pm.plan = lambda _state: next(plans)  # type: ignore[method-assign]
    orch._dispatch = track_dispatch  # type: ignore[method-assign]

    orch.run()

    assert dispatched == ["1.1"]
    assert any("ignored PM target_substep" in e.message for e in titanic_state.log)


def test_substep_1_4_requires_data_mining_goals(titanic_state: CrispDMState):
    assert titanic_state.substep_prereqs_satisfied("1.4") is False
    titanic_state.bu.data_mining_goals = "goal"
    assert titanic_state.substep_prereqs_satisfied("1.4") is True


def test_load_case_config_resolves_data_paths_against_repo_root():
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    root = repo_root()
    assert Path(cfg.data.train_csv).is_absolute()
    assert str(root) in cfg.data.train_csv


def test_resolve_path_from_src_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    monkeypatch.chdir(src)
    p = resolve_path("data/titanic/train.csv")
    assert p == repo_root() / "data/titanic/train.csv"


def test_token_budget_raises_when_exceeded(
    titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "100")
    titanic_state.token_spend["pm"] = 100
    with pytest.raises(RuntimeError, match="token cap"):
        _check_token_budget(titanic_state)


@patch("maads.agents.run_json_task")
def test_pm_plan_halts_on_llm_failure(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    from maads.agents import ProjectManagerAgent
    from maads.crew import CrewKickoffError

    mock_llm.side_effect = CrewKickoffError("timeout")
    pm = ProjectManagerAgent(artifact_dir=tmp_path)
    plan = pm.plan(titanic_state)
    assert plan.action == "halt"
    assert "PM LLM call failed" in plan.reason


@patch("maads.agents.run_json_task")
def test_phase1_domain_llm_substeps_run_in_order(
    mock_llm, titanic_state: CrispDMState, tmp_path: Path,
):
    """Integration: mocked LLM fills domain substeps; orchestrator visits 1.1 before 1.2."""

    def _fake_llm(agent_name, instruction, state, schema_hint=""):
        if state.substep == "1.1":
            return {
                "business_objectives": "obj",
                "situation_assessment": {
                    "resources": [],
                    "requirements": [],
                    "assumptions": [],
                    "constraints": [],
                    "risks": [],
                    "terminology": [],
                    "costs_or_tradeoffs": [],
                    "expected_benefits": [],
                },
                "data_mining_goal": "goal",
                "success_criterion": {
                    "metric": "accuracy",
                    "target_value": "0.77",
                    "direction": "maximize",
                },
                "data_description_notes": [],
                "feature_hints": [],
                "domain_data_quality_flags": [],
                "loop_a_recommendation": {"should_trigger": False, "reason": ""},
                "assumptions": [],
                "open_questions": [],
            }
        if agent_name == "pm":
            return {"action": "advance", "target_substep": None, "reason": "ok"}
        return {}

    mock_llm.side_effect = _fake_llm

    artifact_dir = tmp_path / "artifacts" / "titanic"
    artifact_dir.mkdir(parents=True)
    dispatched: list[str] = []
    orch = Orchestrator(titanic_state, artifact_dir)
    orig = orch._dispatch

    def track(substep: str) -> None:
        dispatched.append(substep)
        orig(substep)

    orch._dispatch = track  # type: ignore[method-assign]

    # Run through phase 1 only — halt once we reach phase 2.
    plans = []
    for _ in range(30):
        plans.append(Plan(action="advance", reason="ok"))
    plans.append(Plan(action="halt", reason="stop"))
    plan_iter = iter(plans)
    orch.pm.plan = lambda _s: next(plan_iter)  # type: ignore[method-assign]

    orch.run()

    assert dispatched.index("1.1") < dispatched.index("1.2")
    assert "1.1" in dispatched
    assert "1.3" in dispatched
    assert titanic_state.bu.business_objectives == "obj"
    assert titanic_state.bu.data_mining_goals == "goal"
