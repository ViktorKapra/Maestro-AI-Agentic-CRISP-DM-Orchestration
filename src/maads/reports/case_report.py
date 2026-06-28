"""Evidence-backed case report (What / How / Why)."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maads.conclusions import build_conclusions_summary
from maads.outcome import ml_outcome_deficits, ml_run_succeeded, workflow_complete
from maads.reports.md_paths import md_file_link
from maads.state import CrispDMState
from maads.reports.report_format import format_token_spend
from maads.token_budget import build_spending_summary, format_spending_lines


def _evidence(ref_type: str, ref: str) -> dict[str, str]:
    return {"type": ref_type, "ref": ref}


def build_case_report(state: CrispDMState) -> dict[str, Any]:
    conclusions = build_conclusions_summary(state)
    what: dict[str, Any] = {
        "workflow_complete": workflow_complete(state),
        "ml_success": ml_run_succeeded(state),
        "ml_deficits": ml_outcome_deficits(state),
        "chosen_model": conclusions.get("chosen_model"),
        "models": conclusions.get("models"),
        "submission_path": conclusions.get("submission_path"),
        "final_report_path": conclusions.get("final_report_path"),
        "dataset_paths": conclusions.get("dataset_paths"),
        "assessment": conclusions.get("assessment"),
        "decision": conclusions.get("decision"),
    }
    how: dict[str, Any] = {
        "phase": int(state.phase),
        "substep": state.substep,
        "halt_reason": state.halt_reason,
        "loops": [
            {
                "label": le.label,
                "from_phase": le.from_phase,
                "to_phase": le.to_phase,
                "reason": le.reason,
                "evidence": [_evidence("loop_history", f"state.loop_history[{i}]")],
            }
            for i, le in enumerate(state.loop_history)
        ],
        "degraded_flags": list(state.degraded_flags),
        "token_spend": dict(state.token_spend),
        "spending_summary": build_spending_summary(state),
        "validator_findings": list(state.validator_findings),
    }
    why: list[dict[str, Any]] = []
    if state.bu.data_mining_goals:
        why.append({
            "claim": f"Data mining goals: {state.bu.data_mining_goals[:200]}",
            "evidence": [_evidence("state", "state.bu.data_mining_goals")],
        })
    for i, le in enumerate(state.loop_history):
        why.append({
            "claim": f"Loop {le.label}: returned to phase {le.to_phase} — {le.reason}",
            "evidence": [_evidence("loop_history", f"state.loop_history[{i}]")],
        })
    if state.md.chosen_model:
        cm = state.md.chosen_model
        why.append({
            "claim": f"Selected {cm.technique} (CV {cm.cv_score})",
            "evidence": [_evidence("state", "state.md.chosen_model")],
        })
    if state.ev.decision:
        why.append({
            "claim": f"Evaluation decision: {state.ev.decision}",
            "evidence": [_evidence("state", "state.ev.decision")],
        })
    for phase in conclusions.get("phases") or []:
        for item in phase.get("items") or []:
            refs = list(item.get("evidence_refs") or [])
            if refs:
                why.append({
                    "claim": item.get("summary", ""),
                    "evidence": refs,
                })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": state.case_id,
        "what": what,
        "how": how,
        "why": why,
        "conclusions": conclusions,
    }


def render_case_report_md(
    report: dict[str, Any],
    *,
    md_dir: Path | None = None,
    run_dir: Path | None = None,
    remap: Callable[[Path], Path] | None = None,
) -> str:
    what = report.get("what") or {}
    how = report.get("how") or {}
    lines = [
        f"# Case report — {report.get('case_id', '?')}",
        "",
        f"*Generated {report.get('generated_at', '')}*",
        "",
        "## What?",
        "",
        f"- **Workflow complete:** {what.get('workflow_complete')}",
        f"- **ML success:** {what.get('ml_success')}",
    ]
    deficits = what.get("ml_deficits") or []
    if deficits:
        lines.append(f"- **ML deficits:** {'; '.join(deficits)}")
    chosen = what.get("chosen_model")
    if chosen:
        lines.append(
            f"- **Model:** {chosen.get('technique')} "
            f"(CV {chosen.get('cv_score')})"
        )
    if what.get("submission_path"):
        sub = what["submission_path"]
        if md_dir is not None and run_dir is not None:
            link = md_file_link(sub, md_dir=md_dir, run_dir=run_dir, remap=remap)
            lines.append(f"- **Submission:** {link or sub}")
        else:
            lines.append(f"- **Submission:** `{sub}`")
    if what.get("decision"):
        lines.append(f"- **Decision:** {what['decision']}")
    lines.extend(["", "## How?", ""])
    if how.get("halt_reason"):
        lines.append(f"- Halt reason: {how['halt_reason']}")
    spending = how.get("spending_summary")
    if spending:
        lines.extend(format_spending_lines(spending))
    else:
        lines.extend(format_token_spend(how.get("token_spend")))
    for loop in how.get("loops") or []:
        lines.append(
            f"- Loop **{loop.get('label')}** "
            f"(phase {loop.get('from_phase')} → {loop.get('to_phase')}): "
            f"{loop.get('reason')}"
        )
    degraded = how.get("degraded_flags") or []
    if degraded:
        lines.append(f"- Degraded steps: {', '.join(degraded)}")
    lines.extend(["", "## Why?", ""])
    for entry in report.get("why") or []:
        claim = entry.get("claim", "")
        refs = ", ".join(
            f"{r.get('type')}:{r.get('ref')}" for r in (entry.get("evidence") or [])
        )
        lines.append(f"- {claim}")
        if refs:
            lines.append(f"  - *Evidence:* {refs}")
    return "\n".join(lines) + "\n"
