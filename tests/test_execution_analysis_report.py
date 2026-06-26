"""Tests for per-run execution analysis report generation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from maads.artifact_paths import RunPaths, ensure_run_layout
from maads.config import load_case_config
from maads.outcome import ml_run_succeeded
from maads.paths import resolve_path
from maads.reports.writer import write_run_reports
from maads.state import CrispDMState, ModelRun, Phase


@pytest.fixture
def run_state(tmp_path: Path) -> tuple[CrispDMState, Path]:
    cfg = load_case_config(resolve_path("configs/house_prices.yaml"))
    state = CrispDMState.from_config(cfg)
    run_dir = tmp_path / "runs" / "test-run-id"
    ensure_run_layout(run_dir, run_id="test-run-id", case_id=cfg.case_id)
    state.halted = True
    state.phase = Phase.DEPLOYMENT
    state.substep = "6.4"
    state.halt_reason = "completed phase 6"
    state.md.chosen_model = ModelRun(
        technique="gradient_boosting",
        cv_score=0.1355,
        cv_std=0.0205,
        assessment="selected",
    )
    state.ev.assessment_of_dm_results = {
        "metric": "rmse_log",
        "achieved_score": 0.1355,
        "threshold": 0.15,
        "success_criterion_met": True,
    }
    state.ev.decision = "deploy"
    sub = run_dir / "submission.csv"
    sub.write_text("Id,SalePrice\n1461,100000\n", encoding="utf-8")
    state.dep.submission_path = str(sub)
    state.dep.final_report_path = str(run_dir / "final_report.md")
    (run_dir / "final_report.md").write_text("# report\n", encoding="utf-8")

    sandbox_dir = run_dir / "sandbox" / "exec"
    sandbox_dir.mkdir(parents=True, exist_ok=True)
    manifest = sandbox_dir / "manifest.jsonl"
    manifest.write_text(
        '{"substep": "4.3", "label": "data_scientist_attempt1", '
        '"script": "00002.py", "ok": false, "return_code": 1}\n'
        '{"substep": "4.3", "label": "data_scientist_attempt2", '
        '"script": "00003.py", "ok": true, "return_code": 0}\n',
        encoding="utf-8",
    )
    return state, run_dir


def test_write_run_reports_emits_execution_analysis(run_state):
    state, run_dir = run_state
    write_run_reports(state, run_dir, force=True)
    paths = RunPaths(run_dir)
    json_path = paths.reports / "execution_analysis.json"
    md_path = paths.reports / "execution_analysis.md"
    assert json_path.is_file()
    assert md_path.is_file()
    bundle = json.loads(json_path.read_text(encoding="utf-8"))
    assert bundle["run_id"] == "test-run-id"
    assert bundle["case_id"] == "house_prices"
    assert bundle["ml_success"] is True
    assert bundle["success_criterion"]["met"] is True
    assert bundle["sandbox"]["failures"] == 1
    assert len(bundle["sandbox_failures"]) == 1
    md = md_path.read_text(encoding="utf-8")
    assert "Execution Analysis" in md
    assert "house_prices" in md
    assert "gradient_boosting" in md
    assert ml_run_succeeded(state)
