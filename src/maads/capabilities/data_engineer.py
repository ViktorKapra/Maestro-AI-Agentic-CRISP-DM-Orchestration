"""Data Engineer capabilities — CRISP-DM-independent execution API."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from maads.baselines import (
    _CLEAN_SRC, _COLLECT_SRC, _CONSTRUCT_SRC, _DESCRIBE_SRC, _FORMAT_SRC,
    _INTEGRATE_SRC, _QUALITY_SRC,
)
from maads.codegen import run_authored_code
from maads.deltas import StateDelta
from maads.state import CrispDMState
from maads.tools import PythonExec, inspect_dataset

from maads.capabilities.shared import (
    abspath as _abspath,
    de_dataset_context as _de_dataset_context,
    has_keys as _has_keys,
    prep_inputs as _prep_inputs,
    prep_workdir as _prep_workdir,
    run_snippet as _run_snippet,
    describe_data_contract as _describe_data_contract,
    measure_prep_artifacts as _measure_prep_artifacts,
)

def execution_evidence(
    pyexec: PythonExec,
    state: CrispDMState,
    substep: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Have the Data Engineer author and run the code for its owned substep.

    Returns measured evidence in the shape `_apply_data_engineer_response`
    expects. Each authored attempt self-debugs (codegen.run_authored_code) and
    falls back to the fixed baseline snippet only when all attempts fail.
    """
    train = _abspath(state.config.data.train_csv)
    test = _abspath(state.config.data.test_csv)
    target = state.config.target_column
    idc = state.config.id_column
    ds_ctx = _de_dataset_context(state, train, test)

    if substep == "2.1":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 2.1 Collect Initial Data: load the train and test "
                        "CSVs and report a brief collection summary. "
                        "Use DATASET_INSPECT_JSON for column alignment hints.",
            header_vars={"TRAIN_CSV": train, "TEST_CSV": test, **ds_ctx},
            contract=lambda p: _has_keys(p, "train_rows", "test_rows", "columns"),
            contract_hint="Required keys: train_rows (int), test_rows (int), columns (list).",
            fallback=lambda: _run_snippet(pyexec, _COLLECT_SRC, __TRAIN__=train, __TEST__=test),
            fallback_code=_COLLECT_SRC,
            artifact_dir=artifact_dir,
        )
        return {"initial_data_collection_report": res.payload}

    if substep == "2.2":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 2.2 Describe Data: profile the training data — "
                        "row/column counts, dtypes, missing counts, cardinality.",
            header_vars={"TRAIN_CSV": train, **ds_ctx},
            contract=_describe_data_contract,
            contract_hint=(
                "Required keys: n_rows (int), n_cols (int), columns (list of str), "
                "dtypes (dict column name -> dtype string), "
                "missing (dict column name -> int count). "
                "Do not emit parallel lists for dtypes or missing."
            ),
            fallback=lambda: _run_snippet(pyexec, _DESCRIBE_SRC, __TRAIN__=train),
            fallback_code=_DESCRIBE_SRC,
            artifact_dir=artifact_dir,
        )
        return {"data_description_report": res.payload}

    if substep == "2.4":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 2.4 Verify Data Quality: inspect the training data "
                        "and list genuine quality BLOCKERS (e.g. >40% missing, constant "
                        "columns, missing target) vs tolerable issues. Compute from the data.",
            header_vars={"TRAIN_CSV": train, "TARGET": target, **ds_ctx},
            contract=lambda p: _has_keys(p, "blockers", "tolerable"),
            contract_hint="Required keys: blockers (list of strings), tolerable (list of strings).",
            fallback=lambda: _run_snippet(pyexec, _QUALITY_SRC, __TRAIN__=train, __TARGET__=target),
            fallback_code=_QUALITY_SRC,
            artifact_dir=artifact_dir,
        )
        return {"data_quality_report": res.payload}

    prep_wd = str(_prep_workdir(artifact_dir).resolve())
    train_in, test_in = _prep_inputs(artifact_dir, state)

    if substep == "3.2":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 3.2 Clean Data: read TRAIN_IN and TEST_IN, apply "
                        "leakage-safe cleaning (impute missing, fix invalid values), "
                        "write train_clean.parquet and test_clean.parquet under OUTDIR, "
                        "and report missing counts before and after.",
            header_vars={
                "TRAIN_IN": train_in, "TEST_IN": test_in, "OUTDIR": prep_wd, "TARGET": target,
                **ds_ctx,
            },
            contract=lambda p: (
                _has_keys(p, "train_out", "test_out")
                or _has_keys(p, "missing_before", "missing_after")
            ),
            contract_hint="Required keys: train_out, test_out (paths), missing_before, "
                          "missing_after (per-column int counts).",
            fallback=lambda: _run_snippet(
                pyexec, _CLEAN_SRC,
                __TRAIN_IN__=train_in, __TEST_IN__=test_in, __OUTDIR__=prep_wd, __TARGET__=target,
            ),
            fallback_code=_CLEAN_SRC,
            artifact_dir=artifact_dir,
        )
        payload = res.payload
        return {
            "data_cleaning_report": {
                "missing_before": payload.get("missing_before"),
                "missing_after_train": payload.get("missing_after"),
                "operations": payload.get("operations") or [],
                "train_out": payload.get("train_out"),
                "test_out": payload.get("test_out"),
                "source": "executed at 3.2"
                + (" [degraded: baseline fallback]" if res.degraded else ""),
            },
            "degraded": res.degraded,
        }

    if substep == "3.3":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 3.3 Construct Data: read TRAIN_IN and TEST_IN, add "
                        "justified derived features available at prediction time, write "
                        "train_constructed.parquet and test_constructed.parquet under OUTDIR, "
                        "and list derived feature names.",
            header_vars={
                "TRAIN_IN": train_in, "TEST_IN": test_in, "OUTDIR": prep_wd,
                "TARGET": target, **ds_ctx,
            },
            contract=lambda p: _has_keys(p, "train_out", "test_out", "derived"),
            contract_hint="Required keys: train_out, test_out (paths), derived (list of names).",
            fallback=lambda: _run_snippet(
                pyexec, _CONSTRUCT_SRC,
                __TRAIN_IN__=train_in, __TEST_IN__=test_in, __OUTDIR__=prep_wd,
            ),
            fallback_code=_CONSTRUCT_SRC,
            artifact_dir=artifact_dir,
        )
        payload = res.payload
        derived = payload.get("derived") or []
        return {
            "derived_attributes": {
                "items": [
                    item if isinstance(item, dict) else {"field": str(item), "source": "executed at 3.3"}
                    for item in derived
                ],
            },
            "generated_records": {"count": 0, "source": "executed at 3.3"},
            "degraded": res.degraded,
        }

    if substep == "3.4":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 3.4 Integrate Data: read TRAIN_IN and TEST_IN, validate "
                        "schema compatibility and row granularity, write "
                        "train_integrated.parquet and test_integrated.parquet under OUTDIR, "
                        "and report merged row/column counts.",
            header_vars={"TRAIN_IN": train_in, "TEST_IN": test_in, "OUTDIR": prep_wd, **ds_ctx},
            contract=lambda p: _has_keys(p, "train_out", "test_out", "train_rows", "test_rows"),
            contract_hint="Required keys: train_out, test_out, train_rows, test_rows, "
                          "columns_train, columns_test.",
            fallback=lambda: _run_snippet(
                pyexec, _INTEGRATE_SRC,
                __TRAIN_IN__=train_in, __TEST_IN__=test_in, __OUTDIR__=prep_wd,
            ),
            fallback_code=_INTEGRATE_SRC,
            artifact_dir=artifact_dir,
        )
        payload = res.payload
        return {
            "merged_data": {
                "train_rows": payload.get("train_rows"),
                "test_rows": payload.get("test_rows"),
                "columns_train": payload.get("columns_train"),
                "columns_test": payload.get("columns_test"),
                "source": "executed at 3.4"
                + (" [degraded: baseline fallback]" if res.degraded else ""),
            },
            "degraded": res.degraded,
        }

    if substep == "3.5":
        outdir = str(artifact_dir.resolve())
        source_train = _abspath(state.config.data.train_csv)
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 3.5 Format Data: read TRAIN_IN and TEST_IN, drop "
                        "identifier/leakage columns, keep TARGET in train and ID_COL in "
                        "test, and write final train.parquet and test.parquet into OUTDIR.",
            header_vars={
                "TRAIN_IN": train_in, "TEST_IN": test_in, "OUTDIR": outdir,
                "SOURCE_TRAIN": source_train, "TARGET": target, "ID_COL": idc,
                **ds_ctx,
            },
            contract=lambda p: (
                _has_keys(p, "train", "test", "n_train", "n_test")
                or ([] if int(p.get("n_train", 0)) > 0 else ["n_train must be > 0"])
            ),
            contract_hint="Required keys: train (parquet path), test (parquet path), "
                          "n_train (int>0), n_test (int), derived (list), dropped (list).",
            fallback=lambda: _run_snippet(
                pyexec, _FORMAT_SRC,
                __TRAIN_IN__=train_in, __TEST_IN__=test_in, __OUTDIR__=outdir,
                __SOURCE_TRAIN__=source_train, __TARGET__=target, __ID__=idc,
            ),
            fallback_code=_FORMAT_SRC,
            artifact_dir=artifact_dir,
        )
        info = res.payload
        n_derived = len(info.get("derived") or [])
        measured = _measure_prep_artifacts(
            source_train=train,
            source_test=test,
            train_parquet=info["train"],
            test_parquet=info["test"],
            target=target,
            payload_derived=info.get("derived") or [],
            payload_dropped=info.get("dropped") or [],
        )
        return {
            "dataset": {"train": info["train"], "test": info["test"]},
            "dataset_description": (
                f"{info.get('n_train')} train / {info.get('n_test')} test rows (parquet); "
                f"{n_derived} derived feature(s) reported by code"
                + (" [degraded: baseline fallback]" if res.degraded else "")
            ),
            "derived": info.get("derived") or [],
            "dropped": info.get("dropped") or [],
            "degraded": res.degraded,
            **measured,
        }
    return {}


