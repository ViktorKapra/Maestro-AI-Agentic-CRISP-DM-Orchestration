"""Tests for 4.4 evaluation_bundle execution."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from maads.baselines import _ASSESS_SRC
from maads.capabilities.shared import run_snippet
from maads.config import load_case_config
from maads.paths import resolve_path
from maads.state import EvaluationBundle
from maads.tools import PythonExec


@pytest.fixture
def tiny_train_parquet(tmp_path: Path) -> Path:
    df = pd.DataFrame({
        "PassengerId": range(1, 41),
        "Survived": [0, 1] * 20,
        "Pclass": [1, 2, 3] * 13 + [1],
        "Sex": ["male", "female"] * 20,
        "Age": [25.0 + i for i in range(40)],
        "SibSp": [0, 1] * 20,
        "Parch": [0, 0, 1, 0] * 10,
        "Fare": [10.0 + i for i in range(40)],
        "Embarked": ["S", "C"] * 20,
    })
    path = tmp_path / "train.parquet"
    df.to_parquet(path)
    return path


def test_assess_baseline_emits_evaluation_bundle(tiny_train_parquet: Path, tmp_path: Path):
    pyexec = PythonExec(workdir=tmp_path / "sandbox")
    figures_dir = tmp_path / "figures"
    class_labels = '{"0": "Not survived", "1": "Survived"}'
    payload = run_snippet(
        pyexec,
        _ASSESS_SRC,
        __TRAIN__=str(tiny_train_parquet),
        __TARGET__="Survived",
        __ID__="PassengerId",
        __PROBLEM_TYPE__="binary_classification",
        __FIGURES_DIR__=str(figures_dir),
        __CLASS_LABELS__=class_labels,
    )
    bundle = payload["evaluation_bundle"]
    assert "accuracy" in bundle["metrics"]
    assert bundle["confusion_matrix"]
    assert len(bundle["figures"]) >= 2
    validated = EvaluationBundle.model_validate(bundle)
    assert validated.problem_type == "binary_classification"


def test_titanic_config_has_class_labels():
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    assert cfg.class_labels["0"] == "Not survived"
    assert cfg.class_labels["1"] == "Survived"
