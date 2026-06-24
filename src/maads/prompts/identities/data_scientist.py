"""Data Scientist — task formatting; persona lives in config/agents.yaml."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.state import CrispDMState, SUBSTEP_NAMES

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

