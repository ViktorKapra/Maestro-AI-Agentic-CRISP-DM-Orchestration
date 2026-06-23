"""Minimal LLM stubs for fast mocked orchestrator runs."""
from __future__ import annotations

from typing import Any

from maads.state import CrispDMState

_DOMAIN_1_1: dict[str, Any] = {
    "business_objectives": "Predict survival accurately.",
    "situation_assessment": {
        "resources": ["tabular train/test CSV"],
        "requirements": ["Kaggle submission"],
        "assumptions": ["no leakage"],
        "constraints": ["time budget"],
        "risks": ["overfitting"],
        "terminology": [{"term": "Survived", "meaning": "1 if passenger lived"}],
        "costs_or_tradeoffs": [],
        "expected_benefits": ["baseline benchmark"],
    },
    "data_mining_goal": "Binary classification for Survived.",
    "success_criterion": {
        "metric": "accuracy",
        "target_value": "0.77",
        "direction": "maximize",
    },
    "data_description_notes": [],
    "feature_hints": ["Pclass", "Sex", "Age"],
    "domain_data_quality_flags": [],
    "loop_a_recommendation": {"should_trigger": False, "reason": ""},
    "assumptions": [],
    "open_questions": [],
}

_DE_STATE_UPDATES: dict[str, dict[str, Any]] = {
    "2.4": {
        "du": {
            "data_quality_report": {
                "blockers": [],
                "tolerable": ["missing values imputed in prep"],
            },
        },
    },
    "3.1": {
        "dp": {
            "rationale_for_inclusion_exclusion": {
                "included": ["numeric", "categorical"],
                "excluded": [],
            },
        },
    },
    "3.2": {
        "dp": {
            "data_cleaning_report": {"strategy": "impute and encode"},
        },
    },
    "3.3": {
        "dp": {
            "derived_attributes": {"FamilySize": "SibSp + Parch + 1"},
        },
    },
    "3.4": {
        "dp": {
            "merged_data": {"note": "single table"},
        },
    },
}

_DS_STATE_UPDATES: dict[str, dict[str, Any]] = {
    "4.1": {
        "md": {
            "modeling_technique": "gradient_boosting",
            "modeling_assumptions": ["tabular features"],
        },
    },
    "4.2": {
        "md": {
            "test_design": {"cv": "stratified_5fold", "metric": "accuracy"},
        },
    },
    "4.4": {
        "md": {
            "chosen_model_technique": "gradient_boosting",
            "assessment": "best CV score",
        },
    },
    "5.1": {
        "ev": {
            "assessment_of_dm_results": {
                "cv_score": 0.82,
                "threshold": 0.77,
                "meets": True,
            },
        },
    },
}


def fake_llm_response(
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    schema_hint: str = "",
) -> dict[str, Any]:
    """Return minimal JSON payloads so every agent ``act()`` path succeeds."""
    if agent_name == "pm":
        return {"action": "advance", "target_substep": None, "reason": "ok"}

    substep = state.substep

    if agent_name == "domain" and substep == "1.1":
        return dict(_DOMAIN_1_1)

    if agent_name == "data_engineer" and substep in _DE_STATE_UPDATES:
        return {"state_updates": _DE_STATE_UPDATES[substep], "summary": f"DE {substep}"}

    if agent_name == "data_scientist" and substep in _DS_STATE_UPDATES:
        return {"state_updates": _DS_STATE_UPDATES[substep], "summary": f"DS {substep}"}

    return {}
