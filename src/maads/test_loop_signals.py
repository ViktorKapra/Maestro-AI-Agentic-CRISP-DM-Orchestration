"""Real loop signals reach the PM: data-quality blockers and validator findings.

These prove the *conditions* that make the PM fire loops are genuinely produced
from data/artifacts (not hardcoded), which is what was missing when loop_history
stayed empty. The PM's LLM decision itself is exercised by the mocked-Plan tests
in test_path_coverage.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from maads.agents import DataEngineerAgent
from maads.config import load_case_config
from maads.orchestrator import Orchestrator
from maads.paths import resolve_path
from maads.state import CrispDMState, Phase


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE", "0")
    monkeypatch.setenv("MAADS_PROGRESS", "0")
    # No live LLM: DE narration returns nothing; authored code returns nothing so
    # the executor falls back to the real quality snippet.
    monkeypatch.setattr("maads.agents.run_json_task", lambda *a, **k: {})
    monkeypatch.setattr("maads.codegen.run_text_task", lambda *a, **k: "")


@pytest.fixture
def state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


def test_real_quality_blockers_reach_pm_view(tmp_path: Path, state: CrispDMState):
    """DE 2.4 computes genuine blockers from the data (Titanic's Cabin is ~77% missing)."""
    state.phase = Phase.DATA_UNDERSTANDING
    state.substep = "2.4"
    de = DataEngineerAgent(artifact_dir=tmp_path)
    de.act(state)

    report = state.du.data_quality_report or {}
    blockers = report.get("blockers") or []
    assert any("Cabin" in b for b in blockers), f"expected a Cabin blocker, got {blockers}"

    # The PM sees it -> this is the Loop A trigger.
    pm_view = state.view_for("pm")
    assert pm_view["latest_quality_blockers"]


def test_validator_findings_populate_and_reach_pm(tmp_path: Path, state: CrispDMState):
    """A prep deficit found at the 3->4 transition lands in validator_findings."""
    orch = Orchestrator(state, tmp_path)
    # Claim a derived feature that the (absent) parquet cannot contain.
    state.dp.dataset = {"train": "/no/such/train.parquet", "test": "/no/such/test.parquet"}
    state.dp.derived_attributes = {"items": ["FamilySize"]}

    orch._validate_on_transition(Phase.DATA_PREPARATION)

    assert state.validator_findings, "expected validator to record deficits"
    pm_view = state.view_for("pm")
    assert pm_view["validator_findings"]  # Loop B trigger visible to the PM


def test_fire_loop_tolerates_stringy_phase(tmp_path: Path, state: CrispDMState):
    """Regression: PMs often return loop_to_phase as a string; Phase() is an IntEnum."""
    orch = Orchestrator(state, tmp_path)
    state.phase = Phase.MODELING
    orch._fire_loop("3", "stringy target from LLM", "B")  # type: ignore[arg-type]
    assert state.phase == Phase.DATA_PREPARATION
    assert state.loop_history[-1].to_phase == 3


def test_fire_loop_clears_validator_findings(tmp_path: Path, state: CrispDMState):
    orch = Orchestrator(state, tmp_path)
    state.validator_findings = ["some deficit"]
    state.phase = Phase.MODELING
    orch._fire_loop(int(Phase.DATA_PREPARATION), "addressing prep deficit", "B")
    assert state.validator_findings == []
    assert state.loop_history and state.loop_history[-1].label == "B"
