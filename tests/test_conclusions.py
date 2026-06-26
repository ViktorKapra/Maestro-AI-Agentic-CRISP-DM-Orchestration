"""Tests for phase-aware conclusions projection."""
from __future__ import annotations

from maads.conclusions import build_conclusions_summary
from maads.config import load_case_config
from maads.paths import resolve_path
from maads.state import CrispDMState, ModelRun


def _state() -> CrispDMState:
    return CrispDMState.from_config(load_case_config(resolve_path("configs/titanic.yaml")))


def test_empty_state_has_no_phases():
    summary = build_conclusions_summary(_state())
    assert summary["phases"] == []
    assert summary["business_objectives"] is None


def test_business_and_data_understanding_phases():
    state = _state()
    state.bu.business_objectives = "Predict survival."
    state.bu.data_mining_goals = "Binary classification."
    state.bu.project_plan = ["collect", "model", "submit"]
    state.du.initial_data_collection_report = {
        "train_rows": 891,
        "test_rows": 418,
        "columns": ["PassengerId", "Survived"],
    }
    state.du.data_description_report = {
        "n_rows": 891,
        "n_cols": 12,
        "columns": ["Age", "Fare"],
        "missing": {"Age": 177},
    }
    state.du.data_exploration_report = {
        "n_rows": 891,
        "target": "Survived",
        "target_distribution": {"0": 549, "1": 342},
    }
    state.du.data_quality_report = {
        "blockers": [],
        "tolerable": ["Age: 20% missing (imputable)"],
    }

    summary = build_conclusions_summary(state)
    by_phase = {p["id"]: p for p in summary["phases"]}

    assert 1 in by_phase
    assert len(by_phase[1]["items"]) >= 2
    assert by_phase[1]["items"][0]["id"] == "1.1"
    assert "Predict survival" in by_phase[1]["items"][0]["summary"]

    assert 2 in by_phase
    du_ids = [i["id"] for i in by_phase[2]["items"]]
    assert du_ids == ["2.1", "2.2", "2.3", "2.4"]
    assert "891" in by_phase[2]["items"][0]["summary"]
    assert summary["data_quality_tolerable"] == ["Age: 20% missing (imputable)"]


def test_data_preparation_phase_with_artifacts():
    state = _state()
    state.dp.rationale_for_inclusion_exclusion = {
        "included": ["numeric", "categorical"],
        "excluded": ["id"],
    }
    state.dp.data_cleaning_report = {
        "operations": ["impute Age"],
        "train_out": "/tmp/train_clean.parquet",
        "test_out": "/tmp/test_clean.parquet",
        "source": "executed at 3.2",
    }
    state.dp.dataset = {"train": "/tmp/train.parquet", "test": "/tmp/test.parquet"}
    state.dp.dataset_description = "891 train / 418 test rows (parquet)"

    summary = build_conclusions_summary(state)
    dp_phase = next(p for p in summary["phases"] if p["id"] == 3)
    ids = [i["id"] for i in dp_phase["items"]]
    assert ids == ["3.1", "3.2", "3.5"]

    cleaning = next(i for i in dp_phase["items"] if i["id"] == "3.2")
    assert cleaning["artifact_paths"]["train_out"] == "/tmp/train_clean.parquet"
    assert summary["dataset_paths"]["train"] == "/tmp/train.parquet"
    assert summary["dataset_description"] == "891 train / 418 test rows (parquet)"


def test_data_preparation_phase_accepts_list_rationale():
    state = _state()
    state.dp.rationale_for_inclusion_exclusion = [
        "text",
        "keyword",
        {"field": "location", "decision": "include"},
    ]

    summary = build_conclusions_summary(state)
    dp_phase = next(p for p in summary["phases"] if p["id"] == 3)
    item = next(i for i in dp_phase["items"] if i["id"] == "3.1")
    assert "3 included" in item["summary"]


def test_modeling_and_evaluation_phases():
    state = _state()
    state.md.modeling_technique = "gradient_boosting"
    state.md.test_design = {"cv": "stratified_5fold"}
    state.md.models = [
        ModelRun(technique="gbm", cv_score=0.82, assessment="strong baseline"),
    ]
    state.md.chosen_model = state.md.models[0]
    state.ev.assessment_of_dm_results = {"cv_score": 0.82, "meets": True, "threshold": 0.77}
    state.ev.decision = "deploy"

    summary = build_conclusions_summary(state)
    phase_ids = {p["id"] for p in summary["phases"]}
    assert phase_ids >= {4, 5}
    assert summary["chosen_model"]["technique"] == "gbm"
    assert summary["decision"] == "deploy"
