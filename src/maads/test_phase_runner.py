"""Tests for shared phase_runner primitives."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from maads.config import load_case_config
from maads.deltas import Plan
from maads.flow.phase_runner import (
    RunContext,
    advance_substep,
    apply_loop,
    can_fire_loop,
    deployment_review_pending,
    force_halt,
    resolve_plan,
    run_substep,
)
from maads.paths import resolve_path
from maads.state import CrispDMState, Phase


@pytest.fixture
def titanic_state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


def _ctx(state: CrispDMState, tmp_path: Path) -> RunContext:
    pm = MagicMock()
    pm.plan.return_value = Plan(action="advance", reason="test")
    agents = {
        "domain": MagicMock(),
        "pm": pm,
        "data_engineer": MagicMock(),
        "data_scientist": MagicMock(act=MagicMock(return_value=__import__("maads.deltas", fromlist=["StateDelta"]).StateDelta(notes="skip"))),
        "developer": MagicMock(),
    }
    artifact = tmp_path / "artifacts"
    artifact.mkdir(parents=True)
    return RunContext.create(state, artifact, agents, pm)


def test_advance_substep_moves_within_phase(titanic_state: CrispDMState, tmp_path: Path):
    ctx = _ctx(titanic_state, tmp_path)
    assert titanic_state.substep == "1.1"
    assert advance_substep(ctx) is False
    assert titanic_state.substep == "1.2"


def test_resolve_plan_mechanical_outside_checkpoints(titanic_state: CrispDMState, tmp_path: Path):
    ctx = _ctx(titanic_state, tmp_path)
    titanic_state.substep = "1.2"
    plan = resolve_plan(ctx)
    assert plan.action == "advance"
    ctx.pm.plan.assert_not_called()


def test_apply_loop_records_history(titanic_state: CrispDMState, tmp_path: Path):
    ctx = _ctx(titanic_state, tmp_path)
    titanic_state.phase = Phase.DATA_PREPARATION
    titanic_state.substep = "3.1"
    apply_loop(
        ctx,
        Plan(action="loop_back", loop_to_phase=1, loop_label="A", reason="quality"),
    )
    assert titanic_state.phase == Phase.BUSINESS_UNDERSTANDING
    assert len(titanic_state.loop_history) == 1


def test_can_fire_loop_respects_inner_cap(titanic_state: CrispDMState, tmp_path: Path):
    ctx = _ctx(titanic_state, tmp_path)
    ctx.inner_loop_count = 3
    plan = Plan(action="loop_back", loop_to_phase=3, loop_label="B", reason="x")
    assert can_fire_loop(ctx, plan) is False


def test_deployment_review_pending(titanic_state: CrispDMState):
    titanic_state.phase = Phase.DEPLOYMENT
    titanic_state.dep.experience_documentation = ""
    assert deployment_review_pending(titanic_state) is True


def test_run_substep_skips_when_prereqs_missing(titanic_state: CrispDMState, tmp_path: Path):
    ctx = _ctx(titanic_state, tmp_path)
    titanic_state.phase = Phase.BUSINESS_UNDERSTANDING
    titanic_state.substep = "4.1"
    run_substep(ctx, "4.1")
    ctx.agents["data_scientist"].act.assert_not_called()


def test_force_halt_sets_state(titanic_state: CrispDMState):
    force_halt(titanic_state, "test halt")
    assert titanic_state.halted is True
    assert titanic_state.halt_reason == "test halt"
