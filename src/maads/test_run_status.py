"""Tests for file-based live run status."""
from __future__ import annotations

import json
from pathlib import Path

from maads.config import load_case_config
from maads.paths import resolve_path
from maads.run_status import bind_run, flush_status, record_substep_done, set_activity
from maads.state import CrispDMState


def test_bind_run_writes_status_files(tmp_path: Path):
    config = load_case_config(resolve_path("configs/titanic.yaml"))
    state = CrispDMState.from_config(config)
    artifact_dir = tmp_path / "titanic"

    bind_run(artifact_dir, state)

    status_json = artifact_dir / "status.json"
    status_md = artifact_dir / "status.md"
    assert status_json.is_file()
    assert status_md.is_file()

    payload = json.loads(status_json.read_text())
    assert payload["case_id"] == "titanic"
    assert payload["substep"] == "1.1"
    assert payload["activity"] == "starting"
    assert "artifact_dir" in payload
    assert "trace_dir" in payload


def test_set_activity_and_substep_done_update_status(tmp_path: Path):
    config = load_case_config(resolve_path("configs/titanic.yaml"))
    state = CrispDMState.from_config(config)
    artifact_dir = tmp_path / "titanic"
    bind_run(artifact_dir, state)

    set_activity("CrewAI · PM · LLM running…")
    mid = json.loads((artifact_dir / "status.json").read_text())
    assert "LLM running" in mid["activity"]

    record_substep_done("1.1")
    payload = json.loads((artifact_dir / "status.json").read_text())
    assert payload["completed_substeps"] == 1
    assert "finished 1.1" in payload["activity"]


def test_flush_status_without_bind_is_noop(tmp_path: Path):
    flush_status()
    assert not (tmp_path / "status.json").exists()
