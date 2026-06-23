"""State-artifact validators run before CRISP-DM phase transitions.

These bridge "what the state claims" and "what the artifacts on disk actually
are". A non-empty result is a real, measured deficit — the orchestrator turns it
into a Loop B signal rather than advancing on a lie.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maads.state import CrispDMState


def validate_phase_3_artifacts(state: "CrispDMState") -> list[str]:
    """Check the prepared parquet matches the Data Preparation claims.

    Returns a list of human-readable deficits (empty == clean). Reads the parquet
    written by the Data Engineer's authored prep code at 3.5.
    """
    errors: list[str] = []
    train_path = state.dp.dataset.get("train")
    test_path = state.dp.dataset.get("test")
    if not train_path:
        return ["dp.dataset['train'] is missing"]
    if not test_path:
        errors.append("dp.dataset['test'] is missing")

    p = Path(train_path)
    if not p.exists():
        return errors + [f"train parquet does not exist: {train_path}"]
    if p.suffix != ".parquet":
        errors.append(f"train dataset is not parquet: {train_path}")

    try:
        import pandas as pd

        df = pd.read_parquet(train_path)
    except Exception as exc:  # unreadable parquet is itself a deficit
        return errors + [f"could not read train parquet: {exc}"]

    target = state.config.target_column
    if target not in df.columns:
        errors.append(f"target '{target}' not in prepared train parquet")
    elif bool(df[target].isna().any()):
        errors.append(f"target '{target}' has missing values after prep")

    # Claimed derived features must actually be present as columns.
    derived = state.dp.derived_attributes or {}
    claimed = derived.get("items") if isinstance(derived, dict) else None
    for feat in _feature_names(claimed):
        if feat not in df.columns:
            errors.append(f"claimed derived feature '{feat}' absent from parquet")

    return errors


def validate_phase_4_models(state: "CrispDMState") -> list[str]:
    """Check the modeling state is internally consistent."""
    errors: list[str] = []
    if not state.md.models:
        return ["no models were produced in Phase 4"]
    for i, run in enumerate(state.md.models):
        if run.assessment and run.cv_score is None:
            errors.append(f"model {i} ('{run.technique}') has an assessment but no cv_score")
    chosen = state.md.chosen_model
    if chosen is not None and chosen.cv_score is None:
        errors.append("chosen_model has no cv_score")
    return errors


def _feature_names(claimed) -> list[str]:
    """Pull plausible feature-name strings out of the loosely-typed derived list."""
    names: list[str] = []
    if not isinstance(claimed, list):
        return names
    for item in claimed:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = item.get("name") or item.get("feature")
            if isinstance(name, str):
                names.append(name)
    return names
