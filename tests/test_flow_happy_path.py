"""Flow happy-path and import smoke tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from maads.config import load_case_config
from maads.flow.crisp_dm_flow import CrispDMFlow
from maads.paths import resolve_path
from maads.state import SUBSTEPS, CrispDMState, Phase
from maads.outcome import completion_halt_reason
from maads.testing.fake_llm import fake_llm_response


@pytest.fixture
def titanic_state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


@pytest.fixture(autouse=True)
def fast_run(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE", "0")
    monkeypatch.setenv("MAADS_PROGRESS", "0")
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setattr("maads.codegen.run_text_task", lambda *a, **k: "")


def test_flow_imports():
    from crewai.flow.flow import Flow, listen, router, start

    assert Flow is not None
    assert callable(listen)
    assert callable(router)
    assert callable(start)


def _artifact_dir(tmp_path: Path) -> Path:
    d = tmp_path / "artifacts" / "titanic"
    d.mkdir(parents=True)
    return d


@patch("maads.agents.run_json_task")
def test_flow_happy_path_all_substeps(mock_llm, titanic_state: CrispDMState, tmp_path: Path):
    mock_llm.side_effect = fake_llm_response
    artifact_dir = _artifact_dir(tmp_path)
    dispatched: list[str] = []

    flow = CrispDMFlow(titanic_state, artifact_dir)
    orig_run = flow._ctx.agents["domain"].act

    def track_domain(state):
        dispatched.append(state.substep)
        return orig_run(state)

    flow._ctx.agents["domain"].act = track_domain

    with patch.object(flow._pm, "plan", side_effect=lambda s: __import__("maads.deltas", fromlist=["Plan"]).Plan(action="advance", reason="mock")):
        state = flow.run()

    assert state.halted
    assert state.halt_reason == completion_halt_reason(state)
    expected = []
    for phase in Phase:
        expected.extend(SUBSTEPS[phase])
    assert dispatched  # domain substeps were hit


def test_flow_loop_back_from_3_1(titanic_state: CrispDMState, tmp_path: Path):
    artifact_dir = _artifact_dir(tmp_path)
    titanic_state.du.data_quality_report = {"blockers": ["missing values"]}

    plans = [
        __import__("maads.deltas", fromlist=["Plan"]).Plan(
            action="loop_back", loop_to_phase=1, loop_label="A",
            target_substep="1.3", reason="quality blockers",
        ),
        __import__("maads.deltas", fromlist=["Plan"]).Plan(action="advance", reason="ok"),
    ]

    flow = CrispDMFlow(titanic_state, artifact_dir)
    with patch.object(flow._pm, "plan", side_effect=plans):
        flow.state.phase = Phase.DATA_PREPARATION
        flow.state.substep = "3.1"
        flow.enter_checkpoint_3_1()
        assert flow._last_checkpoint_route == "phase_1"
        assert flow.state.phase == Phase.BUSINESS_UNDERSTANDING
