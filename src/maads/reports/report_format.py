"""Human-readable formatting for markdown reports (non-technical audience)."""
from __future__ import annotations

from typing import Any

_ASSESSMENT_LABELS: dict[str, str] = {
    "metric": "Metric",
    "achieved_score": "Achieved score",
    "cv_score": "Cross-validation score",
    "threshold": "Threshold",
    "direction": "Optimize direction",
    "success_criterion_met": "Success criterion met",
    "meets": "Success criterion met",
    "meets_success_criterion": "Success criterion met",
    "failure_modes": "Failure modes",
    "caveats": "Caveats",
}


def class_label(key: str, class_labels: dict[str, str] | None = None) -> str:
    if class_labels and str(key) in class_labels:
        return class_labels[str(key)]
    return str(key)


def format_distribution(
    distribution: dict[Any, Any] | list[Any],
    *,
    class_labels: dict[str, str] | None = None,
) -> str:
    """Format class counts as a readable markdown table."""
    if isinstance(distribution, dict):
        rows = [(str(k), v) for k, v in distribution.items()]
    elif isinstance(distribution, list):
        rows = [(str(i), v) for i, v in enumerate(distribution)]
    else:
        return format_report_value(distribution)

    numeric = [float(v) for _, v in rows if isinstance(v, (int, float))]
    total = sum(numeric) if numeric else 0.0
    lines = ["| Class | Count | Share |", "| --- | ---: | ---: |"]
    for key, count in rows:
        label = class_label(key, class_labels)
        if isinstance(count, (int, float)) and total:
            share = 100.0 * float(count) / total
            lines.append(f"| {label} | {int(count):,} | {share:.1f}% |")
        else:
            lines.append(f"| {label} | {format_report_value(count)} | — |")
    return "\n".join(lines)


def format_confusion_matrix(
    matrix: list[list[int]],
    *,
    class_labels: dict[str, str] | None = None,
) -> str:
    """Format a confusion matrix as a markdown table with readable class names."""
    if not matrix:
        return "_No confusion matrix available._"
    n = len(matrix[0]) if matrix else 0
    row_labels = [class_label(str(i), class_labels) for i in range(len(matrix))]
    col_labels = [class_label(str(i), class_labels) for i in range(n)]
    header = ["Actual \\ Predicted", *col_labels]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * len(header)) + " |",
    ]
    for label, row in zip(row_labels, matrix):
        cells = [str(int(v)) if isinstance(v, (int, float)) else format_report_value(v) for v in row]
        lines.append("| " + " | ".join([label, *cells]) + " |")
    return "\n".join(lines)


def format_token_spend(spend: dict[str, int] | None) -> list[str]:
    """Markdown bullet lines for raw per-agent token spend."""
    if not spend:
        return ["- **Token spend:** none recorded"]
    total = sum(spend.values())
    lines = [f"- **Total tokens:** {total:,}"]
    lines.append("- **By agent:**")
    for agent, tokens in sorted(spend.items(), key=lambda kv: kv[1], reverse=True):
        pct = round(100.0 * tokens / total, 1) if total else 0.0
        lines.append(f"  - {agent}: {tokens:,} ({pct}% of total)")
    return lines


def format_report_value(value: Any) -> str:
    """Format structured values without dumping raw JSON/Python repr."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return f"{value:,}"
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        if not value:
            return "none"
        if all(isinstance(x, str) for x in value):
            return "; ".join(value[:12])
        return "; ".join(format_report_value(x) for x in value[:8])
    if isinstance(value, dict):
        if not value:
            return "none"
        parts = [f"{k}: {format_report_value(v)}" for k, v in list(value.items())[:8]]
        return "; ".join(parts)
    return str(value)


def format_assessment_lines(assessment: dict[str, Any]) -> list[str]:
    """Readable bullet lines for evaluation assessment payloads."""
    lines: list[str] = []
    for key in (
        "metric",
        "achieved_score",
        "cv_score",
        "threshold",
        "direction",
        "success_criterion_met",
        "meets",
        "failure_modes",
        "caveats",
    ):
        val = assessment.get(key)
        if val is None or val == "":
            continue
        label = _ASSESSMENT_LABELS.get(key, key.replace("_", " ").title())
        if key in {"failure_modes", "caveats"} and isinstance(val, list):
            lines.append(f"- **{label}:**")
            for item in val[:12]:
                lines.append(f"  - {format_report_value(item)}")
            if len(val) > 12:
                lines.append(f"  - _…and {len(val) - 12} more_")
        else:
            lines.append(f"- **{label}:** {format_report_value(val)}")
    return lines
