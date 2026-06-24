"""Developer capabilities — deployment and submission."""
from __future__ import annotations

from pathlib import Path

from maads.baselines import (
    _NLP_SUBMIT_SRC,
    _SUBMIT_SRC,
    is_nlp_case,
    primary_text_column,
)
from maads.capabilities.shared import abspath as _abspath, run_snippet as _run_snippet
from maads.deltas import StateDelta
from maads.knowledge_setup import append_experience_to_knowledge
from maads.state import CrispDMState
from maads.tools import FileIO, PythonExec


def build_submission(
    pyexec: PythonExec,
    state: CrispDMState,
    artifact_dir: Path,
) -> StateDelta:
    out = str((artifact_dir / "submission.csv").resolve())
    if is_nlp_case(state.config.feature_hints):
        text_col = primary_text_column(state.config.feature_hints) or "text"
        submit_src = _NLP_SUBMIT_SRC
        subs = dict(
            __TRAIN__=state.dp.dataset["train"], __TEST__=state.dp.dataset["test"],
            __TARGET__=state.config.target_column, __ID__=state.config.id_column,
            __TEXT_COL__=text_col, __SAMPLE__=_abspath(state.config.data.sample_submission_csv),
            __OUT__=out,
        )
    else:
        submit_src = _SUBMIT_SRC
        subs = dict(
            __TRAIN__=state.dp.dataset["train"], __TEST__=state.dp.dataset["test"],
            __TARGET__=state.config.target_column, __ID__=state.config.id_column,
            __SAMPLE__=_abspath(state.config.data.sample_submission_csv), __OUT__=out,
        )
    info = _run_snippet(pyexec, submit_src, **subs)
    state.dep.submission_path = info["submission_path"]
    state.dep.deployment_plan = "Refit on full train, predict test, write submission.csv."
    return StateDelta(["dep.submission_path", "dep.deployment_plan"])


def plan_monitoring(state: CrispDMState) -> StateDelta:
    state.dep.monitoring_and_maintenance_plan = "Re-run on data refresh; watch CV vs leaderboard gap."
    return StateDelta(["dep.monitoring_and_maintenance_plan"])


def write_final_report(fileio: FileIO, state: CrispDMState) -> StateDelta:
    lines = [
        f"# Final report — {state.case_id}",
        f"- Technique: {state.md.modeling_technique}",
        f"- CV score: {state.md.chosen_model.cv_score if state.md.chosen_model else 'n/a'}",
        f"- Submission: {state.dep.submission_path}",
    ]
    path = fileio.write_text("final_report.md", "\n".join(lines))
    state.dep.final_report_path = str(path)
    return StateDelta(["dep.final_report_path"])


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
