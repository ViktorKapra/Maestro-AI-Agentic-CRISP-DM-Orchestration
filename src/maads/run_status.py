"""File-based live run status (works without a TTY and during long LLM calls)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maads.artifact_config import live_summary_enabled
from maads.artifact_paths import RunPaths
from maads.conclusions import build_conclusions_summary
from maads.live_summary import build_live_summary
from maads.outcome import ml_outcome_deficits, ml_run_succeeded, workflow_complete
from maads.state import (
    SUBSTEP_NAMES,
    SUBSTEPS,
    CrispDMState,
    Phase,
    _pm_outputs_status,
    _trim_log,
)
from maads.token_budget import budget_status

TOTAL_SUBSTEPS = sum(len(v) for v in SUBSTEPS.values())

PHASE_NAMES: dict[int, str] = {
    int(Phase.BUSINESS_UNDERSTANDING): "Business Understanding",
    int(Phase.DATA_UNDERSTANDING): "Data Understanding",
    int(Phase.DATA_PREPARATION): "Data Preparation",
    int(Phase.MODELING): "Modeling",
    int(Phase.EVALUATION): "Evaluation",
    int(Phase.DEPLOYMENT): "Deployment",
}

_bound_dir: Path | None = None
_bound_state: CrispDMState | None = None
_activity: str = "starting"
_completed_substeps: int = 0


def bind_run(artifact_dir: Path, state: CrispDMState) -> None:
    """Attach the active run; writes an initial ``status.json`` immediately."""
    global _bound_dir, _bound_state, _completed_substeps, _activity
    _bound_dir = artifact_dir
    _bound_state = state
    _completed_substeps = 0
    _activity = "starting"
    RunPaths(artifact_dir).derived.mkdir(parents=True, exist_ok=True)
    flush_status()


def set_activity(message: str) -> None:
    global _activity
    _activity = message
    flush_status()


def record_substep_done(substep: str) -> None:
    global _completed_substeps, _activity
    _completed_substeps += 1
    _activity = f"finished {substep}"
    flush_status()


def flush_status() -> None:
    """Rewrite status artefacts under the artifact directory."""
    if _bound_dir is None or _bound_state is None:
        return
    state = _bound_state
    artifact_dir = _bound_dir.resolve()
    paths = RunPaths(artifact_dir)
    trace_dir = artifact_dir / "trace"
    payload: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": state.case_id,
        "phase": int(state.phase),
        "phase_name": PHASE_NAMES.get(int(state.phase), ""),
        "substep": state.substep,
        "substep_name": SUBSTEP_NAMES.get(state.substep, ""),
        "activity": _activity,
        "completed_substeps": _completed_substeps,
        "total_substeps": TOTAL_SUBSTEPS,
        "token_spend": dict(state.token_spend),
        "token_spend_by_provider": dict(state.token_spend_by_provider),
        "token_budget": budget_status(state),
        "halted": state.halted,
        "halt_reason": state.halt_reason,
        "workflow_complete": workflow_complete(state),
        "ml_success": ml_run_succeeded(state),
        "ml_deficits": ml_outcome_deficits(state),
        "artifact_dir": str(artifact_dir),
        "trace_dir": str(trace_dir),
        "status_file": str(artifact_dir / "status.json"),
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    paths.derived.mkdir(parents=True, exist_ok=True)
    status_text = json.dumps(payload, indent=2, default=str)
    (artifact_dir / "status.json").write_text(status_text, encoding="utf-8")
    (paths.derived / "status.json").write_text(status_text, encoding="utf-8")
    (artifact_dir / "status.md").write_text(_format_md(payload), encoding="utf-8")
    process_payload = _build_process_snapshot(state)
    process_text = json.dumps(process_payload, indent=2, default=str)
    (artifact_dir / "process.json").write_text(process_text, encoding="utf-8")
    (paths.derived / "process.json").write_text(process_text, encoding="utf-8")
    state_payload = _build_state_snapshot(state)
    state_text = json.dumps(state_payload, indent=2, default=str)
    (artifact_dir / "state.json").write_text(state_text, encoding="utf-8")
    (paths.derived / "state_snapshot.json").write_text(state_text, encoding="utf-8")

    if live_summary_enabled():
        summary = build_live_summary(
            state,
            activity=_activity,
            completed_substeps=_completed_substeps,
            artifact_dir=str(artifact_dir),
            trace_dir=str(trace_dir),
        )
        (paths.live_summary()).write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8",
        )


def _build_state_snapshot(state: CrispDMState) -> dict[str, Any]:
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "state": state.model_dump(mode="json"),
    }


def _conclusions_summary(state: CrispDMState) -> dict[str, Any]:
    return build_conclusions_summary(state)


def _build_process_snapshot(state: CrispDMState) -> dict[str, Any]:
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "outputs_status": _pm_outputs_status(state),
        "loop_history": [le.model_dump(mode="json") for le in state.loop_history],
        "validator_findings": list(state.validator_findings),
        "recent_log": _trim_log(state.log, n=20),
        "conclusions": _conclusions_summary(state),
        "config": {
            "problem_statement": state.config.problem_statement,
            "problem_type": state.config.problem_type,
            "target_column": state.config.target_column,
            "evaluation_metric": state.config.evaluation_metric,
        },
    }


def _format_md(payload: dict[str, Any]) -> str:
    tokens = payload.get("token_spend") or {}
    total_tokens = sum(tokens.values()) if tokens else 0
    lines = [
        f"# Run status — {payload.get('case_id', '?')}",
        "",
        f"- **Updated:** {payload.get('updated_at', '?')}",
        f"- **Phase:** {payload.get('phase')} — {payload.get('phase_name', '')}",
        f"- **Substep:** {payload.get('substep')} — {payload.get('substep_name', '')}",
        f"- **Activity:** {payload.get('activity', '')}",
        (
            f"- **Progress:** {payload.get('completed_substeps', 0)}"
            f"/{payload.get('total_substeps', TOTAL_SUBSTEPS)} substeps"
        ),
        f"- **Tokens:** {total_tokens} {dict(tokens) if tokens else ''}",
    ]
    budget = payload.get("token_budget") or {}
    if budget.get("cap") is not None:
        lines.append(
            f"- **Token budget:** {budget.get('spent', 0)}/{budget.get('cap')} "
            f"({budget.get('pct', '?')}%, remaining {budget.get('remaining', '?')})"
        )
        if budget.get("soft_limit"):
            lines.append("- **Token soft limit:** active (DEBUG repairs degraded)")
    lines.extend([
        f"- **Artifacts:** `{payload.get('artifact_dir', '')}`",
        f"- **Trace:** `{payload.get('trace_dir', '')}`",
    ])
    if payload.get("halted"):
        lines.append(f"- **Halted:** {payload.get('halt_reason', '')}")
    if payload.get("workflow_complete") is not None:
        lines.append(
            f"- **Workflow complete:** {payload.get('workflow_complete')}"
        )
    if payload.get("ml_success") is not None:
        lines.append(f"- **ML success:** {payload.get('ml_success')}")
        deficits = payload.get("ml_deficits") or []
        if deficits:
            lines.append(f"- **ML deficits:** {'; '.join(deficits)}")
    return "\n".join(lines) + "\n"
