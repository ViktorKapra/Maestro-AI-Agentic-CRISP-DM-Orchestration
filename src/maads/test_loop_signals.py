"""Real loop signals reach the PM: data-quality blockers and validator findings."""
from __future__ import annotations

from pathlib import Path

import pytest

from maads.agents import DataEngineerAgent
from maads.config import load_case_config
from maads.deltas import Plan
from maads.flow.phase_runner import apply_loop, validate_phase_exit
from maads.paths import resolve_path
from maads.state import CrispDMState, Phase
from maads.testing.flow_harness import make_run_context


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE", "0")
    monkeypatch.setenv("MAADS_PROGRESS", "0")
    monkeypatch.setattr("maads.agents.run_json_task", lambda *a, **k: {})
    monkeypatch.setattr("maads.codegen.run_text_task", lambda *a, **k: "")


@pytest.fixture
def state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


def test_real_quality_blockers_reach_pm_view(state: CrispDMState, tmp_path: Path):
    state.substep = "2.4"
    de = DataEngineerAgent(artifact_dir=tmp_path)
    de.act(state)
    assert state.du.data_quality_report
    blockers = state.du.data_quality_report.get("blockers", [])
    assert blockers
    pm_view = state.view_for("pm")
    assert pm_view["latest_quality_blockers"]


def test_validator_findings_populate_and_reach_pm(state: CrispDMState, tmp_path: Path):
    ctx = make_run_context(state, tmp_path)
    state.dp.dataset = {"train": "/no/such/train.parquet", "test": "/no/such/test.parquet"}
    state.dp.derived_attributes = {"items": ["FamilySize"]}

    validate_phase_exit(state, Phase.DATA_PREPARATION)

    assert state.validator_findings
    pm_view = state.view_for("pm")
    assert pm_view["validator_findings"]


def test_fire_loop_tolerates_stringy_phase(tmp_path: Path, state: CrispDMState):
    """Regression: PMs often return loop_to_phase as a string; Phase() is an IntEnum."""
    ctx = make_run_context(state, tmp_path)
    state.phase = Phase.MODELING
    apply_loop(
        ctx,
        Plan(action="loop_back", loop_to_phase=3, loop_label="B", reason="stringy target"),
    )
    assert state.phase == Phase.DATA_PREPARATION
    assert state.loop_history[-1].to_phase == 3


def test_fire_loop_clears_validator_findings(tmp_path: Path, state: CrispDMState):
    ctx = make_run_context(state, tmp_path)
    state.validator_findings = ["some deficit"]
    state.phase = Phase.MODELING
    apply_loop(
        ctx,
        Plan(
            action="loop_back",
            loop_to_phase=int(Phase.DATA_PREPARATION),
            loop_label="B",
            reason="addressing prep deficit",
        ),
    )
    assert state.validator_findings == []
    assert state.loop_history and state.loop_history[-1].label == "B"


def test_degraded_flags_reach_pm_view(state: CrispDMState):
    state.record_degraded("data_engineer@3.2: baseline fallback")
    pm_view = state.view_for("pm")
    assert pm_view["degraded_flags"]


def test_suggested_action_loop_b_on_validator_findings(state: CrispDMState):
    state.validator_findings = ["missing artifact"]
    state.substep = "5.1"
    suggested = state._suggested_pm_action()
    assert suggested is not None
    assert suggested["loop_label"] == "B"


def test_inspect_dataset_reports_column_diff(state: CrispDMState, tmp_path: Path):
    de = DataEngineerAgent(artifact_dir=tmp_path)
    state.substep = "2.2"
    de.act(state)
    assert state.du.data_description_report
