"""Developer capabilities — deployment and submission."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from maads.codegen import run_authored_code
from maads.capabilities.shared import abspath as _abspath, has_keys as _has_keys
from maads.deltas import StateDelta
from maads.knowledge_setup import append_experience_to_knowledge
from maads.state import CrispDMState
from maads.tools import FileIO, PythonExec

_SUBMISSION_INSTRUCTION = (
    "CRISP-DM 6.1 Build Submission: refit the chosen model approach on the full "
    "training set, generate predictions for the prepared test set, and write "
    "OUTPUT_PATH. Load SAMPLE_SUBMISSION as the authoritative schema template — "
    "column names, dtypes, and row count must match exactly before writing. "
    "Parse CHOSEN_MODEL for technique and parameter_settings; mirror the pipeline "
    "that passed evaluation in Phase 4–5. Respect PROBLEM_TYPE and EVAL_METRIC "
    "(e.g. log-transform the target when the metric name contains 'log'). "
    "When TEXT_COLUMN is non-empty, treat this as NLP-primary and use that column "
    "as the main feature (parse FEATURE_HINTS for weak categoricals if needed). "
    "Join predictions to ID_COL from the test records; never reorder or drop rows. "
    "Never treat the sample submission as ground-truth labels."
)


def _submission_contract(sample_csv: str) -> callable:
    sample_path = Path(sample_csv)
    sample_cols: list[str] | None = None
    expected_rows: int | None = None
    if sample_path.is_file():
        sample = pd.read_csv(sample_path)
        sample_cols = list(sample.columns)
        expected_rows = len(sample)

    def contract(payload: dict) -> list[str]:
        errors = _has_keys(payload, "submission_path", "rows")
        if errors:
            return errors
        path = Path(str(payload["submission_path"]))
        if not path.is_file():
            return [f"submission file not found: {path}"]
        try:
            sub = pd.read_csv(path)
        except Exception as exc:
            return [f"submission not readable: {exc}"]
        if sample_cols is not None and list(sub.columns) != sample_cols:
            return [f"columns {list(sub.columns)} != sample {sample_cols}"]
        if expected_rows is not None and len(sub) != expected_rows:
            return [f"row count {len(sub)} != sample {expected_rows}"]
        rows = payload.get("rows")
        if not isinstance(rows, int) or rows != len(sub):
            return ["rows must be an int matching the written file"]
        return []

    return contract


def _primary_text_column(feature_hints: dict) -> str:
    for key in ("text_free", "text"):
        cols = feature_hints.get(key)
        if isinstance(cols, list) and cols:
            return str(cols[0])
    return ""


def build_submission(
    pyexec: PythonExec,
    state: CrispDMState,
    artifact_dir: Path,
) -> StateDelta:
    dataset_train = state.dp.dataset.get("train")
    dataset_test = state.dp.dataset.get("test")
    if not dataset_train or not dataset_test:
        raise RuntimeError("6.1 requires prepared dataset train and test parquet paths")

    out = str((artifact_dir / "submission.csv").resolve())
    sample = _abspath(state.config.data.sample_submission_csv)
    chosen = state.md.chosen_model.model_dump() if state.md.chosen_model else {}
    feature_hints = state.config.feature_hints or {}

    res = run_authored_code(
        pyexec=pyexec,
        agent_name="developer",
        state=state,
        instruction=_SUBMISSION_INSTRUCTION,
        header_vars={
            "TRAIN_PARQUET": dataset_train,
            "TEST_PARQUET": dataset_test,
            "TARGET": state.config.target_column,
            "ID_COL": state.config.id_column,
            "PROBLEM_TYPE": state.config.problem_type,
            "EVAL_METRIC": state.config.evaluation_metric,
            "SAMPLE_SUBMISSION": sample,
            "OUTPUT_PATH": out,
            "CHOSEN_MODEL": json.dumps(chosen),
            "FEATURE_HINTS": json.dumps(feature_hints),
            "TEXT_COLUMN": _primary_text_column(feature_hints),
        },
        contract=_submission_contract(sample),
        contract_hint=(
            "Required keys: submission_path (str, absolute path to written CSV), "
            "rows (int, must match file and sample submission row count)."
        ),
        artifact_dir=artifact_dir,
    )

    state.dep.submission_path = res.payload["submission_path"]
    state.dep.deployment_plan = (
        f"Agent-authored submission from {chosen.get('technique', 'chosen model')}; "
        f"validated against sample template."
    )
    return StateDelta(["dep.submission_path", "dep.deployment_plan"])


def plan_monitoring(state: CrispDMState) -> StateDelta:
    state.dep.monitoring_and_maintenance_plan = "Re-run on data refresh; watch CV vs leaderboard gap."
    return StateDelta(["dep.monitoring_and_maintenance_plan"])


def experience_review(state: CrispDMState) -> StateDelta:
    loops = [le.label for le in state.loop_history]
    deg = state.degraded_flags
    experience = (
        f"# Experience — {state.case_id}\n\n"
        f"- Loops fired: {loops or 'none'}\n"
        f"- Degraded steps: {deg or 'none'}\n"
        f"- Chosen model: "
        f"{state.md.chosen_model.technique if state.md.chosen_model else 'n/a'}\n"
        f"- CV: {state.md.chosen_model.cv_score if state.md.chosen_model else 'n/a'}\n"
    )
    state.dep.experience_documentation = experience
    append_experience_to_knowledge(state.case_id, experience)
    return StateDelta(["dep.experience_documentation"])
