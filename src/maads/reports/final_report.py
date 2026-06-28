"""Deterministic final report renderer (markdown)."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from maads.reports.md_paths import md_file_link, relative_md_path
from maads.reports.report_format import (
    format_confusion_matrix,
    format_distribution,
    format_report_value,
)
from maads.state import CrispDMState
from maads.success_criterion import assessment_meets


def _fmt_metrics(metrics: dict[str, float]) -> str:
    lines = ["| Metric | Value |", "| --- | --- |"]
    for key, val in sorted(metrics.items()):
        if key.startswith("support_"):
            lines.append(f"| {key} | {int(val)} |")
        else:
            lines.append(f"| {key} | {val:.4f} |")
    return "\n".join(lines)


def _figure_section(
    figures: list[str],
    *,
    md_dir: Path | None = None,
    run_dir: Path | None = None,
    remap: Callable[[Path], Path] | None = None,
) -> str:
    if not figures:
        return "_No figures available._\n"
    lines: list[str] = []
    for fig in figures:
        name = Path(fig).stem.replace("_", " ").title()
        lines.append(f"### {name}\n")
        if md_dir is not None and run_dir is not None:
            rel = relative_md_path(fig, md_dir=md_dir, run_dir=run_dir, remap=remap)
            src = rel or fig
        else:
            src = fig
        lines.append(f"![{name}]({src})\n")
    return "\n".join(lines)


def build_story_spec_from_bundle(state: CrispDMState) -> dict[str, Any]:
    """Fallback story spec when LLM output is missing."""
    cm = state.md.chosen_model
    bundle = cm.evaluation_bundle if cm else None
    if not bundle:
        return {
            "detected_problem_type": state.config.problem_type,
            "storytelling_summary": "Evaluation bundle not available.",
            "selected_metrics": [],
            "interpretations": [],
            "methodological_warnings": [],
            "next_steps": [],
        }
    interpretations = []
    for key, val in bundle.metrics.items():
        if key.startswith("support_"):
            continue
        interpretations.append({
            "metric": key,
            "value": val,
            "interpretation": f"{key.replace('_', ' ')} = {val:.4f} on out-of-fold predictions.",
        })
    return {
        "detected_problem_type": bundle.problem_type,
        "selected_model": cm.technique if cm else None,
        "selected_metrics": list(bundle.metrics.keys()),
        "interpretations": interpretations,
        "methodological_warnings": list(bundle.warnings),
        "storytelling_summary": (
            f"Model {cm.technique if cm else '?'} evaluated with "
            f"accuracy {bundle.metrics.get('accuracy', 0):.4f} "
            f"(CV mean {bundle.cv.get('mean', 0):.4f} ± {bundle.cv.get('std', 0):.4f})."
            if bundle.cv
            else f"Model evaluated with out-of-fold metrics."
        ),
        "next_steps": [
            "Review per-class recall if the positive class is business-critical.",
            "Consider feature engineering if metrics are below the success threshold.",
        ],
    }


def render_final_report_md(
    state: CrispDMState,
    story_spec: dict[str, Any],
    *,
    artifact_dir: Path | None = None,
    md_dir: Path | None = None,
    run_dir: Path | None = None,
    remap: Callable[[Path], Path] | None = None,
) -> str:
    """Render the full markdown report from state + story spec."""
    md_dir = md_dir or artifact_dir
    run_dir = run_dir or artifact_dir
    cm = state.md.chosen_model
    bundle = cm.evaluation_bundle if cm else None
    assessment = state.ev.assessment_of_dm_results or {}
    lines = [
        f"# Final Report — {state.case_id}",
        "",
        "## Executive Summary",
        "",
        story_spec.get("storytelling_summary", "No summary available."),
        "",
    ]
    if assessment:
        meets = assessment_meets(assessment)
        score = assessment.get("achieved_score", assessment.get("cv_score", "n/a"))
        lines.extend([
            f"- **Success criterion met:** {'yes' if meets else 'no'}",
            f"- **CV score:** {format_report_value(score) or 'n/a'}",
            f"- **Threshold:** {format_report_value(assessment.get('threshold')) or 'n/a'}",
            "",
        ])

    lines.extend([
        "## Problem and Data",
        "",
        state.config.problem_statement.strip(),
        "",
    ])
    if state.bu.data_mining_goals:
        lines.extend([f"**Data mining goals:** {state.bu.data_mining_goals}", ""])

    explore = state.du.data_exploration_report or {}
    if explore.get("target_distribution"):
        class_labels = dict(state.config.class_labels)
        if bundle and bundle.class_labels:
            class_labels.update(bundle.class_labels)
        lines.extend([
            "**Target distribution:**",
            "",
            format_distribution(
                explore["target_distribution"],
                class_labels=class_labels or None,
            ),
            "",
        ])

    lines.extend([
        "## Methodology",
        "",
        f"- **Technique:** {cm.technique if cm else 'n/a'}",
        f"- **Test design:** {state.md.test_design or 'n/a'}",
    ])
    if cm and cm.cv_score is not None:
        std = f" ± {cm.cv_std:.4f}" if cm.cv_std is not None else ""
        lines.append(f"- **CV score:** {cm.cv_score:.4f}{std}")
    if state.loop_history:
        loops = ", ".join(le.label for le in state.loop_history)
        lines.append(f"- **Loops fired:** {loops}")
    lines.append("")

    lines.extend(["## Results", ""])
    if bundle and bundle.metrics:
        lines.extend([_fmt_metrics(bundle.metrics), ""])
    if bundle and bundle.confusion_matrix:
        lines.extend([
            "**Confusion matrix (out-of-fold):**",
            "",
            format_confusion_matrix(
                bundle.confusion_matrix,
                class_labels=bundle.class_labels or dict(state.config.class_labels),
            ),
            "",
        ])
    lines.extend([
        "## Visualizations",
        "",
        _figure_section(
            bundle.figures if bundle else [],
            md_dir=md_dir,
            run_dir=run_dir,
            remap=remap,
        ),
    ])

    interpretations = story_spec.get("interpretations") or []
    if interpretations:
        lines.extend(["## Interpretation", ""])
        for item in interpretations:
            metric = item.get("metric", "?")
            text = item.get("interpretation", "")
            lines.append(f"- **{metric}:** {text}")
        lines.append("")

    warnings = story_spec.get("methodological_warnings") or []
    if bundle and bundle.warnings:
        warnings = list(dict.fromkeys([*warnings, *bundle.warnings]))
    if state.degraded_flags:
        warnings = list(dict.fromkeys([*warnings, *[f"degraded: {f}" for f in state.degraded_flags]]))
    lines.extend(["## Limitations and Warnings", ""])
    if warnings:
        for w in warnings:
            lines.append(f"- {w}")
    else:
        lines.append("- No major methodological warnings detected from available information.")
    lines.append("")

    next_steps = story_spec.get("next_steps") or []
    lines.extend(["## Recommendations", ""])
    if next_steps:
        for step in next_steps:
            lines.append(f"- {step}")
    else:
        lines.append("- Monitor model performance on new data.")
    lines.append("")

    lines.extend(["## Appendix", ""])
    if state.dep.submission_path:
        if md_dir is not None and run_dir is not None:
            link = md_file_link(
                state.dep.submission_path,
                md_dir=md_dir,
                run_dir=run_dir,
                remap=remap,
            )
            lines.append(f"- **Submission:** {link or state.dep.submission_path}")
        else:
            lines.append(f"- **Submission:** `{state.dep.submission_path}`")
    if artifact_dir and md_dir is not None and run_dir is not None:
        link = md_file_link(
            artifact_dir,
            md_dir=md_dir,
            run_dir=run_dir,
            label="run directory",
            remap=remap,
        )
        lines.append(f"- **Artifacts:** {link or '.'}")
    elif artifact_dir:
        lines.append(f"- **Artifacts:** `{artifact_dir}`")
    if cm:
        lines.append(f"- **Assessment:** {cm.assessment or 'n/a'}")
    lines.append("")

    return "\n".join(lines)


def write_final_report(
    state: CrispDMState,
    story_spec: dict[str, Any],
    artifact_dir: Path,
) -> Path:
    """Write final_report.md to artifact_dir and return its path."""
    content = render_final_report_md(state, story_spec, artifact_dir=artifact_dir)
    path = artifact_dir / "final_report.md"
    path.write_text(content, encoding="utf-8")
    return path
