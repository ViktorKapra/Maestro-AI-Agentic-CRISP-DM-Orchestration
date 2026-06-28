"""Tests for graceful Ctrl+C shutdown."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from maads.agents import Plan
from maads.config import load_case_config
from maads.flow.phase_runner import check_global_halt, force_halt
from maads.paths import resolve_path
from maads.shutdown import (
    INTERRUPT_HALT_REASON,
    apply_interrupt_to_state,
    request_shutdown,
    reset_shutdown_state,
    shutdown_requested,
)
from maads.state import CrispDMState
from maads.testing.flow_harness import make_flow, make_run_context


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


def test_flow_halts_when_shutdown_requested(tmp_path: Path):
    reset_shutdown_state()
    request_shutdown()
    config = load_case_config(resolve_path("configs/titanic.yaml"))
    state = CrispDMState.from_config(config)
    artifact_dir = tmp_path / "titanic"
    artifact_dir.mkdir(parents=True)

    ctx = make_run_context(state, artifact_dir)
    reason = check_global_halt(ctx)
    assert reason == INTERRUPT_HALT_REASON
    force_halt(state, reason)
    assert state.halted


@patch("maads.flow.crisp_dm_flow.CrispDMFlow")
def test_cmd_run_returns_130_on_keyboard_interrupt(mock_flow_cls, tmp_path: Path):
    from maads.__main__ import cmd_run
    import argparse

    reset_shutdown_state()
    config_path = resolve_path("configs/titanic.yaml")
    mock_flow_cls.return_value.run.side_effect = KeyboardInterrupt

    args = argparse.Namespace(
        config=config_path,
        case=None,
        config_dir="configs",
        artifact_dir=str(tmp_path / "artifacts"),
        quiet=True,
        model=None,
    )
    code = cmd_run(args)
    assert code == 130
    runs_dir = tmp_path / "artifacts" / "titanic" / "runs"
    finals = list(runs_dir.glob("*/final_state.json"))
    assert finals, f"expected final_state.json under {runs_dir}"
    final = finals[0]
    assert final.is_file()
    assert INTERRUPT_HALT_REASON in final.read_text()


@patch("maads.flow.crisp_dm_flow.CrispDMFlow")
def test_cmd_run_persists_reports_on_flow_failure(mock_flow_cls, tmp_path: Path):
    from maads.__main__ import cmd_run
    import argparse

    reset_shutdown_state()
    config_path = resolve_path("configs/titanic.yaml")
    mock_flow_cls.return_value.run.side_effect = TypeError(
        "float() argument must be a string or a real number, not 'dict'"
    )

    args = argparse.Namespace(
        config=config_path,
        case=None,
        config_dir="configs",
        artifact_dir=str(tmp_path / "artifacts"),
        quiet=True,
        model=None,
    )
    code = cmd_run(args)
    assert code == 1
    runs_dir = tmp_path / "artifacts" / "titanic" / "runs"
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    assert (run_dir / "final_state.json").is_file()
    assert (run_dir / "reports" / "case_report.md").is_file()
    assert (run_dir / "reports" / ".generated").is_file()
    final = json.loads((run_dir / "final_state.json").read_text(encoding="utf-8"))
    assert final["halted"] is True
    assert "run failed" in (final.get("halt_reason") or "")