def apply_response(
    data: dict,
    state: CrispDMState,
    substep: str,
    execution: dict[str, Any],
) -> StateDelta:
    from maads.capabilities.shared import execution_or_llm, record_degraded

    su = (data or {}).get("state_updates") or {}
    du = su.get("du") or {}
    dp = su.get("dp") or {}
    fields: list[str] = []

    if substep == "2.1":
        report = execution_or_llm(execution, du, "initial_data_collection_report")
        if report:
            state.du.initial_data_collection_report = report
            fields.append("du.initial_data_collection_report")
    elif substep == "2.2":
        report = execution_or_llm(execution, du, "data_description_report")
        if report:
            state.du.data_description_report = report
            fields.append("du.data_description_report")
    elif substep == "2.4":
        report = execution_or_llm(execution, du, "data_quality_report")
        if report:
            state.du.data_quality_report = report
            fields.append("du.data_quality_report")
    elif substep == "3.1":
        rationale = dp.get("rationale_for_inclusion_exclusion")
        if rationale:
            state.dp.rationale_for_inclusion_exclusion = rationale
            fields.append("dp.rationale_for_inclusion_exclusion")
    elif substep == "3.2":
        cleaning = execution_or_llm(execution, dp, "data_cleaning_report")
        if cleaning:
            state.dp.data_cleaning_report = cleaning
            fields.append("dp.data_cleaning_report")
        if execution.get("degraded"):
            state.dp.reformatted_data = {"degraded": True, "reason": "DE 3.2 fell back to baseline"}
            record_degraded(state, substep, "data_engineer", "3.2 baseline fallback")
            fields.append("dp.reformatted_data")
    elif substep == "3.3":
        derived = execution_or_llm(execution, dp, "derived_attributes")
        if derived:
            state.dp.derived_attributes = derived
            fields.append("dp.derived_attributes")
        generated = execution_or_llm(execution, dp, "generated_records")
        if generated:
            state.dp.generated_records = generated
            fields.append("dp.generated_records")
    elif substep == "3.4":
        merged = execution_or_llm(execution, dp, "merged_data")
        if merged:
            state.dp.merged_data = merged
            fields.append("dp.merged_data")
    elif substep == "3.5":
        dataset = execution.get("dataset")
        description = execution.get("dataset_description")
        if dataset:
            state.dp.dataset = dataset
            fields.append("dp.dataset")
        if description:
            state.dp.dataset_description = description
            fields.append("dp.dataset_description")
        cleaning = execution.get("data_cleaning_report")
        if cleaning:
            state.dp.data_cleaning_report = cleaning
            fields.append("dp.data_cleaning_report")
        derived = execution.get("derived_attributes")
        if derived:
            state.dp.derived_attributes = derived
            fields.append("dp.derived_attributes")
        merged = execution.get("merged_data")
        if merged:
            state.dp.merged_data = merged
            fields.append("dp.merged_data")
        if execution.get("degraded"):
            state.dp.reformatted_data = {"degraded": True, "reason": "DE prep fell back to baseline"}
            record_degraded(state, substep, "data_engineer", "prep baseline fallback")
            fields.append("dp.reformatted_data")

    summary = (data or {}).get("summary", "")
    return StateDelta(fields, notes=summary or f"DE completed {substep}")

