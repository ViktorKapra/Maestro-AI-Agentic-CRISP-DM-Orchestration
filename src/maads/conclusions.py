"""Phase-aware conclusions projection for the Process dashboard."""
from __future__ import annotations

from typing import Any

from maads.state import (
    SUBSTEP_NAMES,
    CrispDMState,
    Phase,
    _quality_blockers,
)

_PHASE_NAMES: dict[int, str] = {
    int(Phase.BUSINESS_UNDERSTANDING): "Business Understanding",
    int(Phase.DATA_UNDERSTANDING): "Data Understanding",
    int(Phase.DATA_PREPARATION): "Data Preparation",
    int(Phase.MODELING): "Modeling",
    int(Phase.EVALUATION): "Evaluation",
    int(Phase.DEPLOYMENT): "Deployment",
}


def build_conclusions_summary(state: CrispDMState) -> dict[str, Any]:
    """Merge legacy headline fields with per-phase substep conclusions."""
    bu, du, dp, md, ev, dep = state.bu, state.du, state.dp, state.md, state.ev, state.dep
    models = [
        {
            "technique": m.technique,
            "cv_score": m.cv_score,
            "assessment": m.assessment,
        }
        for m in md.models
    ]
    chosen = None
    if md.chosen_model:
        chosen = {
            "technique": md.chosen_model.technique,
            "cv_score": md.chosen_model.cv_score,
            "assessment": md.chosen_model.assessment,
        }
    phases = _phase_conclusions(state)
    return {
        "business_objectives": bu.business_objectives,
        "data_mining_goals": bu.data_mining_goals,
        "data_quality_blockers": _quality_blockers(du.data_quality_report),
        "data_quality_tolerable": _quality_tolerable(du.data_quality_report),
        "dataset_paths": dict(dp.dataset) if dp.dataset else {},
        "dataset_description": dp.dataset_description,
        "models": models,
        "chosen_model": chosen,
        "assessment": ev.assessment_of_dm_results,
        "decision": ev.decision,
        "submission_path": dep.submission_path,
        "final_report_path": dep.final_report_path,
        "phases": phases,
    }


def _quality_tolerable(report: dict[str, Any] | None) -> list[str]:
    if not report:
        return []
    return list(report.get("tolerable", []))


def _phase_conclusions(state: CrispDMState) -> list[dict[str, Any]]:
    builders = {
        int(Phase.BUSINESS_UNDERSTANDING): _bu_phase,
        int(Phase.DATA_UNDERSTANDING): _du_phase,
        int(Phase.DATA_PREPARATION): _dp_phase,
        int(Phase.MODELING): _md_phase,
        int(Phase.EVALUATION): _ev_phase,
        int(Phase.DEPLOYMENT): _dep_phase,
    }
    out: list[dict[str, Any]] = []
    for phase_id in sorted(builders):
        items = builders[phase_id](state)
        if items:
            out.append({
                "id": phase_id,
                "name": _PHASE_NAMES.get(phase_id, str(phase_id)),
                "items": items,
            })
    return out


def _item(
    substep: str,
    *,
    summary: str,
    highlights: list[dict[str, str]] | None = None,
    artifact_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": substep,
        "name": SUBSTEP_NAMES.get(substep, substep),
        "summary": summary,
    }
    if highlights:
        payload["highlights"] = highlights
    if artifact_paths:
        payload["artifact_paths"] = artifact_paths
    return payload


