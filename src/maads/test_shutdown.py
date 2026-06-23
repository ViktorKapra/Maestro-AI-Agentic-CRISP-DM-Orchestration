"""Tests for graceful Ctrl+C shutdown."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from maads.agents import Plan
from maads.config import load_case_config
from maads.orchestrator import Orchestrator
from maads.paths import resolve_path
from maads.shutdown import (
    INTERRUPT_HALT_REASON,
    apply_interrupt_to_state,
    request_shutdown,
    reset_shutdown_state,
    shutdown_requested,
)
from maads.state import CrispDMState


def test_shutdown_flag():
    reset_shutdown_state()
    assert not shutdown_requested()
    request_shutdown()
    assert shutdown_requested()


def test_apply_interrupt_to_state():
    config = load_case_config(resolve_path("configs/titanic.yaml"))
    state = CrispDMState.from_config(config)
    reason = apply_interrupt_to_state(state)
    assert reason == INTERRUPT_HALT_REASON
    assert state.halted
    assert state.halt_reason == INTERRUPT_HALT_REASON


def test_orchestrator_halts_when_shutdown_requested(tmp_path: Path):
    reset_shutdown_state()
    request_shutdown()
    config = load_case_config(resolve_path("configs/titanic.yaml"))
    state = CrispDMState.from_config(config)
    artifact_dir = tmp_path / "titanic"
    artifact_dir.mkdir(parents=True)

    dispatched: list[str] = []
    orch = Orchestrator(state, artifact_dir)
    orch._dispatch = lambda substep: dispatched.append(substep)  # type: ignore[method-assign]
    orch.pm.plan = lambda _s: Plan(action="advance", reason="keep going")  # type: ignore[method-assign]

    result = orch.run()

    assert result.halted
    assert result.halt_reason == INTERRUPT_HALT_REASON
    assert dispatched == []


@patch("maads.__main__.Orchestrator")
def test_cmd_run_returns_130_on_keyboard_interrupt(mock_orch_cls, tmp_path: Path):
    from maads.__main__ import cmd_run
    import argparse

    reset_shutdown_state()
    config_path = resolve_path("configs/titanic.yaml")
    mock_orch_cls.return_value.run.side_effect = KeyboardInterrupt

    args = argparse.Namespace(
        config=config_path,
        case=None,
        config_dir="configs",
        artifact_dir=str(tmp_path / "artifacts"),
        quiet=True,
    )
    code = cmd_run(args)
    assert code == 130
    final = tmp_path / "artifacts" / "titanic" / "final_state.json"
    assert final.is_file()
    assert INTERRUPT_HALT_REASON in final.read_text()
