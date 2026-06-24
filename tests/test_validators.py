"""Tests for the state-artifact validators."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from maads.config import load_case_config
from maads.paths import resolve_path
from maads.state import CrispDMState, ModelRun
from maads.validators import validate_phase_3_artifacts, validate_phase_4_models


@pytest.fixture
def state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


def _write_parquet(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)


def test_phase3_clean_passes(tmp_path: Path, state: CrispDMState):
    train = tmp_path / "train.parquet"
    _write_parquet(train, pd.DataFrame({"Survived": [0, 1], "Age": [22, 38], "FamilySize": [1, 2]}))
    state.dp.dataset = {"train": str(train), "test": str(train)}
    state.dp.derived_attributes = {"items": ["FamilySize"]}
    assert validate_phase_3_artifacts(state) == []


def test_phase3_missing_parquet(state: CrispDMState):
    state.dp.dataset = {"train": "/no/such/train.parquet", "test": "/no/such/test.parquet"}
    errors = validate_phase_3_artifacts(state)
    assert any("does not exist" in e for e in errors)


def test_phase3_missing_derived_feature(tmp_path: Path, state: CrispDMState):
    train = tmp_path / "train.parquet"
    _write_parquet(train, pd.DataFrame({"Survived": [0, 1], "Age": [22, 38]}))
    state.dp.dataset = {"train": str(train), "test": str(train)}
    state.dp.derived_attributes = {"items": ["FamilySize"]}  # claimed but absent
    errors = validate_phase_3_artifacts(state)
    assert any("FamilySize" in e for e in errors)


def test_phase3_target_nan(tmp_path: Path, state: CrispDMState):
    train = tmp_path / "train.parquet"
    _write_parquet(train, pd.DataFrame({"Survived": [0, None], "Age": [22, 38]}))
    state.dp.dataset = {"train": str(train), "test": str(train)}
    errors = validate_phase_3_artifacts(state)
    assert any("missing values" in e for e in errors)


def test_phase4_no_models(state: CrispDMState):
    assert validate_phase_4_models(state) == ["no models were produced in Phase 4"]


def test_phase4_assessment_without_score(state: CrispDMState):
    state.md.models = [ModelRun(technique="rf", cv_score=None, assessment="great")]
    errors = validate_phase_4_models(state)
    assert any("no cv_score" in e for e in errors)


def test_phase4_clean(state: CrispDMState):
    run = ModelRun(technique="rf", cv_score=0.81, assessment="ok")
    state.md.models = [run]
    state.md.chosen_model = run
    assert validate_phase_4_models(state) == []
