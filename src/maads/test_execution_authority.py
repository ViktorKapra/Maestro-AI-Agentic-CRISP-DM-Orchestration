"""DE/DS measured execution must win over LLM narration."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from maads.agents import DataEngineerAgent, DataScientistAgent
from maads.config import load_case_config
from maads.paths import resolve_path
from maads.state import CrispDMState, Phase


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE", "0")
    monkeypatch.setenv("MAADS_PROGRESS", "0")
    monkeypatch.setattr("maads.codegen.run_text_task", lambda *a, **k: "")


@pytest.fixture
def state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


def test_de_quality_report_ignores_llm_when_execution_present(tmp_path: Path, state: CrispDMState):
    state.phase = Phase.DATA_UNDERSTANDING
    state.substep = "2.4"
    de = DataEngineerAgent(artifact_dir=tmp_path)

    fictional = {
        "state_updates": {
            "du": {"data_quality_report": {"blockers": ["LLM fiction"], "tolerable": []}},
        },
    }
    with patch("maads.agents.run_json_task", return_value=fictional):
        de.act(state)

    blockers = (state.du.data_quality_report or {}).get("blockers") or []
    assert any("Cabin" in b for b in blockers), blockers
    assert not any("LLM fiction" in b for b in blockers)


def test_de_prep_substeps_chain_execution(tmp_path: Path, state: CrispDMState):
    """3.2-3.5 each execute code; measured artifacts accumulate through the chain."""
    state.phase = Phase.DATA_PREPARATION
    de = DataEngineerAgent(artifact_dir=tmp_path)

    for substep in ("3.2", "3.3", "3.4", "3.5"):
        state.substep = substep
        with patch("maads.agents.run_json_task", return_value={}):
            de.act(state)

    assert state.dp.data_cleaning_report
    assert state.dp.derived_attributes
    assert state.dp.merged_data
    assert state.dp.dataset and Path(state.dp.dataset["train"]).exists()

    prep_dir = tmp_path / "prep"
    assert (prep_dir / "train_clean.parquet").exists()
    assert (prep_dir / "train_constructed.parquet").exists()
    assert (prep_dir / "train_integrated.parquet").exists()

    derived = (state.dp.derived_attributes or {}).get("items") or []
    derived_fields = [
        (d.get("field") if isinstance(d, dict) else d) for d in derived
    ]
    assert "FamilySize" in derived_fields


def test_de_prep_reports_measured_from_parquet_not_llm(tmp_path: Path, state: CrispDMState):
    state.phase = Phase.DATA_PREPARATION
    state.substep = "3.5"
    de = DataEngineerAgent(artifact_dir=tmp_path)

    fictional = {
        "state_updates": {
            "dp": {
                "data_cleaning_report": {"operations": ["imputed all Age to 0"]},
                "derived_attributes": {"items": [{"field": "FamilySize"}]},
            },
        },
    }
    with patch("maads.agents.run_json_task", return_value=fictional):
        de.act(state)

    assert state.dp.dataset and Path(state.dp.dataset["train"]).exists()
    cleaning = state.dp.data_cleaning_report or {}
    assert cleaning.get("source") == "measured from source CSV vs prepared parquet"
    assert "missing_before" in cleaning
    # 3.5-only path formats raw CSV — LLM fiction must not appear as measured truth.
    derived = (state.dp.derived_attributes or {}).get("items") or []
    derived_fields = [
        (d.get("field") if isinstance(d, dict) else d) for d in derived
    ]
    assert "FamilySize" not in derived_fields


def test_ds_model_run_ignores_llm_technique_when_execution_present(
    tmp_path: Path, state: CrispDMState,
):
    state.phase = Phase.DATA_PREPARATION
    state.substep = "3.5"
    de = DataEngineerAgent(artifact_dir=tmp_path)
    de.act(state)

    state.phase = Phase.MODELING
    state.substep = "4.3"
    ds = DataScientistAgent(artifact_dir=tmp_path)

    fictional = {
        "state_updates": {
            "md": {
                "model_run": {
                    "technique": "random_forest",
                    "cv_score": 0.99,
                    "description": "LLM fiction",
                },
            },
        },
    }
    with patch("maads.agents.run_json_task", return_value=fictional):
        ds.act(state)

    assert state.md.models
    run = state.md.models[-1]
    assert run.technique == "gradient_boosting"
    assert run.cv_score is not None
    assert run.cv_score != 0.99
