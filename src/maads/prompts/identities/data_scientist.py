"""Senior Data Scientist — task formatting (persona in backstories/data_scientist.md)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.output_contracts import schema_hint_for_agent
from maads.state import CrispDMState, SUBSTEP_NAMES

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
        "objective": "Select one primary modeling approach for this case and state assumptions",
        "requested_outputs": [
            "md.modeling_technique",
            "md.modeling_assumptions"
        ],
        "completion_criteria": [
            "Technique chosen from case evidence and best practices with explicit justification"
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
        "objective": "Assess model runs with execution-backed evaluation_bundle and select chosen model",
        "requested_outputs": [
            "md.chosen_model"
        ],
        "completion_criteria": [
            "evaluation_bundle includes per-class metrics and confusion matrix for classification",
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
    }
    instruction = (
        "Complete the assigned CRISP-DM substep using the runtime input below. "
        "Ground scores and metrics in execution_evidence when present. "
        "Return exactly one JSON object matching the output schema in your instructions.\n\n"
        f"Runtime input:\n{json.dumps(runtime_input, indent=2, default=str)}"
    )
    return instruction, schema_hint_for_agent("data_scientist", substep=state.substep)
