"""Deterministic per-run execution analysis report."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.artifact_paths import RunPaths
from maads.conclusions import build_conclusions_summary
from maads.observability.schema import TraceRun
from maads.outcome import ml_outcome_deficits, ml_run_succeeded, workflow_complete
from maads.reports.postmortem import _sandbox_stats
from maads.state import CrispDMState
from maads.success_criterion import assessment_meets, criterion_direction


def _sandbox_failures(paths: RunPaths) -> list[dict[str, Any]]:
    manifest = paths.sandbox_manifest()
    if not manifest.is_file():
        return []
    failures: list[dict[str, Any]] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not row.get("ok"):
            failures.append({
                "substep": row.get("substep"),
                "label": row.get("label"),
                "script": row.get("script"),
                "return_code": row.get("return_code"),
            })
    return failures


def build_execution_analysis(
    state: CrispDMState,
    paths: RunPaths,
    *,
    trace: TraceRun | None = None,
    comm_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured execution analysis bundle for one run."""
    conclusions = build_conclusions_summary(state)
    comm_summary = comm_summary or {}
    sc = state.config.success_criterion
    cm = state.md.chosen_model
    assessment = state.ev.assessment_of_dm_results or {}
    dir_ = criterion_direction(sc.metric, sc.direction)

    started_at = trace.started_at.isoformat() if trace else None
    ended_at = (
        trace.ended_at.isoformat()
        if trace and trace.ended_at
        else None
    )
    duration_ms = int(trace.events[-1].ts_mono_ms) if trace and trace.events else None

    deliverables: dict[str, Any] = {
        "submission": state.dep.submission_path,
        "submission_exists": bool(
            state.dep.submission_path and Path(state.dep.submission_path).is_file()
        ),
        "final_report": state.dep.final_report_path,
        "train_parquet": (state.dp.dataset or {}).get("train"),
        "test_parquet": (state.dp.dataset or {}).get("test"),
        "figures_dir": state.dep.figures_dir,
    }

    model_block: dict[str, Any] | None = None
    if cm:
        model_block = {
            "technique": cm.technique,
            "cv_score": cm.cv_score,
            "cv_std": cm.cv_std,
            "assessment": cm.assessment,
        }
        if cm.evaluation_bundle:
            model_block["evaluation_metrics"] = dict(cm.evaluation_bundle.metrics)

    return {
        "case_id": state.case_id,
        "run_id": paths.run_dir.name,
        "artifact_dir": str(paths.run_dir),
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "halt_reason": state.halt_reason,
        "workflow_complete": workflow_complete(state),
        "ml_success": ml_run_succeeded(state),
        "ml_deficits": ml_outcome_deficits(state),
        "success_criterion": {
            "metric": sc.metric,
            "threshold": sc.threshold,
            "direction": dir_,
            "met": assessment_meets(assessment),
        },
        "assessment": assessment,
        "decision": state.ev.decision,
        "chosen_model": model_block,
        "token_spend": dict(state.token_spend),
        "llm_turns": comm_summary.get("turn_count", 0),
        "sandbox": _sandbox_stats(paths),
        "sandbox_failures": _sandbox_failures(paths),
        "loops": [
            {
                "label": le.label,
                "from_phase": le.from_phase,
                "to_phase": le.to_phase,
                "reason": le.reason,
            }
            for le in state.loop_history
        ],
        "degraded_flags": list(state.degraded_flags),
        "deliverables": deliverables,
        "conclusions": conclusions,
    }


