"""Tests for canonical success-criterion evaluation."""
from __future__ import annotations

from maads.success_criterion import (
    assessment_meets,
    assessment_summary_phrase,
    criterion_direction,
    normalize_assessment,
    score_meets_threshold,
)


def test_rmse_log_minimize_meets_when_below_threshold():
    assert criterion_direction("rmse_log") == "minimize"
    assert score_meets_threshold(0.1355, 0.15, direction="minimize") is True
    assert score_meets_threshold(0.16, 0.15, direction="minimize") is False


def test_accuracy_maximize_meets_when_above_threshold():
    assert criterion_direction("accuracy") == "maximize"
    assert score_meets_threshold(0.82, 0.77, direction="maximize") is True
    assert score_meets_threshold(0.70, 0.77, direction="maximize") is False


def test_normalize_assessment_maps_success_criterion_met_alias():
    out = normalize_assessment(
        {"success_criterion_met": True, "achieved_score": 0.1355},
        metric="rmse_log",
        threshold=0.15,
        direction="minimize",
    )
    assert out["meets"] is True
    assert out["success_criterion_met"] is True


def test_normalize_assessment_recomputes_meets_from_score():
    out = normalize_assessment(
        {"meets": False, "success_criterion_met": False},
        metric="rmse_log",
        threshold=0.15,
        direction="minimize",
        cv_score=0.1355,
    )
    assert out["meets"] is True
    assert out["success_criterion_met"] is True
    assert out["cv_score"] == 0.1355


def test_assessment_meets_reads_either_field():
    assert assessment_meets({"meets": True}) is True
    assert assessment_meets({"success_criterion_met": True}) is True
    assert assessment_meets({"meets": False, "success_criterion_met": True}) is False
    assert assessment_meets(None) is False


def test_assessment_summary_phrase_direction_aware():
    assert assessment_summary_phrase(
        {"metric": "rmse_log", "direction": "minimize", "meets": True},
        cv_score=0.1355,
    ) == "CV 0.1355 meets threshold."
    assert "above threshold" in assessment_summary_phrase(
        {"metric": "rmse_log", "direction": "minimize", "meets": False},
        cv_score=0.16,
    )
    assert "below threshold" in assessment_summary_phrase(
        {"metric": "accuracy", "direction": "maximize", "meets": False},
        cv_score=0.70,
    )
