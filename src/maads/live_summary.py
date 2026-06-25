"""Build ``derived/live_summary.json`` for dashboard polling."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from maads.observability.collector import get_collector
from maads.observability.llm_communications import get_communication_registry
from maads.outcome import ml_outcome_deficits, ml_run_succeeded, workflow_complete
from maads.state import SUBSTEP_NAMES, SUBSTEPS, CrispDMState, Phase

TOTAL_SUBSTEPS = sum(len(v) for v in SUBSTEPS.values())

PHASE_NAMES: dict[int, str] = {
    int(Phase.BUSINESS_UNDERSTANDING): "Business Understanding",
    int(Phase.DATA_UNDERSTANDING): "Data Understanding",
    int(Phase.DATA_PREPARATION): "Data Preparation",
    int(Phase.MODELING): "Modeling",
    int(Phase.EVALUATION): "Evaluation",
    int(Phase.DEPLOYMENT): "Deployment",
}


def _completed_from_trace() -> int:
    coll = get_collector()
    run = coll.run
    if run is None:
        return 0
    ended: set[str] = set()
    for evt in run.events:
        if evt.type == "substep.end":
            sub = evt.attributes.get("substep")
            if sub:
                ended.add(str(sub))
    return len(ended)


def _in_flight_comm() -> dict[str, Any] | None:
    reg = get_communication_registry()
    for rec in reversed(reg.all_records()):
        if not rec.closed:
            return {
                "communication_id": rec.id,
                "agent": rec.agent_name,
                "substep": rec.substep,
                "model": rec.model,
            }
    return None


def _last_comm() -> dict[str, Any] | None:
    reg = get_communication_registry()
    records = reg.all_records()
    if not records:
        return None
    rec = records[-1]
    return {
        "id": rec.id,
        "agent": rec.agent_name,
        "substep": rec.substep,
        "parse_ok": rec.outcome.get("parse_ok"),
        "json_valid": rec.outcome.get("json_valid"),
        "schema_ok": rec.outcome.get("schema_ok"),
        "tokens": rec.tokens.get("total"),
    }


def _elapsed_ms() -> int | None:
    coll = get_collector()
    run = coll.run
    if run is None:
        return None
    if run.events:
        return int(run.events[-1].ts_mono_ms)
    return 0


def build_live_summary(
    state: CrispDMState,
    *,
    activity: str,
    completed_substeps: int,
    artifact_dir: str,
    trace_dir: str,
) -> dict[str, Any]:
    trace_completed = _completed_from_trace()
    progress_completed = max(completed_substeps, trace_completed)
    coll = get_collector()
    run = coll.run
    last_comm = _last_comm()
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": state.case_id,
        "phase": int(state.phase),
        "phase_name": PHASE_NAMES.get(int(state.phase), ""),
        "substep": state.substep,
        "substep_name": SUBSTEP_NAMES.get(state.substep, ""),
        "activity": activity,
        "progress": {
            "completed_substeps": progress_completed,
            "total_substeps": TOTAL_SUBSTEPS,
            "source": "trace" if trace_completed > completed_substeps else "counter",
        },
        "halted": state.halted,
        "halt_reason": state.halt_reason,
        "workflow_complete": workflow_complete(state),
        "ml_success": ml_run_succeeded(state),
        "ml_deficits": ml_outcome_deficits(state),
        "token_spend": dict(state.token_spend),
        "token_spend_by_provider": dict(state.token_spend_by_provider),
        "elapsed_ms": _elapsed_ms(),
        "trace": {
            "run_id": run.run_id if run else None,
            "started_at": run.started_at.isoformat() if run else None,
            "ended_at": run.ended_at.isoformat() if run and run.ended_at else None,
            "event_count": len(run.events) if run else 0,
        },
        "in_flight": _in_flight_comm(),
        "last_comm": last_comm,
        "pointers": {
            "status": "status.json",
            "process": "process.json",
            "communications_since": last_comm["id"] if last_comm else None,
        },
        "artifact_dir": artifact_dir,
        "trace_dir": trace_dir,
    }