def render_execution_analysis_md(bundle: dict[str, Any]) -> str:
    """Render human-readable execution analysis markdown."""
    lines: list[str] = [
        f"# Execution Analysis — {bundle.get('case_id', '?')}",
        "",
        f"**Run ID:** `{bundle.get('run_id', '?')}`",
        "",
        "## Executive Summary",
        "",
    ]

    sc = bundle.get("success_criterion") or {}
    cm = bundle.get("chosen_model") or {}
    cv = cm.get("cv_score")
    thr = sc.get("threshold")
    met = sc.get("met")
    wf = bundle.get("workflow_complete")
    ml_ok = bundle.get("ml_success")

    lines.append(f"- **Workflow complete:** {wf}")
    lines.append(f"- **ML success:** {ml_ok}")
    if bundle.get("ml_deficits"):
        lines.append(f"- **ML deficits:** {'; '.join(bundle['ml_deficits'])}")
    if cv is not None and thr is not None:
        lines.append(
            f"- **Model CV ({sc.get('metric', '?')}):** {cv:.4f} "
            f"(threshold {thr}, {sc.get('direction', '?')}) — "
            f"{'met' if met else 'not met'}"
        )
    if bundle.get("decision"):
        lines.append(f"- **Deployment decision:** {bundle['decision']}")
    lines.append("")

    lines.extend([
        "## Run Metadata",
        "",
        f"- **Started:** {bundle.get('started_at', 'n/a')}",
        f"- **Ended:** {bundle.get('ended_at', 'n/a')}",
        f"- **Duration (ms):** {bundle.get('duration_ms', 'n/a')}",
        f"- **Halt reason:** {bundle.get('halt_reason', 'n/a')}",
        f"- **LLM turns:** {bundle.get('llm_turns', 0)}",
        f"- **Token spend:** {bundle.get('token_spend', {})}",
        "",
    ])

    sandbox = bundle.get("sandbox") or {}
    lines.extend([
        "## Sandbox Execution",
        "",
        f"- **Attempts:** {sandbox.get('attempts', 0)}",
        f"- **Failures:** {sandbox.get('failures', 0)}",
        "",
    ])
    failures = bundle.get("sandbox_failures") or []
    if failures:
        lines.append("### Failed Attempts (recovered)")
        lines.append("")
        for f in failures:
            lines.append(
                f"- Substep {f.get('substep')}: {f.get('label')} "
                f"({f.get('script')}, rc={f.get('return_code')})"
            )
        lines.append("")

    conclusions = bundle.get("conclusions") or {}
    phases = conclusions.get("phases") or []
    if phases:
        lines.extend(["## Phase Summaries", ""])
        for phase in phases:
            name = phase.get("phase_name", phase.get("phase", "?"))
            lines.append(f"### {name}")
            lines.append("")
            for item in phase.get("items") or []:
                sub = item.get("substep", "?")
                summary = item.get("summary", "")
                lines.append(f"- **{sub}:** {summary}")
            lines.append("")

    if cm:
        lines.extend(["## Model Results", ""])
        lines.append(f"- **Technique:** {cm.get('technique', '?')}")
        if cv is not None:
            std = cm.get("cv_std")
            std_s = f" ± {std:.4f}" if std is not None else ""
            lines.append(f"- **CV score:** {cv:.4f}{std_s}")
        metrics = cm.get("evaluation_metrics") or {}
        if metrics:
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("| --- | --- |")
            for key, val in sorted(metrics.items()):
                if isinstance(val, float):
                    lines.append(f"| {key} | {val:.4f} |")
                else:
                    lines.append(f"| {key} | {val} |")
        lines.append("")

    dq_blockers = conclusions.get("data_quality_blockers") or []
    dq_tolerable = conclusions.get("data_quality_tolerable") or []
    if dq_blockers or dq_tolerable:
        lines.extend(["## Data Quality", ""])
        if dq_blockers:
            lines.append("**Blockers:**")
            for b in dq_blockers:
                lines.append(f"- {b}")
            lines.append("")
        if dq_tolerable:
            lines.append("**Tolerable:**")
            for t in dq_tolerable[:8]:
                lines.append(f"- {t}")
            if len(dq_tolerable) > 8:
                lines.append(f"- _…and {len(dq_tolerable) - 8} more_")
            lines.append("")

    loops = bundle.get("loops") or []
    if loops:
        lines.extend(["## Loops", ""])
        for le in loops:
            lines.append(
                f"- Loop {le.get('label')}: phase {le.get('from_phase')} "
                f"→ {le.get('to_phase')} — {le.get('reason')}"
            )
        lines.append("")

    deliverables = bundle.get("deliverables") or {}
    lines.extend(["## Deliverables", ""])
    for key, path in deliverables.items():
        if key.endswith("_exists"):
            continue
        lines.append(f"- **{key}:** `{path}`")
    lines.append("")

    lines.extend(["## Outcome Verdict", ""])
    if met and ml_ok:
        lines.append(
            "The run met the configured success criterion and produced all core ML deliverables."
        )
    elif met and not ml_ok:
        lines.append(
            "The model met the success criterion but other ML deliverables are missing "
            f"({'; '.join(bundle.get('ml_deficits') or [])})."
        )
    elif not met and wf:
        lines.append(
            "The workflow completed but the model did not meet the success criterion."
        )
    else:
        lines.append(f"Workflow status: complete={wf}, ml_success={ml_ok}.")
    lines.append("")

    return "\n".join(lines)
