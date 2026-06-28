"""Tests for human-readable report formatting."""
from __future__ import annotations

from maads.reports.report_format import (
    format_assessment_lines,
    format_confusion_matrix,
    format_distribution,
    format_report_value,
    format_token_spend,
)
from maads.reports.final_report import render_final_report_md
from maads.reports.final_report import build_story_spec_from_bundle
from maads.config import load_case_config
from maads.paths import resolve_path
from maads.state import CrispDMState, EvaluationBundle, ModelRun


def test_format_distribution_with_labels():
    md = format_distribution(
        {"0": 549, "1": 342},
        class_labels={"0": "Not survived", "1": "Survived"},
    )
    assert "Not survived" in md
    assert "549" in md
    assert "61.6%" in md
    assert "{" not in md


def test_format_confusion_matrix_with_labels():
    md = format_confusion_matrix(
        [[10, 2], [3, 5]],
        class_labels={"0": "Not survived", "1": "Survived"},
    )
    assert "Actual \\ Predicted" in md
    assert "Not survived" in md
    assert "| 10 |" in md or "| 10 | 2 |" in md
    assert "[[" not in md


def test_format_report_value_avoids_json_repr():
    assert "{" not in format_report_value({"a": 1, "b": 2})
    assert format_report_value(True) == "yes"
    assert format_report_value([1, 2, 3]) == "1; 2; 3"


def test_format_token_spend():
    lines = format_token_spend({"data_scientist": 1000, "developer": 500})
    text = "\n".join(lines)
    assert "1,500" in text
    assert "data_scientist" in text
    assert "{" not in text


def test_format_assessment_lines():
    lines = format_assessment_lines({
        "metric": "accuracy",
        "achieved_score": 0.82,
        "threshold": 0.77,
        "success_criterion_met": True,
        "failure_modes": ["class imbalance"],
        "caveats": ["small validation set"],
    })
    text = "\n".join(lines)
    assert "Achieved score" in text
    assert "class imbalance" in text
    assert "{" not in text


def test_final_report_uses_readable_tables():
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    state = CrispDMState.from_config(cfg)
    bundle = EvaluationBundle(
        problem_type="binary_classification",
        metrics={"accuracy": 0.82},
        confusion_matrix=[[10, 2], [3, 5]],
        class_labels=dict(cfg.class_labels),
        cv={"mean": 0.80, "std": 0.02, "n_folds": 5},
        figures=[],
        warnings=[],
    )
    state.md.chosen_model = ModelRun(technique="gb", cv_score=0.80, evaluation_bundle=bundle)
    state.du.data_exploration_report = {
        "target_distribution": {"0": 549, "1": 342},
        "target": "Survived",
    }
    md = render_final_report_md(state, build_story_spec_from_bundle(state))
    assert "{'0':" not in md
    assert "[[10, 2], [3, 5]]" not in md
    assert "Not survived" in md
    assert "Actual \\ Predicted" in md
