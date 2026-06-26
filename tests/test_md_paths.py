"""Tests for relative markdown paths in reports."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from maads.artifact_paths import RunPaths, ensure_run_layout
from maads.config import load_case_config
from maads.paths import resolve_path
from maads.reports.case_report import build_case_report, render_case_report_md
from maads.reports.execution_analysis import build_execution_analysis, render_execution_analysis_md
from maads.reports.final_report import build_story_spec_from_bundle, render_final_report_md
from maads.reports.handoff import build_handoff_zip
from maads.reports.md_paths import relative_md_path
from maads.reports.writer import write_run_reports
from maads.state import CrispDMState, EvaluationBundle, ModelRun, Phase


def _state_with_figures(run_dir: Path) -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    state = CrispDMState.from_config(cfg)
    fig = run_dir / "figures" / "confusion_matrix.png"
    fig.parent.mkdir(parents=True, exist_ok=True)
    fig.write_bytes(b"png")
    bundle = EvaluationBundle(
        problem_type="binary_classification",
        metrics={"accuracy": 0.82},
        confusion_matrix=[[10, 2], [3, 5]],
        class_labels=dict(cfg.class_labels),
        cv={"mean": 0.80, "std": 0.02, "n_folds": 5},
        figures=[str(fig.resolve())],
        warnings=[],
    )
    state.md.chosen_model = ModelRun(
        technique="gradient_boosting",
        cv_score=0.80,
        cv_std=0.02,
        assessment="selected",
        evaluation_bundle=bundle,
    )
    sub = run_dir / "submission.csv"
    sub.write_text("id,pred\n1,0\n", encoding="utf-8")
    state.dep.submission_path = str(sub.resolve())
    state.dep.final_report_path = str((run_dir / "final_report.md").resolve())
    state.dep.figures_dir = str(fig.parent.resolve())
    return state


def test_relative_md_path_from_reports_dir(tmp_path: Path):
    run_dir = tmp_path / "runs" / "rel-paths"
    ensure_run_layout(run_dir, run_id="rel-paths", case_id="titanic")
    sub = run_dir / "submission.csv"
    sub.write_text("x\n", encoding="utf-8")
    rel = relative_md_path(
        str(sub.resolve()),
        md_dir=run_dir / "reports",
        run_dir=run_dir,
    )
    assert rel == "../submission.csv"


def test_case_report_uses_relative_submission_link(tmp_path: Path):
    run_dir = tmp_path / "runs" / "case-md"
    ensure_run_layout(run_dir, run_id="case-md", case_id="titanic")
    state = _state_with_figures(run_dir)
    report = build_case_report(state)
    md = render_case_report_md(
        report,
        md_dir=run_dir / "reports",
        run_dir=run_dir,
    )
    assert "/Users/" not in md
    assert "[submission.csv](../submission.csv)" in md


def test_execution_analysis_uses_relative_deliverable_links(tmp_path: Path):
    run_dir = tmp_path / "runs" / "exec-md"
    ensure_run_layout(run_dir, run_id="exec-md", case_id="titanic")
    state = _state_with_figures(run_dir)
    (run_dir / "train.parquet").write_bytes(b"")
    (run_dir / "test.parquet").write_bytes(b"")
    state.dp.dataset = {"train": str(run_dir / "train.parquet"), "test": str(run_dir / "test.parquet")}
    analysis = build_execution_analysis(state, RunPaths(run_dir))
    md = render_execution_analysis_md(
        analysis,
        md_dir=run_dir / "reports",
        run_dir=run_dir,
    )
    assert "/Users/" not in md
    assert "[submission.csv](../submission.csv)" in md
    assert "[train.parquet](../train.parquet)" in md
    assert "[figures](../figures)" in md


def test_final_report_uses_relative_figure_links(tmp_path: Path):
    run_dir = tmp_path / "runs" / "final-md"
    ensure_run_layout(run_dir, run_id="final-md", case_id="titanic")
    state = _state_with_figures(run_dir)
    spec = build_story_spec_from_bundle(state)
    md = render_final_report_md(state, spec, artifact_dir=run_dir)
    assert "/Users/" not in md
    assert "![Confusion Matrix](figures/confusion_matrix.png)" in md
    assert "[submission.csv](submission.csv)" in md


def test_write_run_reports_emits_relative_links(tmp_path: Path):
    run_dir = tmp_path / "runs" / "writer-md"
    ensure_run_layout(run_dir, run_id="writer-md", case_id="titanic")
    state = _state_with_figures(run_dir)
    state.halted = True
    state.phase = Phase.DEPLOYMENT
    state.substep = "6.4"
    state.ev.assessment_of_dm_results = {"success_criterion_met": True, "achieved_score": 0.8}
    write_run_reports(state, run_dir, force=True)
    case_md = (run_dir / "reports" / "case_report.md").read_text(encoding="utf-8")
    exec_md = (run_dir / "reports" / "execution_analysis.md").read_text(encoding="utf-8")
    assert "/Users/" not in case_md
    assert "/Users/" not in exec_md
    assert "../submission.csv" in case_md


def test_handoff_reports_use_bundle_relative_links(tmp_path: Path):
    run_dir = tmp_path / "runs" / "handoff-md"
    ensure_run_layout(run_dir, run_id="handoff-md", case_id="titanic")
    state = _state_with_figures(run_dir)
    (run_dir / "train.parquet").write_bytes(b"")
    (run_dir / "test.parquet").write_bytes(b"")
    (run_dir / "reports" / "case_report.md").parent.mkdir(parents=True, exist_ok=True)
    payload = build_handoff_zip(state, RunPaths(run_dir))
    import zipfile
    from io import BytesIO

    with zipfile.ZipFile(BytesIO(payload)) as zf:
        case_md = zf.read("titanic_handoff/reports/case_report.md").decode()
        final_md = zf.read("titanic_handoff/reports/final_report.md").decode()
    assert "/Users/" not in case_md
    assert "[submission.csv](../artifacts/submission.csv)" in case_md
    assert "../artifacts/figures/confusion_matrix.png" in final_md
