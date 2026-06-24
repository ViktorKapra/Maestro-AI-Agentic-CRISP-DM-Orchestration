"""Senior Data Scientist — task formatting (persona in backstories/data_scientist.md)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.state import CrispDMState, SUBSTEP_NAMES

DATA_SCIENTIST_OUTPUT_SCHEMA_HINT = "{\n  \"assignment_id\": \"string\",\n  \"agent\": \"data_scientist\",\n  \"status\": \"COMPLETED|PARTIAL|REVISION_REQUIRED|BLOCKED|HANDOFF_REQUIRED\",\n  \"summary\": \"string\",\n  \"state_updates\": {\n    \"du\": {\"data_exploration_report\": \"object|null\"},\n    \"md\": {\n      \"modeling_technique\": \"string|null\",\n      \"modeling_assumptions\": [\"string\"],\n      \"test_design\": \"object|null\",\n      \"models_append\": [\"ModelRun\"],\n      \"chosen_model\": \"ModelRun|null\"\n    },\n    \"ev\": {\n      \"assessment_of_dm_results\": \"object|null\",\n      \"approved_models\": [\"ModelRun\"]\n    }\n  },\n  \"model_runs\": [{\n    \"technique\": \"string\",\n    \"parameter_settings\": \"object\",\n    \"description\": \"string\",\n    \"cv_score\": \"number|null\",\n    \"cv_score_std\": \"number|null\",\n    \"holdout_score\": \"number|null\",\n    \"assessment\": \"string|null\",\n    \"revised_parameter_settings\": \"object|null\",\n    \"is_baseline\": \"boolean\"\n  }],\n  \"evidence\": [{\"evidence_id\": \"string\", \"claim\": \"string\", \"source\": \"string\", \"method\": \"string\"}],\n  \"decisions\": [{\"decision_id\": \"string\", \"decision\": \"string\", \"rationale\": \"string\", \"evidence_ids\": [\"string\"], \"affected_fields\": [\"string\"]}],\n  \"validations\": [{\"validation_id\": \"string\", \"check\": \"string\", \"status\": \"PASS|WARNING|FAIL|NOT_RUN\", \"evidence\": \"string\"}],\n  \"leakage_checks\": [{\"check\": \"string\", \"status\": \"PASS|WARNING|FAIL\", \"evidence\": \"string\"}],\n  \"diagnostics\": [{\"finding_id\": \"string\", \"category\": \"string\", \"severity\": \"INFO|LOW|MEDIUM|HIGH\", \"evidence\": \"string\", \"interpretation\": \"string\", \"recommended_owner\": \"string\"}],\n  \"artifacts\": [{\"artifact_id\": \"string\", \"artifact_type\": \"string\", \"path\": \"string\", \"version\": \"string\", \"fingerprint\": \"string|null\", \"source_lineage\": [\"string\"], \"intended_use\": \"string\", \"validation_status\": \"string\"}],\n  \"assumptions\": [{\"assumption_id\": \"string\", \"statement\": \"string\", \"evidence\": \"string\", \"risk_if_wrong\": \"string\", \"confirmation_owner\": \"string\"}],\n  \"risks\": [{\"risk_id\": \"string\", \"severity\": \"string\", \"description\": \"string\", \"mitigation\": \"string\", \"owner\": \"string\"}],\n  \"blockers\": [{\"blocker_id\": \"string\", \"description\": \"string\", \"missing_requirement\": \"string\", \"requested_owner\": \"string\"}],\n  \"handoffs\": [{\"target_role\": \"string\", \"reason\": \"string\", \"requested_action\": \"string\", \"supporting_artifacts\": [\"string\"]}],\n  \"loop_signal\": {\"recommended\": false, \"contour\": \"NONE|B_4_TO_3|C_5_TO_1\", \"reason\": \"string|null\", \"evidence_ids\": [\"string\"]},\n  \"completion_evidence\": {\n    \"input_contract_valid\": true,\n    \"required_outputs_present\": true,\n    \"execution_succeeded\": true,\n    \"baseline_established\": true,\n    \"leakage_checks_passed\": true,\n    \"uncertainty_reported\": true,\n    \"evaluated_against_success_criterion\": \"boolean|null\",\n    \"safe_for_downstream_use\": true\n  }\n}"

_SUBSTEP_ASSIGNMENTS: dict[str, dict[str, Any]] = {
    "2.3": {
        "objective": "Explore data with a modeling lens and produce the Data Exploration Report",
        "requested_outputs": [
            "du.data_exploration_report"
        ],
        "completion_criteria": [
            "Target distribution, class balance, and leakage suspicions documented",
            "Extends data_description_report with modeling-relevant findings"
        ],
        "constraints": [
            "Do not overwrite the Data Engineer's 2.2 report"
        ]
    },
    "4.1": {
        "objective": "Select one modeling technique from the constrained menu and state assumptions",
        "requested_outputs": [
            "md.modeling_technique",
            "md.modeling_assumptions"
        ],
        "completion_criteria": [
            "Technique chosen from menu for config.problem_type with evidence-based justification"
        ],
        "constraints": [
            "Establish a baseline before complexity"
        ]
    },
    "4.2": {
        "objective": "Generate a leakage-safe, reproducible test design",
        "requested_outputs": [
            "md.test_design"
        ],
        "completion_criteria": [
            "Folds, seed, metric, and split type recorded for reproducibility"
        ],
        "constraints": [
            "Fit learned steps inside training folds only"
        ]
    },
    "4.3": {
        "objective": "Build a model and append a ModelRun with cross-validated score and uncertainty",
        "requested_outputs": [
            "md.models"
        ],
        "completion_criteria": [
            "Report CV mean and std; ground scores in execution_evidence when present",
            "Record is_baseline=true for the first simple baseline"
        ],
        "constraints": [
            "Respect inputs.max_model_iterations cap"
        ]
    },
    "4.4": {
        "objective": "Assess model runs and select the chosen model",
        "requested_outputs": [
            "md.chosen_model"
        ],
        "completion_criteria": [
            "Assessment cites concrete scores; compare against baseline"
        ],
        "constraints": [
            "Emit concrete diagnostic on weak results, do not silently iterate"
        ]
    },
    "5.1": {
        "objective": "Evaluate data-mining results against the agreed success criterion",
        "requested_outputs": [
            "ev.assessment_of_dm_results",
            "ev.approved_models"
        ],
        "completion_criteria": [
            "meets boolean stated explicitly against config threshold with uncertainty"
        ],
        "constraints": [
            "Recommend C_5_TO_1 when criterion not met; PM decides whether to loop"
        ]
    }
}


def _domain_evidence(state: CrispDMState) -> list[Any]:
    inv = state.bu.inventory_of_resources or {}
    artifacts = inv.get("domain_artifacts") or {}
    evidence: list[Any] = []
    if artifacts.get("feature_hints"):
        evidence.append({"kind": "domain_feature_hints", "value": artifacts["feature_hints"]})
    if state.config.feature_hints:
        evidence.append({"kind": "config_feature_hints", "value": state.config.feature_hints})
    if artifacts:
        evidence.append({"kind": "domain_artifacts", "value": artifacts})
    return evidence


def _assignment_for_substep(substep: str, state: CrispDMState) -> dict[str, Any]:
    meta = _SUBSTEP_ASSIGNMENTS.get(substep, {})
    return {
        "assignment_id": substep,
        "objective": meta.get("objective", f"Complete CRISP-DM substep {substep}"),
        "crisp_dm_phase": substep.split(".")[0],
        "crisp_dm_substeps": [substep],
        "requested_outputs": meta.get("requested_outputs", []),
        "completion_criteria": meta.get("completion_criteria", []),
        "constraints": meta.get("constraints", []),
        "revision_feedback": None,
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
    cfg = state.config
    inputs: dict[str, Any] = {
        "dataset": state.dp.dataset,
        "upstream_artifacts": [],
        "accepted_decisions": {
            "target_column": cfg.target_column,
            "id_column": cfg.id_column,
            "evaluation_metric": cfg.evaluation_metric,
            "problem_type": cfg.problem_type,
        },
        "domain_evidence": _domain_evidence(state),
        "helper_modules": [],
        "max_model_iterations": 3,
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
