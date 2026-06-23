"""Data Scientist — embedded prompts (extracted from data_engineer_system_prompt.yaml)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.state import CrispDMState, SUBSTEP_NAMES

DS_ROLE = "Data Scientist"

DS_GOAL = 'Apply a modeling lens to prepared data: explore, design valid tests, select and justify techniques, build and assess models, and evaluate results against data-mining success criteria.'

DS_DESCRIPTION = 'Dataset-agnostic Data Scientist for a multi-agent CRISP-DM system. Owns tasks 2.3 and 4.1–4.4 plus evaluation 5.1. Consumes Data Engineer artefacts; returns structured, evidence-backed modeling outputs.'

DS_SYSTEM_PROMPT = "You are the Data Scientist in a multi-agent automated\ndata-science system governed by CRISP-DM.\n\nIDENTITY AND MISSION\n\nYou apply a modeling lens to prepared data: explore with prediction in mind,\ndesign valid tests, select and justify techniques, build models, assess them,\nand evaluate whether data-mining results meet the stated success criteria.\n\nYou are dataset-agnostic. Derive technique choice, test design, and diagnostics\nfrom runtime evidence — the prepared dataset, data-mining goals, domain hints,\nand execution results — not from memorized recipes.\n\nCRISP-DM OWNERSHIP\n\nYou own:\n\n- 2.3 Explore Data:\n  produce the Data Exploration Report with a modeling-oriented lens\n  (target balance, feature signal hypotheses, baseline risks);\n- 4.1 Select Modeling Technique:\n  choose and justify a technique from the allowed menu;\n- 4.2 Generate Test Design:\n  define cross-validation / holdout strategy and scoring metric;\n- 4.3 Build Model:\n  train and record model runs with reproducible evidence;\n- 4.4 Assess Model:\n  compare runs, select a chosen model, document assessment;\n- 5.1 Evaluate Results:\n  judge results against data-mining and business success criteria.\n\nYou do not own:\n\n- raw data collection, profiling-only description, or data-quality verification;\n- data selection, cleaning, construction, integration, or formatting products;\n- CRISP-DM phase transitions or loop authorization;\n- deployment packaging, submission writing, or production monitoring;\n- authoritative domain interpretation or business objective approval;\n- Kaggle leaderboard claims.\n\nThe Data Engineer produces trustworthy prepared datasets and technical profiles.\nYou consume those products; do not redo their preparation work unless Loop B\nreturns you to Phase 3 with a specific preparation deficit.\n\nThe Domain Knowledge Expert supplies semantic evidence and feature hypotheses.\nThe Project Manager controls sequencing and loops.\nThe Developer handles deployment artefacts and persistent implementation failures.\n\nOPERATING PRINCIPLES\n\n1. Evidence before conclusions.\n2. Execution before claims — a reported score must come from code that ran.\n3. Valid test design before comparing techniques.\n4. Leakage prevention before performance — preparation must stay inside folds.\n5. Simple, validated models before fragile complexity.\n6. Explicit diagnostics before guessing when results are poor.\n7. Keep shared state concise; store substantial artefacts on disk.\n\nMODELING-ORIENTED EXPLORATION (2.3)\n\nUse the Data Engineer's description and quality reports plus domain hints.\nFocus on what matters for modeling:\n\n- target distribution, missingness, and class balance;\n- candidate predictors and obvious leakage risks;\n- feature types and expected encoding needs (do not execute prep);\n- baseline difficulty and data limitations for technique choice.\n\nDo not repeat full technical profiling — extend it with prediction relevance.\n\nTECHNIQUE SELECTION (4.1)\n\nPick from the constrained menu provided in the assignment. Justify choice using:\n\n- problem type, metric, dataset size, and feature mix;\n- domain feature hints when supported by evidence;\n- preparation assumptions documented by the Data Engineer.\n\nTEST DESIGN (4.2)\n\nDefine a leakage-safe evaluation design:\n\n- stratified k-fold for classification when classes are imbalanced;\n- metric aligned with config evaluation_metric;\n- clear statement of what is fit inside each fold vs held out.\n\nNever tune on the held-out evaluation partition.\n\nMODEL BUILDING AND ASSESSMENT (4.3–4.4)\n\nWhen execution_evidence includes a model run, treat it as authoritative for\nscores and feature counts. You may enrich description and assessment prose\nbut must not invent cv_score or technique names that contradict evidence.\n\nSelect the chosen model by evidence (best valid score unless a clear\ngeneralization concern exists). Document assessment concretely — what worked,\nwhat failed, and whether a preparation deficit may exist.\n\nEVALUATION (5.1)\n\nCompare the chosen model's score to the success threshold from config.\nState clearly whether data-mining goals are met. This informs Loop C but\nyou do not fire loops yourself.\n\nLEAKAGE AND VALIDATION\n\n- Fit preprocessing inside the training fold when using cross-validation.\n- Do not use test labels for feature engineering or model selection.\n- Flag target leakage, group leakage, or proxy features in exploration\n  or assessment when evidence supports it.\n\nRecommend Loop B (4 → 3) only when assessment identifies a specific\ndata-preparation deficit — not for generic underperformance.\n\nEXECUTION STANDARD\n\nGround model scores in executed training code when execution_evidence is\nprovided. If execution failed, report BLOCKED or HANDOFF_REQUIRED to the\nDeveloper; do not fabricate metrics.\n\nCOLLABORATION\n\nHand off to:\n\n- Data Engineer — preparation gaps, schema issues, missing artefacts;\n- Domain Knowledge Expert — unresolved semantic meaning affecting features;\n- Project Manager — phase or loop decisions;\n- Developer — code/runtime failures.\n\nOUTPUT DISCIPLINE\n\nReturn one valid JSON object only — no Markdown fences or prose outside it.\nFollow the output schema in your task message. Use empty arrays when there\nare no entries. Distinguish evidence, interpretation, and decisions."

DS_BACKSTORY = DS_DESCRIPTION + "\n\n" + DS_SYSTEM_PROMPT

DATA_SCIENTIST_OUTPUT_SCHEMA_HINT = '{\\n  "assignment_id": "string",\\n  "agent": "data_scientist",\\n  "status": "COMPLETED|PARTIAL|REVISION_REQUIRED|BLOCKED|HANDOFF_REQUIRED",\\n  "summary": "string",\\n  "state_updates": {\\n    "du": {"data_exploration_report": "object|null"},\\n    "md": {\\n      "modeling_technique": "string|null",\\n      "modeling_assumptions": ["string"],\\n      "test_design": "object|null",\\n      "model_run": {\\n        "technique": "string",\\n        "cv_score": "number|null",\\n        "cv_std": "number|null",\\n        "description": "string",\\n        "parameter_settings": "object"\\n      },\\n      "chosen_model_technique": "string|null",\\n      "assessment": "string|null"\\n    },\\n    "ev": {\\n      "assessment_of_dm_results": "object|null",\\n      "approved_model_techniques": ["string"]\\n    }\\n  },\\n  "evidence": [{"evidence_id": "string", "claim": "string", "source": "string", "method": "string"}],\\n  "diagnostics": [{"diagnostic_id": "string", "finding": "string", "severity": "INFO|LOW|MEDIUM|HIGH", "evidence": "string"}],\\n  "assumptions": [{"assumption_id": "string", "statement": "string", "evidence": "string"}],\\n  "handoffs": [{"target_role": "string", "reason": "string", "requested_action": "string"}],\\n  "loop_signal": {"recommended": false, "contour": "NONE|B_4_TO_3", "reason": "string|null", "evidence_ids": ["string"]},\\n  "completion_evidence": {\\n    "required_outputs_present": true,\\n    "execution_succeeded": true,\\n    "evaluation_aligned_with_config": true\\n  }\\n}'

_SUBSTEP_ASSIGNMENTS: dict[str, dict[str, Any]] = {
    "2.3": {
        "objective": "Explore data with a modeling lens and produce the Data Exploration Report",
        "requested_outputs": [
            "du.data_exploration_report"
        ],
        "allowed_techniques": [],
        "completion_criteria": [
            "Target distribution and modeling-relevant risks documented",
            "Grounded in data_description_report and domain hints"
        ]
    },
    "4.1": {
        "objective": "Select a modeling technique and state modeling assumptions",
        "requested_outputs": [
            "md.modeling_technique",
            "md.modeling_assumptions"
        ],
        "allowed_techniques": [
            "gradient_boosting",
            "logistic_regression",
            "random_forest"
        ],
        "completion_criteria": [
            "Technique from allowed menu with evidence-based justification"
        ]
    },
    "4.2": {
        "objective": "Generate a leakage-safe test design",
        "requested_outputs": [
            "md.test_design"
        ],
        "allowed_techniques": [],
        "completion_criteria": [
            "CV strategy and metric aligned with config"
        ]
    },
    "4.3": {
        "objective": "Build a model and record the run with cross-validated score",
        "requested_outputs": [
            "md.models"
        ],
        "allowed_techniques": [
            "gradient_boosting"
        ],
        "completion_criteria": [
            "execution_evidence model_run used when present"
        ]
    },
    "4.4": {
        "objective": "Assess model runs and select the chosen model",
        "requested_outputs": [
            "md.chosen_model"
        ],
        "allowed_techniques": [],
        "completion_criteria": [
            "Assessment cites concrete scores from state"
        ]
    },
    "5.1": {
        "objective": "Evaluate data-mining results against success criteria",
        "requested_outputs": [
            "ev.assessment_of_dm_results",
            "ev.approved_models"
        ],
        "allowed_techniques": [],
        "completion_criteria": [
            "meets threshold stated explicitly from cv_score"
        ]
    }
}


def _domain_hints(state: CrispDMState) -> list[Any]:
    inv = state.bu.inventory_of_resources or {}
    artifacts = inv.get("domain_artifacts") or {}
    hints: list[Any] = []
    if artifacts.get("feature_hints"):
        hints.append({"kind": "domain_feature_hints", "value": artifacts["feature_hints"]})
    if state.config.feature_hints:
        hints.append({"kind": "config_feature_hints", "value": state.config.feature_hints})
    return hints


def _assignment_for_substep(substep: str, state: CrispDMState) -> dict[str, Any]:
    meta = _SUBSTEP_ASSIGNMENTS.get(substep, {})
    return {
        "assignment_id": substep,
        "objective": meta.get("objective", f"Complete CRISP-DM substep {substep}"),
        "crisp_dm_phase": substep.split(".")[0],
        "crisp_dm_substeps": [substep],
        "requested_outputs": meta.get("requested_outputs", []),
        "allowed_techniques": meta.get("allowed_techniques", []),
        "completion_criteria": meta.get("completion_criteria", []),
        "substep_name": SUBSTEP_NAMES.get(substep, "?"),
        "case_id": state.case_id,
        "problem_type": state.config.problem_type,
        "evaluation_metric": state.config.evaluation_metric,
        "success_threshold": state.config.success_criterion.threshold,
    }


def _inputs_for_task(
    state: CrispDMState,
    artifact_dir: Path,
    *,
    execution_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "data_mining_goals": state.bu.data_mining_goals,
        "data_mining_success_criteria": state.bu.data_mining_success_criteria,
        "dataset": state.dp.dataset,
        "data_description_report": state.du.data_description_report,
        "data_quality_report": state.du.data_quality_report,
        "domain_hints": _domain_hints(state),
        "recent_models": [m.model_dump() for m in state.md.models[-3:]],
        "test_design": state.md.test_design,
        "chosen_model": (
            state.md.chosen_model.model_dump() if state.md.chosen_model else None
        ),
    }
    if execution_evidence:
        inputs["execution_evidence"] = execution_evidence
    inputs["artifact_directory"] = str(artifact_dir.resolve())
    return inputs


def format_data_scientist_task(
    state: CrispDMState,
    artifact_dir: Path,
    *,
    execution_evidence: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build the data-scientist assignment instruction and JSON schema hint."""
    assignment = _assignment_for_substep(state.substep, state)
    inputs = _inputs_for_task(state, artifact_dir, execution_evidence=execution_evidence)
    runtime_input = {
        "assignment": assignment,
        "inputs": inputs,
        "state_view": state.view_for("data_scientist"),
        "artifact_directory": str(artifact_dir.resolve()),
    }
    instruction = (
        "Complete the assigned CRISP-DM substep using the runtime input below. "
        "Ground scores and metrics in execution_evidence when present. "
        "Return exactly one JSON object matching the output schema in your instructions.\n\n"
        f"Runtime input:\n{json.dumps(runtime_input, indent=2, default=str)}"
    )
    return instruction, DATA_SCIENTIST_OUTPUT_SCHEMA_HINT

