"""Domain Knowledge Expert — task formatting (persona in backstories/domain.md)."""
from __future__ import annotations

import json
from typing import Any

from maads.prompts.loader import load_agent_prompts
from maads.rag import retrieve_for_state
from maads.state import CrispDMState

DOMAIN_UNDERSTANDING_TASK = """For the dataset "{dataset_name}" with prediction target "{target}",
evaluation metric "{metric}", and ML task type "{ml_task}", produce the domain
foundation for the CRISP-DM run.

You own:
  - 1.1 Determine Business Objectives
  - 1.2 Assess Situation
  - 1.3 Determine Data Mining Goals

You contribute to:
  - 2.2 Describe Data
  - 2.3 Explore Data

Work ONLY from these inputs:
  - Feature schema & statistics: {feature_schema}
  - Retrieved domain notes / data dictionary: {domain_corpus}

Do all of the following:
  1. State the business objective in one or two plain sentences.
  2. Translate the business objective into a concrete data-mining goal.
  3. Define a measurable success criterion tied to "{metric}". If no target
     threshold is provided, set target_value to null and explain the direction.
  4. Assess the situation: identify useful resources, constraints, assumptions,
     terminology, risks, and expected benefits where supported by the inputs.
  5. Give a short domain gloss for each non-trivial feature: what it means in
     the real world and why it may matter. Do not over-explain purely technical
     ID columns unless they carry domain meaning or leakage risk.
  6. Propose feature_hints: features likely to carry signal, each with a
     one-line domain rationale and expected effect. For classification,
     positive means higher likelihood of the positive/target class. For
     regression, positive means higher expected target value.
  7. Flag real-world data-quality risks predicted by domain knowledge, including
     missing-not-at-random fields, target leakage, proxy variables, encoding
     quirks, unstable definitions, or train/test mismatch risks.
  8. Decide whether Loop A should be recommended. Trigger Loop A if the schema,
     target, metric, or domain notes contradict the stated business or
     data-mining goal.

Rules:
  - Ground every confirmed domain claim in either the domain corpus or
    the feature schema.
  - Anything not directly supported must go under "assumptions" or
    "open_questions".
  - Do not hardcode anything specific to one dataset beyond the provided inputs.
  - Do not invent columns, files, thresholds, metrics, target meanings, or
    business context.
  - Do not write code.
  - Do not recommend a final model.
  - Output strict JSON only: no prose, no markdown, no comments."""

DOMAIN_UNDERSTANDING_SCHEMA_HINT = """{
  "business_objectives": "string",
  "situation_assessment": {
    "resources": ["string"],
    "requirements": ["string"],
    "assumptions": ["string"],
    "constraints": ["string"],
    "risks": ["string"],
    "terminology": [{"term": "string", "meaning": "string"}],
    "costs_or_tradeoffs": ["string"],
    "expected_benefits": ["string"]
  },
  "data_mining_goal": "string",
  "success_criterion": {
    "metric": "string",
    "target_value": "string|null",
    "direction": "maximize|minimize"
  },
  "data_description_notes": [
    {"feature": "string", "meaning": "string"}
  ],
  "feature_hints": [
    {
      "feature": "string",
      "rationale": "string",
      "expected_effect": "positive|negative|nonlinear|unknown"
    }
  ],
  "domain_data_quality_flags": [
    {"feature": "string", "risk": "string"}
  ],
  "loop_a_recommendation": {
    "should_trigger": true,
    "reason": "string"
  },
  "assumptions": ["string"],
  "open_questions": ["string"]
}"""


def domain_identity(dataset_name: str) -> dict[str, str]:
    """Return role/goal/backstory for a specific dataset."""
    base = load_agent_prompts()["domain"]
    return {
        "role": base["role"].format(dataset_name=dataset_name),
        "goal": base["goal"].format(dataset_name=dataset_name),
        "backstory": base["backstory"],
    }


def _feature_schema(state: CrispDMState) -> dict[str, Any]:
    """Config-only schema hints; DU reports live in the scaffold state_view."""
    cfg = state.config
    return {
        "target_column": cfg.target_column,
        "id_column": cfg.id_column,
        "problem_type": cfg.problem_type,
        "evaluation_metric": cfg.evaluation_metric,
        "config_feature_hints": cfg.feature_hints,
    }


def _domain_corpus(state: CrispDMState, passages: list[str]) -> dict[str, Any]:
    cfg = state.config
    return {
        "problem_statement": cfg.problem_statement,
        "kaggle_competition": cfg.kaggle_competition,
        "success_criterion": cfg.success_criterion.model_dump(),
        "config_feature_hints": cfg.feature_hints,
        "retrieved_passages": passages,
    }


def _rag_block(passages: list[str]) -> str:
    if not passages:
        return "(no passages retrieved)"
    return "\n".join(f"- {p}" for p in passages)


def format_domain_understanding_task(state: CrispDMState) -> tuple[str, str]:
    """Build the domain-understanding instruction and JSON schema hint."""
    cfg = state.config
    passages = retrieve_for_state(state)
    instruction = DOMAIN_UNDERSTANDING_TASK.format(
        dataset_name=cfg.case_id,
        target=cfg.target_column,
        metric=cfg.evaluation_metric,
        ml_task=cfg.problem_type,
        feature_schema=json.dumps(_feature_schema(state), indent=2, default=str),
        domain_corpus=json.dumps(_domain_corpus(state, passages), indent=2, default=str),
    )
    return instruction, DOMAIN_UNDERSTANDING_SCHEMA_HINT


DOMAIN_SITUATION_TASK = """CRISP-DM 1.2 Assess Situation for "{dataset_name}".

Expand the situation assessment: resources, requirements, assumptions, constraints,
risks, terminology, costs/tradeoffs, and expected benefits. Ground claims in the
relevant state view and retrieved domain passages below.

Retrieved domain passages:
{retrieved_passages}

Output strict JSON with key "situation_assessment" matching the schema
from the domain understanding task."""

DOMAIN_REFINE_GOALS_TASK = """CRISP-DM 1.3 Determine Data Mining Goals for "{dataset_name}".

Given the data quality report and current business understanding in the state view,
refine data_mining_goals and success criteria if warranted. If quality blockers
contradict the current goals, recommend Loop A.

Retrieved domain passages:
{retrieved_passages}

Output JSON with keys: data_mining_goal,
success_criterion (metric, target_value, direction), loop_a_recommendation."""


def format_domain_situation_task(state: CrispDMState) -> tuple[str, str]:
    cfg = state.config
    passages = retrieve_for_state(state)
    instruction = DOMAIN_SITUATION_TASK.format(
        dataset_name=cfg.case_id,
        retrieved_passages=_rag_block(passages),
    )
    return instruction, DOMAIN_UNDERSTANDING_SCHEMA_HINT


def format_domain_refine_goals_task(state: CrispDMState) -> tuple[str, str]:
    cfg = state.config
    passages = retrieve_for_state(state)
    instruction = DOMAIN_REFINE_GOALS_TASK.format(
        dataset_name=cfg.case_id,
        retrieved_passages=_rag_block(passages),
    )
    hint = """{"data_mining_goal": "string", "success_criterion": {"metric": "string",
    "target_value": "string|null", "direction": "maximize|minimize"},
    "loop_a_recommendation": {"should_trigger": true, "reason": "string"}}"""
    return instruction, hint
