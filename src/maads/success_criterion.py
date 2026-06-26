"""Canonical success-criterion evaluation (minimize vs maximize, field aliasing)."""
from __future__ import annotations

from typing import Any, Literal

Direction = Literal["minimize", "maximize"]

_MINIMIZE_TOKENS = ("rmse", "mae", "mse", "loss", "error")


def criterion_direction(metric: str, explicit: str | None = None) -> Direction:
    """Return optimize direction for a metric name or explicit override."""
    if explicit in ("minimize", "maximize"):
        return explicit
    m = (metric or "").lower()
    if any(tok in m for tok in _MINIMIZE_TOKENS):
        return "minimize"
    return "maximize"


def score_meets_threshold(
    score: float,
    threshold: float,
    *,
    direction: Direction,
) -> bool:
    """True when score satisfies the success threshold for the given direction."""
    if direction == "minimize":
        return score <= threshold
    return score >= threshold


def assessment_meets(assessment: dict[str, Any] | None) -> bool:
    """Single read path for whether assessment indicates success."""
    if not assessment:
        return False
    if assessment.get("meets") is not None:
        return bool(assessment["meets"])
    if assessment.get("success_criterion_met") is not None:
        return bool(assessment["success_criterion_met"])
    return False


def normalize_assessment(
    assessment: dict[str, Any] | None,
    *,
    metric: str,
    threshold: float,
    direction: str | None = None,
    cv_score: float | None = None,
) -> dict[str, Any]:
    """Canonical dict for ``ev.assessment_of_dm_results``."""
    out: dict[str, Any] = dict(assessment or {})
    dir_ = criterion_direction(
        out.get("metric") or metric,
        out.get("direction") or direction,
    )
    thr = float(out.get("threshold", threshold))
    score_raw = out.get("achieved_score", out.get("cv_score", cv_score))
    score = float(score_raw) if score_raw is not None else None

    out.setdefault("metric", metric)
    out.setdefault("threshold", thr)
    out["direction"] = dir_

    if score is not None:
        meets = score_meets_threshold(score, thr, direction=dir_)
        out["meets"] = meets
        out["success_criterion_met"] = meets
        out.setdefault("cv_score", score)
        out.setdefault("achieved_score", score)
    elif "meets" not in out and "success_criterion_met" in out:
        out["meets"] = bool(out["success_criterion_met"])
        out.setdefault("success_criterion_met", out["meets"])

    return out


def assessment_summary_phrase(
    assessment: dict[str, Any] | None,
    *,
    cv_score: float | None = None,
) -> str:
    """Direction-aware one-line summary for conclusions."""
    if not assessment and cv_score is None:
        return "Results evaluated."
    meets = assessment_meets(assessment)
    score = None
    if assessment:
        raw = assessment.get("cv_score", assessment.get("achieved_score"))
        score = float(raw) if raw is not None else None
    if score is None and cv_score is not None:
        score = cv_score
    if score is None:
        return "Results evaluated."
    if meets:
        return f"CV {score:.4f} meets threshold."
    dir_ = criterion_direction(
        (assessment or {}).get("metric", ""),
        (assessment or {}).get("direction"),
    )
    if dir_ == "minimize":
        return f"CV {score:.4f} above threshold."
    return f"CV {score:.4f} below threshold."
