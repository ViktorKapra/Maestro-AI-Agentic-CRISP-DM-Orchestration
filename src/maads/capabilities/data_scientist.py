"""Data Scientist capabilities — CRISP-DM-independent execution API."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.baselines import (
    _ASSESS_SRC,
    _EXPLORE_SRC,
    _NLP_TRAIN_SRC,
    _TRAIN_SRC,
    is_nlp_case,
    primary_text_column,
)
from maads.codegen import run_authored_code
from maads.deltas import StateDelta
from maads.capabilities.shared import (
    abspath as _abspath,
    execution_or_llm,
    has_keys as _has_keys,
    record_degraded,
    run_snippet as _run_snippet,
)
from maads.state import CrispDMState, EvaluationBundle, ModelRun


def execution_evidence(
    pyexec,
    state: CrispDMState,
    substep: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Author and run code for DS-owned execution substeps."""
    train = _abspath(state.config.data.train_csv)
    target = state.config.target_column

    if substep == "2.3":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_scientist", state=state,
            instruction="CRISP-DM 2.3 Explore Data: probe the training data to inform "
                        "modeling — target balance, feature/target relationships, "
                        "notable distributions. Compute from the data, do not guess.",
            header_vars={"TRAIN_CSV": train, "TARGET": target},
            contract=lambda p: _has_keys(p, "n_rows", "target"),
            contract_hint="Required keys: n_rows (int), target (str); add any findings "
                          "(e.g. target_distribution, correlations).",
            fallback=lambda: _run_snippet(pyexec, _EXPLORE_SRC, __TRAIN__=train, __TARGET__=target),
            fallback_code=_EXPLORE_SRC,
            artifact_dir=artifact_dir,
        )
        return {"data_exploration_report": res.payload}

    if substep == "4.3":
        dataset_train = state.dp.dataset.get("train")
        if not dataset_train:
            return {}
        idc = state.config.id_column
        metric = state.config.evaluation_metric
        problem_type = state.config.problem_type
        technique_hint = state.md.modeling_technique or "your choice"
        if is_nlp_case(state.config.feature_hints):
            text_col = primary_text_column(state.config.feature_hints) or "text"
            train_fallback = lambda: _run_snippet(
                pyexec, _NLP_TRAIN_SRC,
                __TRAIN__=dataset_train, __TARGET__=target,
                __TEXT_COL__=text_col, __METRIC__=metric,
            )
            train_code = _NLP_TRAIN_SRC
        else:
            train_fallback = lambda: _run_snippet(
                pyexec, _TRAIN_SRC, __TRAIN__=dataset_train, __TARGET__=target, __ID__=idc,
            )
            train_code = _TRAIN_SRC
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_scientist", state=state,
            instruction="CRISP-DM 4.3 Build Model: write and execute Python that reads "
                        "TRAIN_PARQUET, builds a scikit-learn pipeline appropriate for "
                        "PROBLEM_TYPE, and evaluates it with cross-validation scored on "
                        f"METRIC. Prefer the technique from 4.1 ({technique_hint}) when "
                        "suitable. Drop TARGET and ID_COL from features. You must train and "
                        "score the model in code — do not claim results you did not run.",
            header_vars={
                "TRAIN_PARQUET": dataset_train,
                "TARGET": target,
                "ID_COL": idc,
                "METRIC": metric,
                "PROBLEM_TYPE": problem_type,
            },
            contract=lambda p: (
                _has_keys(p, "technique", "cv_score", "cv_std")
                or ([] if isinstance(p.get("cv_score"), (int, float)) and isinstance(p.get("cv_std"), (int, float))
                    else ["cv_score and cv_std must be numeric"])
            ),
            contract_hint="Required keys: technique (str), cv_score (float), cv_std (float), n_features (int).",
            fallback=train_fallback,
            fallback_code=train_code,
            artifact_dir=artifact_dir,
        )
        p = res.payload
        return {
            "model_run": {
                "technique": p.get("technique") or "unspecified",
                "cv_score": p.get("cv_score"),
                "cv_std": p.get("cv_std"),
                "description": f"{p.get('n_features', '?')} features, CV"
                               + (" [degraded: baseline fallback]" if res.degraded else ""),
                "parameter_settings": p.get("parameter_settings") or {},
            },
            "degraded": res.degraded,
        }

    if substep == "4.4":
        dataset_train = state.dp.dataset.get("train")
        if not dataset_train:
            return {}
        idc = state.config.id_column
        problem_type = state.config.problem_type
        figures_dir = str((artifact_dir / "figures").resolve())
        class_labels = json.dumps(state.config.class_labels or {})
        assess_fallback = lambda: _run_snippet(
            pyexec, _ASSESS_SRC,
            __TRAIN__=dataset_train, __TARGET__=target, __ID__=idc,
            __PROBLEM_TYPE__=problem_type, __FIGURES_DIR__=figures_dir,
            __CLASS_LABELS__=class_labels,
        )
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_scientist", state=state,
            instruction="CRISP-DM 4.4 Assess Model: write and execute Python that reads "
                        "TRAIN_PARQUET, uses the best model approach from 4.3, produces "
                        "out-of-fold predictions via stratified CV, computes problem-type-appropriate "
                        "metrics (for binary classification: accuracy, balanced accuracy, per-class "
                        "precision/recall/F1, confusion matrix), saves figures under FIGURES_DIR, "
                        "and prints evaluation_bundle. Use CLASS_LABELS for human-readable names.",
            header_vars={
                "TRAIN_PARQUET": dataset_train,
                "TARGET": target,
                "ID_COL": idc,
                "PROBLEM_TYPE": problem_type,
                "FIGURES_DIR": figures_dir,
                "CLASS_LABELS": class_labels,
            },
            contract=lambda p: _has_keys(p, "evaluation_bundle"),
            contract_hint="Required key: evaluation_bundle (dict with metrics, confusion_matrix, figures).",
            fallback=assess_fallback,
            fallback_code=_ASSESS_SRC,
            artifact_dir=artifact_dir,
        )
        p = res.payload
        return {
            "evaluation_bundle": p.get("evaluation_bundle"),
            "assessment": p.get("assessment"),
            "degraded": res.degraded,
        }
    return {}


