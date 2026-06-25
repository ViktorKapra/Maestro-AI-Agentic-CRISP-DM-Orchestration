"""Thin post-run summary for quick postmortems."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maads.artifact_paths import RunPaths
from maads.conclusions import build_conclusions_summary
from maads.observability.llm_communications import build_communications_summary
from maads.observability.schema import TraceRun
from maads.outcome import ml_outcome_deficits, ml_run_succeeded, workflow_complete
from maads.state import CrispDMState


def _sandbox_stats(paths: RunPaths) -> dict[str, Any]:
    manifest = paths.sandbox_manifest()
    if not manifest.is_file():
        return {"attempts": 0, "failures": 0}
    attempts = 0
    failures = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        attempts += 1
        try:
            row = json.loads(line)
            if not row.get("ok"):
                failures += 1
        except json.JSONDecodeError:
            failures += 1
    return {"attempts": attempts, "failures": failures}


def build_postmortem(
    state: CrispDMState,
    paths: RunPaths,
    *,
    trace: TraceRun | None = None,
    comm_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conclusions = build_conclusions_summary(state)
    loops = [
        {
            "label": le.label,
            "from_phase": le.from_phase,
            "to_phase": le.to_phase,
            "reason": le.reason,
            "ts": le.t,
            "evidence": f"state.loop_history[{i}]",
        }
        for i, le in enumerate(state.loop_history)
    ]
    started_at = trace.started_at.isoformat() if trace else None
    ended_at = trace.ended_at.isoformat() if trace and trace.ended_at else datetime.now(timezone.utc).isoformat()
    duration_ms = None
    if trace and trace.events:
        duration_ms = int(trace.events[-1].ts_mono_ms)
    comm_summary = comm_summary or {}
    submission = state.dep.submission_path
    sub_exists = bool(submission and Path(submission).is_file())
    if not sub_exists and submission:
        rel = Path(submission)
        if not rel.is_absolute():
            sub_exists = (paths.run_dir / rel).is_file()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": paths.run_dir.name,
        "case_id": state.case_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "halt_reason": state.halt_reason,
        "workflow_complete": workflow_complete(state),
        "ml_success": ml_run_succeeded(state),
        "ml_deficits": ml_outcome_deficits(state),
        "loops": loops,
        "token_spend": dict(state.token_spend),
        "token_spend_by_provider": dict(state.token_spend_by_provider),
        "parse_failures": comm_summary.get("parse_failures", 0),
        "llm_turns": comm_summary.get("turn_count", 0),
        "sandbox": _sandbox_stats(paths),
        "degraded_flags": list(state.degraded_flags),
        "validator_findings": list(state.validator_findings),
        "deliverables": {
            "submission": submission,
            "submission_exists": sub_exists,
            "final_report": state.dep.final_report_path,
            "chosen_model": (
                state.md.chosen_model.technique if state.md.chosen_model else None
            ),
            "cv_score": (
                state.md.chosen_model.cv_score if state.md.chosen_model else None
            ),
        },
        "conclusions_headline": {
            "decision": conclusions.get("decision"),
            "assessment": conclusions.get("assessment"),
        },
        "drill_down": {
            "communications": "collected/communications.jsonl",
            "trace": "derived/trace.json",
            "sandbox_manifest": "collected/sandbox/manifest.jsonl",
            "process": "process.json",
            "final_state": "final_state.json",
        },
    }
