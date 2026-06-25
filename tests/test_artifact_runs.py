"""Tests for per-run artifact directory layout."""
from __future__ import annotations

from pathlib import Path

from maads.artifact_runs import prepare_run_dir, resolve_active_run_dir


def test_prepare_run_dir_creates_isolated_run(tmp_path: Path) -> None:
    case = tmp_path / "disaster_tweets"
    run_a = prepare_run_dir(case, "run-a")
    (run_a / "status.json").write_text("{}", encoding="utf-8")

    assert run_a == case / "runs" / "run-a"
    assert resolve_active_run_dir(case) == run_a
    assert (case / "current").resolve() == run_a


def test_second_run_archives_first(tmp_path: Path) -> None:
    case = tmp_path / "disaster_tweets"
    run_a = prepare_run_dir(case, "run-a")
    (run_a / "sandbox" / "exec").mkdir(parents=True)
    (run_a / "sandbox" / "exec" / "00001.py").write_text("x = 1", encoding="utf-8")

    run_b = prepare_run_dir(case, "run-b")
    assert run_b == case / "runs" / "run-b"
    assert not run_a.exists()
    assert (case / "archive" / "run-a" / "sandbox" / "exec" / "00001.py").is_file()
    assert resolve_active_run_dir(case) == run_b


def test_legacy_flat_layout_archived_on_first_structured_run(tmp_path: Path) -> None:
    case = tmp_path / "disaster_tweets"
    case.mkdir()
    (case / "status.json").write_text("{}", encoding="utf-8")
    (case / "sandbox").mkdir()
    (case / "sandbox" / "exec").mkdir()
    (case / "sandbox" / "exec" / "old.py").write_text("pass", encoding="utf-8")

    run_dir = prepare_run_dir(case, "run-new")
    assert run_dir == case / "runs" / "run-new"
    assert not (case / "status.json").exists()
    archive_dirs = list((case / "archive").iterdir())
    assert len(archive_dirs) == 1
    assert archive_dirs[0].name.startswith("legacy_")
    assert (archive_dirs[0] / "sandbox" / "exec" / "old.py").is_file()
