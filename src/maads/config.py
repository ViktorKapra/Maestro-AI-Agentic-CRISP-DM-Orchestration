"""Typed loading of `configs/<case>.yaml` files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from maads.paths import resolve_path


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
    cfg = CaseConfig.model_validate(raw)
    # Data paths in YAML are relative to repo root, not cwd.
    data = cfg.data.model_copy(
        update={
            "train_csv": str(resolve_path(cfg.data.train_csv)),
            "test_csv": str(resolve_path(cfg.data.test_csv)),
            "sample_submission_csv": str(resolve_path(cfg.data.sample_submission_csv)),
        }
    )
    return cfg.model_copy(update={"data": data})


def kickoff_inputs(config: CaseConfig) -> dict[str, str]:
    """Flat inputs dict for CrewAI ``{placeholder}`` substitution and run artefacts."""
    return {
        "case_id": config.case_id,
        "kaggle_competition": config.kaggle_competition,
        "problem_statement": config.problem_statement,
        "problem_type": config.problem_type,
        "target_column": config.target_column,
        "id_column": config.id_column,
        "evaluation_metric": config.evaluation_metric,
        "success_metric": config.success_criterion.metric,
        "success_threshold": str(config.success_criterion.threshold),
    }
