"""Domain Knowledge Expert — task formatting; persona lives in config/agents.yaml."""
from __future__ import annotations

import json
from typing import Any

from maads.prompts.loader import load_agent_prompts
from maads.state import CrispDMState

# Persona (role/goal carry the literal {dataset_name} placeholder, rendered per dataset).
_DOMAIN = load_agent_prompts()["domain"]
DOMAIN_ROLE_TEMPLATE = _DOMAIN["role"]
DOMAIN_GOAL = _DOMAIN["goal"]
DOMAIN_BACKSTORY = _DOMAIN["backstory"]

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
    return {
        "role": DOMAIN_ROLE_TEMPLATE.format(dataset_name=dataset_name),
        "goal": DOMAIN_GOAL.format(dataset_name=dataset_name),
        "backstory": DOMAIN_BACKSTORY,
    }


def _feature_schema(state: CrispDMState) -> dict[str, Any]:
    cfg = state.config
    schema: dict[str, Any] = {
        "target_column": cfg.target_column,
        "id_column": cfg.id_column,
        "problem_type": cfg.problem_type,
        "evaluation_metric": cfg.evaluation_metric,
        "config_feature_hints": cfg.feature_hints,
    }
    desc = state.du.data_description_report
    if desc:
        schema["data_description_report"] = desc
    explore = state.du.data_exploration_report
    if explore:
        schema["data_exploration_report"] = explore
    quality = state.du.data_quality_report
    if quality:
        schema["data_quality_report"] = quality
    return schema


def _domain_corpus(state: CrispDMState) -> dict[str, Any]:
    cfg = state.config
    return {
        "problem_statement": cfg.problem_statement,
        "kaggle_competition": cfg.kaggle_competition,
        "success_criterion": cfg.success_criterion.model_dump(),
        "config_feature_hints": cfg.feature_hints,
    }


def format_domain_understanding_task(state: CrispDMState) -> tuple[str, str]:
    """Build the domain-understanding instruction and JSON schema hint."""
    cfg = state.config
    instruction = DOMAIN_UNDERSTANDING_TASK.format(
        dataset_name=cfg.case_id,
        target=cfg.target_column,
        metric=cfg.evaluation_metric,
        ml_task=cfg.problem_type,
        feature_schema=json.dumps(_feature_schema(state), indent=2, default=str),
        domain_corpus=json.dumps(_domain_corpus(state), indent=2, default=str),
    )
    return instruction, DOMAIN_UNDERSTANDING_SCHEMA_HINT
