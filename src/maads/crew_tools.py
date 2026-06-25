"""CrewAI @tool wrappers for MAADS agents."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from crewai.tools import tool

from maads.paths import resolve_path


def _read_yaml_case(case_id: str) -> dict[str, Any]:
    from maads.config import load_case_config

    path = resolve_path(f"configs/{case_id}.yaml")
    cfg = load_case_config(path)
    return {
        "case_id": cfg.case_id,
        "problem_type": cfg.problem_type,
        "target_column": cfg.target_column,
        "evaluation_metric": cfg.evaluation_metric,
        "problem_statement": cfg.problem_statement[:500],
    }


@tool("read_case_config_summary")
def read_case_config_summary(case_id: str) -> str:
    """Return a short summary of the competition config for the given case_id."""
    import json

    return json.dumps(_read_yaml_case(case_id), indent=2)


@tool("validate_submission_file")
def validate_submission_file(
    submission_path: str,
    sample_submission_path: str,
    id_column: str,
) -> str:
    """Validate a Kaggle submission CSV against the sample submission schema."""
    errors: list[str] = []
    sub = Path(submission_path)
    sample = Path(sample_submission_path)
    if not sub.exists():
        return f"FAIL: submission not found: {submission_path}"
    if not sample.exists():
        return f"FAIL: sample submission not found: {sample_submission_path}"

    df_sub = pd.read_csv(sub)
    df_sample = pd.read_csv(sample)
    if list(df_sub.columns) != list(df_sample.columns):
        errors.append(
            f"column mismatch: got {list(df_sub.columns)}, "
            f"expected {list(df_sample.columns)}"
        )
    if len(df_sub) != len(df_sample):
        errors.append(f"row count {len(df_sub)} != expected {len(df_sample)}")
    if id_column in df_sub.columns and df_sub[id_column].isna().any():
        errors.append(f"null values in {id_column}")
    if errors:
        return "FAIL: " + "; ".join(errors)
    return "OK: submission schema valid"
