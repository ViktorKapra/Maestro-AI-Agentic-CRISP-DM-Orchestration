"""Tests for dashboard artifact discovery."""
from __future__ import annotations

import json
from pathlib import Path

from maads.artifact_runs import resolve_active_run_dir
from maads.dashboard.store import list_cases, read_trace_optional


def test_resolve_active_run_prefers_current_with_status(tmp_path: Path):
    case = tmp_path / "disaster_tweets"
    runs = case / "runs"
    old = runs / "old-run"
    new = runs / "new-run"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / "status.json").write_text("{}")
  # new run has no status yet
    (case / "current").symlink_to(Path("runs") / "new-run")
    assert resolve_active_run_dir(case) == new


def test_list_cases_finds_run_under_runs_layout(tmp_path: Path):
    case = tmp_path / "titanic"
    run = case / "runs" / "abc"
    run.mkdir(parents=True)
    (run / "status.json").write_text(
        json.dumps({"case_id": "titanic", "phase": 1, "halted": False}),
    )
    (case / "current").symlink_to(Path("runs") / "abc")
    cases = list_cases(tmp_path)
    assert len(cases) == 1
    assert cases[0]["case_id"] == "titanic"


def test_read_trace_optional_empty_when_missing(tmp_path: Path):
    run = tmp_path / "run1"
    run.mkdir()
    (run / "status.json").write_text(json.dumps({"case_id": "titanic"}))
    trace = read_trace_optional(run, case_id="titanic")
    assert trace.events == []
    assert trace.case_id == "titanic"