def _bu_phase(state: CrispDMState) -> list[dict[str, Any]]:
    bu = state.bu
    items: list[dict[str, Any]] = []

    if bu.business_objectives or bu.background or bu.business_success_criteria:
        highlights = _highlights_from(
            ("Background", bu.background),
            ("Success criteria", bu.business_success_criteria),
        )
        summary = bu.business_objectives or bu.background or "Business objectives recorded."
        items.append(_item("1.1", summary=summary, highlights=highlights))

    situation = _any_filled(
        bu.inventory_of_resources,
        bu.requirements_assumptions_constraints,
        bu.risks_and_contingencies,
        bu.terminology,
        bu.costs_and_benefits,
    )
    if situation:
        highlights = _highlights_from(
            ("Resources", _fmt_value(bu.inventory_of_resources)),
            ("Requirements", _fmt_value(bu.requirements_assumptions_constraints)),
            ("Risks", _join_list(bu.risks_and_contingencies)),
            ("Terminology", _fmt_terminology(bu.terminology)),
        )
        items.append(_item(
            "1.2",
            summary="Situation assessed with resources, constraints, and risks.",
            highlights=highlights,
        ))

    if bu.data_mining_goals or bu.data_mining_success_criteria:
        highlights = _highlights_from(
            ("Success criteria", bu.data_mining_success_criteria),
        )
        items.append(_item(
            "1.3",
            summary=bu.data_mining_goals or "Data mining goals recorded.",
            highlights=highlights,
        ))

    if bu.project_plan or bu.initial_assessment_of_tools_and_techniques:
        highlights = _highlights_from(
            ("Plan steps", _join_list(bu.project_plan)),
            ("Tools & techniques", _fmt_value(bu.initial_assessment_of_tools_and_techniques)),
        )
        plan_summary = (
            f"{len(bu.project_plan)} plan step(s) defined."
            if bu.project_plan
            else "Initial tools and techniques assessed."
        )
        items.append(_item("1.4", summary=plan_summary, highlights=highlights))

    return items


def _du_phase(state: CrispDMState) -> list[dict[str, Any]]:
    du = state.du
    items: list[dict[str, Any]] = []

    report = du.initial_data_collection_report
    if report:
        cols = report.get("columns") or []
        summary = (
            f"Collected {report.get('train_rows', '?')} train / "
            f"{report.get('test_rows', '?')} test rows, {len(cols)} column(s)."
        )
        items.append(_item(
            "2.1",
            summary=summary,
            highlights=_highlights_from(
                ("Columns", _join_list(cols[:12]) + ("…" if len(cols) > 12 else "")),
            ),
        ))

    report = du.data_description_report
    if report:
        cols = report.get("columns") or []
        missing = report.get("missing") or {}
        miss_parts = [
            f"{c}: {n}" for c, n in list(missing.items())[:6] if n
        ]
        summary = (
            f"{report.get('n_rows', '?')} rows × {report.get('n_cols', '?')} columns profiled."
        )
        items.append(_item(
            "2.2",
            summary=summary,
            highlights=_highlights_from(
                ("Columns", _join_list(cols[:10]) + ("…" if len(cols) > 10 else "")),
                ("Missing values", _join_list(miss_parts) or "none"),
            ),
        ))

    report = du.data_exploration_report
    if report:
        dist = report.get("target_distribution") or {}
        dist_txt = ", ".join(f"{k}={v}" for k, v in list(dist.items())[:6])
        target = report.get("target") or state.config.target_column
        summary = f"Explored training data for target `{target}`."
        if dist_txt:
            summary += f" Distribution: {dist_txt}."
        items.append(_item(
            "2.3",
            summary=summary,
            highlights=_highlights_from(
                ("Rows", _fmt_value(report.get("n_rows"))),
                ("Target missing", _fmt_value(report.get("target_missing"))),
            ),
        ))

    report = du.data_quality_report
    if report:
        blockers = list(report.get("blockers") or [])
        tolerable = list(report.get("tolerable") or [])
        if blockers:
            summary = f"{len(blockers)} quality blocker(s) identified."
        elif tolerable:
            summary = f"No blockers; {len(tolerable)} tolerable issue(s) noted."
        else:
            summary = "Data quality verified with no issues reported."
        items.append(_item(
            "2.4",
            summary=summary,
            highlights=_highlights_from(
                ("Blockers", _join_list(blockers) or "none"),
                ("Tolerable", _join_list(tolerable) or "none"),
            ),
        ))

    return items