_DS_EXECUTION_AUTHORITY_KEYS: dict[str, tuple[str, ...]] = {
    "2.3": ("data_exploration_report",),
    "4.3": ("model_run",),
    "4.4": ("evaluation_bundle",),
}


def _execution_authoritative(execution: dict[str, Any], substep: str) -> bool:
    return any(
        execution.get(key) is not None
        for key in _DS_EXECUTION_AUTHORITY_KEYS.get(substep, ())
    )


def apply_response(
    data: dict,
    state: CrispDMState,
    substep: str,
    execution: dict[str, Any],
) -> StateDelta:
    """Map data-scientist JSON (or execution fallback) into shared state."""
    from maads.output_contracts import validate_agent_output

    if not _execution_authoritative(execution, substep):
        schema_errors = validate_agent_output("data_scientist", data, substep=substep)
        if schema_errors:
            return StateDelta(
                notes=f"DS {substep}: schema-invalid response: {schema_errors[0]}",
                failed=True,
            )

    su = (data or {}).get("state_updates") or {}
    du = su.get("du") or {}
    md = su.get("md") or {}
    ev = su.get("ev") or {}
    fields: list[str] = []

    if substep == "2.3":
        report = execution_or_llm(execution, du, "data_exploration_report")
        if not report:
            desc = state.du.data_description_report or {}
            report = {"n_rows": desc.get("n_rows"), "target": state.config.target_column}
        state.du.data_exploration_report = report
        fields.append("du.data_exploration_report")
    elif substep == "4.1":
        state.md.modeling_technique = md.get("modeling_technique") or "to be chosen at 4.3"
        state.md.modeling_assumptions = md.get("modeling_assumptions") or [
            "tabular features", "no leakage (pipeline fit on train only)",
        ]
        fields.extend(["md.modeling_technique", "md.modeling_assumptions"])
    elif substep == "4.2":
        state.md.test_design = md.get("test_design") or {
            "cv": "stratified_5fold",
            "metric": state.config.evaluation_metric,
        }
        fields.append("md.test_design")
    elif substep == "4.3":
        run = dict(execution.get("model_run") or {})
        llm_run = md.get("model_run") or {}
        if llm_run.get("description") and not run.get("description"):
            run["description"] = llm_run["description"]
        if not run:
            return StateDelta(notes="DS 4.3: no model execution evidence")
        technique = run.get("technique") or "unspecified"
        state.md.models.append(ModelRun(
            technique=technique,
            cv_score=run.get("cv_score"),
            cv_std=run.get("cv_std"),
            description=run.get("description") or "model run",
            parameter_settings=run.get("parameter_settings") or {},
        ))
        state.md.modeling_technique = technique
        fields.extend(["md.models", "md.modeling_technique"])
        if execution.get("degraded"):
            state.append_log(
                "data_scientist",
                "4.3 model training degraded to baseline fallback",
                level="warn",
            )
            record_degraded(state, substep, "data_scientist", "4.3 baseline fallback")
    elif substep == "4.4":
        bundle_raw = execution.get("evaluation_bundle")
        if state.md.models:
            best = max(state.md.models, key=lambda m: m.cv_score or 0.0)
            chosen = md.get("chosen_model_technique")
            if chosen:
                for m in state.md.models:
                    if m.technique == chosen:
                        best = m
                        break
            best.assessment = (
                execution.get("assessment")
                or md.get("assessment")
                or "selected: best CV score"
            )
            if bundle_raw:
                best.evaluation_bundle = EvaluationBundle.model_validate(bundle_raw)
            state.md.chosen_model = best
            fields.append("md.chosen_model")
        elif not bundle_raw:
            return StateDelta(notes="DS 4.4: no evaluation_bundle from execution", failed=True)
        if execution.get("degraded"):
            state.append_log(
                "data_scientist",
                "4.4 assessment degraded to baseline fallback",
                level="warn",
            )
            record_degraded(state, substep, "data_scientist", "4.4 baseline fallback")
    elif substep == "5.1":
        cv = state.md.chosen_model.cv_score if state.md.chosen_model else None
        thr = state.config.success_criterion.threshold
        state.ev.assessment_of_dm_results = ev.get("assessment_of_dm_results") or {
            "cv_score": cv,
            "threshold": thr,
            "meets": bool(cv is not None and cv >= thr),
        }
        fields.append("ev.assessment_of_dm_results")
        if state.md.chosen_model:
            state.ev.approved_models = [state.md.chosen_model]
            fields.append("ev.approved_models")

    summary = (data or {}).get("summary", "")
    return StateDelta(fields, notes=summary or f"DS completed {substep}")
