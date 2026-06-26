"""Shared helpers for agent capabilities."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from maads.paths import resolve_path
from maads.state import CrispDMState
from maads.tools import inspect_dataset

_PREP_STAGES = (
    ("integrated", "train_integrated.parquet", "test_integrated.parquet"),
    ("constructed", "train_constructed.parquet", "test_constructed.parquet"),
    ("clean", "train_clean.parquet", "test_clean.parquet"),
)


def abspath(rel: str) -> str:
    return str(resolve_path(rel))


def run_snippet(pyexec, src: str, **subs: str) -> dict:
    code = src
    for token, value in subs.items():
        code = code.replace(token, value)
    res = pyexec.run(code)
    if not res.ok:
        raise RuntimeError(f"baseline snippet failed:\n{res.stderr.strip()}")
    return json.loads(res.stdout.strip().splitlines()[-1])


def prep_workdir(artifact_dir: Path) -> Path:
    wd = artifact_dir / "prep"
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def prep_inputs(artifact_dir: Path, state: CrispDMState) -> tuple[str, str]:
    wd = prep_workdir(artifact_dir)
    for _stage, train_name, test_name in _PREP_STAGES:
        train_p, test_p = wd / train_name, wd / test_name
        if train_p.exists() and test_p.exists():
            return str(train_p.resolve()), str(test_p.resolve())
    return abspath(state.config.data.train_csv), abspath(state.config.data.test_csv)


def record_degraded(state: CrispDMState, substep: str, agent: str, reason: str) -> None:
    state.record_degraded(f"{agent}@{substep}: {reason}")


def de_dataset_context(state: CrispDMState, train: str, test: str) -> dict[str, Any]:
    summary = inspect_dataset(train, test, target_column=state.config.target_column)
    fh = state.config.feature_hints or {}
    if fh.get("na_means_absent"):
        summary["na_means_absent"] = list(fh["na_means_absent"])
    return {"DATASET_INSPECT_JSON": json.dumps(summary, default=str)}


def has_keys(payload: dict, *keys: str) -> list[str]:
    return [f"missing key '{k}'" for k in keys if k not in payload]


def per_column_map(payload: dict, field: str, *, value_label: str) -> list[str]:
    if field not in payload:
        return [f"missing key '{field}'"]
    value = payload[field]
    if isinstance(value, list):
        return [f"'{field}' must be a dict mapping column name -> {value_label}, not a list"]
    if not isinstance(value, dict):
        return [f"'{field}' must be a dict mapping column name -> {value_label}"]
    return []


def int_column_map(payload: dict, field: str) -> list[str]:
    errors = per_column_map(payload, field, value_label="int count")
    if errors:
        return errors
    for col, count in payload[field].items():
        if not isinstance(count, int) or isinstance(count, bool):
            errors.append(f"'{field}[{col!r}]' must be an int count")
    return errors


def str_column_map(payload: dict, field: str) -> list[str]:
    errors = per_column_map(payload, field, value_label="dtype string")
    if errors:
        return errors
    for col, dtype in payload[field].items():
        if not isinstance(dtype, str):
            errors.append(f"'{field}[{col!r}]' must be a dtype string")
    return errors


def describe_data_contract(payload: dict) -> list[str]:
    errors = has_keys(payload, "n_rows", "n_cols", "columns", "dtypes", "missing")
    if errors:
        return errors
    if not isinstance(payload.get("columns"), list):
        errors.append("'columns' must be a list of column names")
    errors.extend(int_column_map(payload, "missing"))
    errors.extend(str_column_map(payload, "dtypes"))
    return errors


def execution_or_llm(execution: dict[str, Any], llm_parent: dict, key: str) -> Any:
    if key in execution and execution[key] is not None:
        return execution[key]
    return llm_parent.get(key)


_DE_EXECUTION_AUTHORITY_KEYS: dict[str, tuple[str, ...]] = {
    "2.1": ("initial_data_collection_report",),
    "2.2": ("data_description_report",),
    "2.4": ("data_quality_report",),
    "3.2": ("data_cleaning_report",),
    "3.3": ("derived_attributes", "generated_records"),
    "3.4": ("merged_data",),
    "3.5": ("dataset", "dataset_description"),
}

_DS_EXECUTION_AUTHORITY_KEYS: dict[str, tuple[str, ...]] = {
    "2.3": ("data_exploration_report",),
    "4.3": ("model_run",),
    "4.4": ("evaluation_bundle",),
}


def execution_authoritative(
    execution: dict[str, Any],
    substep: str,
    agent: Literal["data_engineer", "data_scientist"],
) -> bool:
    """True when measured codegen output already satisfies the substep contract."""
    keys = (
        _DE_EXECUTION_AUTHORITY_KEYS
        if agent == "data_engineer"
        else _DS_EXECUTION_AUTHORITY_KEYS
    )
    return any(
        execution.get(key) is not None
        for key in keys.get(substep, ())
    )


def measure_prep_artifacts(
    *,
    source_train: str,
    source_test: str,
    train_parquet: str,
    test_parquet: str,
    target: str,
    payload_derived: list[Any] | None,
    payload_dropped: list[Any] | None,
) -> dict[str, Any]:
    import pandas as pd

    src_tr = pd.read_csv(source_train)
    src_te = pd.read_csv(source_test)
    prep_tr = pd.read_parquet(train_parquet)
    prep_te = pd.read_parquet(test_parquet)

    dropped = [c for c in src_tr.columns if c not in prep_tr.columns and c not in {target}]
    if payload_dropped:
        dropped = list(dict.fromkeys([*payload_dropped, *dropped]))

    new_cols = [c for c in prep_tr.columns if c not in src_tr.columns]
    derived_names = list(payload_derived) if payload_derived else new_cols
    derived_items = [
        item if isinstance(item, dict) else {"field": str(item), "source": "measured"}
        for item in derived_names
    ]

    missing_before = {c: int(src_tr[c].isna().sum()) for c in src_tr.columns}
    missing_after = {c: int(prep_tr[c].isna().sum()) for c in prep_tr.columns}

    return {
        "data_cleaning_report": {
            "missing_before": missing_before,
            "missing_after_train": missing_after,
            "columns_dropped": dropped,
            "source": "measured from source CSV vs prepared parquet",
        },
        "derived_attributes": {"items": derived_items},
        "merged_data": {
            "train_rows": int(len(prep_tr)),
            "test_rows": int(len(prep_te)),
            "columns_train": list(prep_tr.columns),
            "columns_test": list(prep_te.columns),
            "source": "measured from prepared parquets",
        },
    }