def _dp_phase(state: CrispDMState) -> list[dict[str, Any]]:
    dp = state.dp
    items: list[dict[str, Any]] = []

    rationale = dp.rationale_for_inclusion_exclusion
    if rationale:
        included = rationale.get("included") or rationale.get("features_included") or []
        excluded = rationale.get("excluded") or rationale.get("features_excluded") or []
        summary = "Inclusion/exclusion rationale recorded."
        if included or excluded:
            summary = (
                f"{len(included)} included, {len(excluded)} excluded feature group(s)."
            )
        items.append(_item(
            "3.1",
            summary=summary,
            highlights=_highlights_from(
                ("Included", _join_list(included) or _fmt_value(rationale.get("summary"))),
                ("Excluded", _join_list(excluded)),
            ),
        ))

    report = dp.data_cleaning_report
    if report:
        ops = report.get("operations") or []
        paths = _extract_paths(report, ("train_out", "test_out"))
        summary = report.get("source") or report.get("strategy") or "Data cleaning completed."
        if isinstance(summary, dict):
            summary = _fmt_value(summary)
        if ops:
            summary = f"Cleaning applied ({len(ops)} operation(s))."
        items.append(_item(
            "3.2",
            summary=str(summary),
            highlights=_highlights_from(
                ("Operations", _join_list(ops[:8]) or "see report"),
                ("Missing before", _fmt_value(report.get("missing_before"))),
                ("Missing after", _fmt_value(report.get("missing_after_train", report.get("missing_after")))),
            ),
            artifact_paths=paths or None,
        ))

    if dp.derived_attributes or dp.generated_records:
        derived = dp.derived_attributes or {}
        items_list = derived.get("items") if isinstance(derived, dict) else derived
        names = []
        if isinstance(items_list, list):
            for entry in items_list:
                if isinstance(entry, dict):
                    names.append(str(entry.get("field") or entry.get("name") or entry))
                else:
                    names.append(str(entry))
        elif isinstance(derived, dict):
            names = [str(k) for k in derived if k not in ("items",)]
        gen = dp.generated_records or {}
        summary = f"{len(names)} derived attribute(s) constructed."
        if gen.get("count"):
            summary += f" {gen['count']} generated record(s)."
        items.append(_item(
            "3.3",
            summary=summary,
            highlights=_highlights_from(("Derived", _join_list(names) or "see report")),
        ))

    if dp.merged_data:
        merged = dp.merged_data
        summary = merged.get("note") or merged.get("summary") or "Data integration completed."
        paths = _extract_paths(merged, ("train_out", "test_out"))
        items.append(_item(
            "3.4",
            summary=str(summary),
            highlights=_highlights_from(
                ("Train rows", _fmt_value(merged.get("train_rows"))),
                ("Test rows", _fmt_value(merged.get("test_rows"))),
            ),
            artifact_paths=paths or None,
        ))

    if dp.dataset or dp.reformatted_data or dp.dataset_description:
        paths = dict(dp.dataset) if dp.dataset else {}
        reformatted = dp.reformatted_data or {}
        if reformatted.get("degraded"):
            summary = f"Formatted dataset (degraded: {reformatted.get('reason', 'fallback')})."
        elif dp.dataset_description:
            summary = dp.dataset_description
        else:
            summary = "Modeling-ready dataset produced."
        items.append(_item(
            "3.5",
            summary=summary,
            artifact_paths=paths or None,
        ))

    return items


