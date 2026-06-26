"""Tests for capability modules (CRISP-DM-independent APIs)."""
from __future__ import annotations

from pathlib import Path

import pytest

import maads.crew as crew
from maads.capabilities.data_engineer import execution_evidence
from maads.capabilities.data_scientist import execution_evidence as ds_execution_evidence
from maads.capabilities.shared import has_keys, de_dataset_context
from maads.config import load_case_config
from maads.paths import resolve_path
from maads.state import CrispDMState
from maads.tools import PythonExec
from tests.fixtures.titanic_exec import fake_run_text_task


@pytest.fixture
def state() -> CrispDMState:
    return CrispDMState.from_config(load_case_config(resolve_path("configs/titanic.yaml")))


def test_has_keys_contract():
    assert has_keys({"a": 1}, "a") == []
    assert has_keys({}, "a") == ["missing key 'a'"]


def test_execution_evidence_collect_requires_authored_code(monkeypatch, state, tmp_path):
    monkeypatch.setattr(crew, "run_text_task", lambda *a, **k: "")
    pyexec = PythonExec(workdir=tmp_path / "sandbox")
    with pytest.raises(crew.CrewKickoffError):
        execution_evidence(pyexec, state, "2.1", tmp_path)


def test_execution_evidence_collect_with_stub_code(monkeypatch, state, tmp_path):
    monkeypatch.setattr(crew, "run_text_task", fake_run_text_task)
    state.substep = "2.1"
    pyexec = PythonExec(workdir=tmp_path / "sandbox")
    out = execution_evidence(pyexec, state, "2.1", tmp_path)
    assert "initial_data_collection_report" in out


def test_ds_execution_evidence_explore_with_stub_code(monkeypatch, state, tmp_path):
    monkeypatch.setattr(crew, "run_text_task", fake_run_text_task)
    state.substep = "2.3"
    pyexec = PythonExec(workdir=tmp_path / "sandbox")
    out = ds_execution_evidence(pyexec, state, "2.3", tmp_path)
    assert "data_exploration_report" in out
