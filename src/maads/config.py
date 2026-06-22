"""Typed loading of `configs/<case>.yaml` files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class DataPaths(BaseModel):
    train_csv: str
    test_csv: str
    sample_submission_csv: str


class SuccessCriterion(BaseModel):
    metric: str
    threshold: float


class CaseConfig(BaseModel):
    case_id: str
    kaggle_competition: str
    problem_statement: str
    problem_type: str  # "binary_classification" | "regression"
    target_column: str
    id_column: str
    evaluation_metric: str
    data: DataPaths
    feature_hints: dict[str, Any] = Field(default_factory=dict)
    success_criterion: SuccessCriterion


def load_case_config(path: Path) -> CaseConfig:
    """Load and validate a case config from YAML."""
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    raw = yaml.safe_load(path.read_text())
    return CaseConfig.model_validate(raw)