def _md_phase(state: CrispDMState) -> list[dict[str, Any]]:
    md = state.md
    items: list[dict[str, Any]] = []

    if md.modeling_technique or md.modeling_assumptions:
        items.append(_item(
            "4.1",
            summary=md.modeling_technique or "Modeling technique selected.",
            highlights=_highlights_from(
                ("Assumptions", _join_list(md.modeling_assumptions)),
            ),
        ))

    if md.test_design:
        items.append(_item(
            "4.2",
            summary="Test design defined.",
            highlights=_highlights_from(
                ("Design", _fmt_value(md.test_design)),
            ),
        ))

    if md.models:
        lines = [
            f"{m.technique}: CV {m.cv_score if m.cv_score is not None else '?'}"
            for m in md.models[-5:]
        ]
        items.append(_item(
            "4.3",
            summary=f"{len(md.models)} model run(s) recorded.",
            highlights=_highlights_from(("Runs", _join_list(lines))),
        ))

    if md.chosen_model:
        cm = md.chosen_model
        items.append(_item(
            "4.4",
            summary=f"Chosen model: {cm.technique}.",
            highlights=_highlights_from(
                ("CV score", _fmt_value(cm.cv_score)),
                ("Assessment", cm.assessment),
            ),
        ))

    return items


def _ev_phase(state: CrispDMState) -> list[dict[str, Any]]:
    ev = state.ev
    items: list[dict[str, Any]] = []

    if ev.assessment_of_dm_results or ev.approved_models:
        assess = ev.assessment_of_dm_results or {}
        meets = assess.get("meets")
        cv = assess.get("cv_score")
        summary = "Results evaluated."
        if cv is not None:
            summary = f"CV {cv:.4f}" + (" meets threshold." if meets else " below threshold.")
        items.append(_item(
            "5.1",
            summary=summary,
            highlights=_highlights_from(
                ("Threshold", _fmt_value(assess.get("threshold"))),
                ("Approved models", str(len(ev.approved_models))),
            ),
        ))

    if ev.review_of_process:
        items.append(_item("5.2", summary=ev.review_of_process))

    if ev.list_of_possible_actions or ev.decision:
        items.append(_item(
            "5.3",
            summary=ev.decision or "Possible actions listed.",
            highlights=_highlights_from(
                ("Actions", _join_list(ev.list_of_possible_actions)),
            ),
        ))

    return items


def _dep_phase(state: CrispDMState) -> list[dict[str, Any]]:
    dep = state.dep
    items: list[dict[str, Any]] = []

    if dep.deployment_plan:
        items.append(_item("6.1", summary=dep.deployment_plan))
    if dep.monitoring_and_maintenance_plan:
        items.append(_item("6.2", summary=dep.monitoring_and_maintenance_plan))
    if dep.final_report_path or dep.final_presentation_path or dep.submission_path:
        paths = {
            k: v for k, v in {
                "report": dep.final_report_path,
                "presentation": dep.final_presentation_path,
                "submission": dep.submission_path,
            }.items() if v
        }
        items.append(_item(
            "6.3",
            summary="Final deliverables produced.",
            artifact_paths=paths or None,
        ))
    if dep.experience_documentation:
        items.append(_item("6.4", summary=dep.experience_documentation))

    return items


def _highlights_from(*pairs: tuple[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for label, value in pairs:
        text = _fmt_value(value)
        if text:
            out.append({"label": label, "value": text})
    return out


def _extract_paths(data: dict[str, Any], keys: tuple[str, ...]) -> dict[str, str]:
    paths: dict[str, str] = {}
    for key in keys:
        val = data.get(key)
        if isinstance(val, str) and val:
            paths[key] = val
    return paths


def _any_filled(*values: Any) -> bool:
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, dict)) and not value:
            continue
        if value:
            return True
    return False


def _fmt_terminology(terms: dict[str, str]) -> str:
    if not terms:
        return ""
    parts = [f"{k}: {v}" for k, v in list(terms.items())[:8]]
    return "; ".join(parts)


def _join_list(items: Any) -> str:
    if not items:
        return ""
    if isinstance(items, list):
        return ", ".join(str(x) for x in items[:12])
    return str(items)


def _fmt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return _join_list(value)
    if isinstance(value, dict):
        if not value:
            return ""
        parts = [f"{k}: {v}" for k, v in list(value.items())[:8]]
        return "; ".join(parts)
    return str(value)
