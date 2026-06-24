"""Senior Data Engineer — task formatting (persona in backstories/data_engineer.md)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.state import CrispDMState, SUBSTEP_NAMES

DATA_ENGINEER_OUTPUT_SCHEMA_HINT = '{\n  "assignment_id": "string",\n  "agent": "data_engineer",\n  "status": "COMPLETED|PARTIAL|REVISION_REQUIRED|BLOCKED|HANDOFF_REQUIRED",\n  "summary": "string",\n  "state_updates": {\n    "du": {\n      "initial_data_collection_report": "object|null",\n      "data_description_report": "object|null",\n      "data_quality_report": "object|null"\n    },\n    "dp": {\n      "rationale_for_inclusion_exclusion": "object|null",\n      "data_cleaning_report": "object|null",\n      "derived_attributes": "object|null",\n      "generated_records": "object|null",\n      "merged_data": "object|null",\n      "reformatted_data": "object|null",\n      "dataset": "object|null",\n      "dataset_description": "string|null"\n    }\n  },\n  "evidence": [{"evidence_id": "string", "claim": "string", "source": "string", "method": "string"}],\n  "decisions": [{"decision_id": "string", "decision": "string", "rationale": "string", "evidence_ids": ["string"], "affected_fields": ["string"]}],\n  "operations": [{"operation_id": "string", "operation": "string", "operation_kind": "DETERMINISTIC|LEARNED", "fit_scope": "NOT_APPLICABLE|TRAIN_PARTITION_ONLY|TRAIN_FOLD_ONLY", "status": "EXECUTED|SKIPPED|FAILED", "input_artifacts": ["string"], "output_artifacts": ["string"], "evidence": "string"}],\n  "quality_findings": [{"finding_id": "string", "severity": "INFO|LOW|MEDIUM|HIGH|BLOCKING", "category": "string", "affected_fields": ["string"], "evidence": "string", "interpretation": "string", "decision": "string"}],\n  "validations": [{"validation_id": "string", "check": "string", "status": "PASS|WARNING|FAIL|NOT_RUN", "evidence": "string"}],\n  "artifacts": [{"artifact_id": "string", "artifact_type": "string", "path": "string", "version": "string", "fingerprint": "string|null", "source_lineage": ["string"], "intended_use": "string", "validation_status": "string"}],\n  "assumptions": [{"assumption_id": "string", "statement": "string", "evidence": "string", "risk_if_wrong": "string", "confirmation_owner": "string"}],\n  "risks": [{"risk_id": "string", "severity": "string", "description": "string", "mitigation": "string", "owner": "string"}],\n  "blockers": [{"blocker_id": "string", "description": "string", "missing_requirement": "string", "requested_owner": "string"}],\n  "handoffs": [{"target_role": "string", "reason": "string", "requested_action": "string", "supporting_artifacts": ["string"]}],\n  "loop_signal": {"recommended": false, "contour": "NONE|A_2_TO_1|B_4_TO_3", "reason": "string|null", "evidence_ids": ["string"]},\n  "completion_evidence": {\n    "input_contract_valid": true,\n    "required_outputs_present": true,\n    "execution_succeeded": true,\n    "artifacts_verified": true,\n    "leakage_checks_passed": true,\n    "reproducibility_checks_passed": true,\n    "safe_for_downstream_use": true\n  }\n}'

_SUBSTEP_ASSIGNMENTS: dict[str, dict[str, Any]] = {
    "2.1": {
        "objective": "Collect initial data and produce the Initial Data Collection Report",
        "requested_outputs": ["du.initial_data_collection_report"],
        "completion_criteria": [
            "Source files inventoried and readable",
            "Train and test row counts recorded",
        ],
        "constraints": ["Do not mutate raw source files"],
    },
    "2.2": {
        "objective": "Describe the data and produce the Data Description Report",
        "requested_outputs": ["du.data_description_report"],
        "completion_criteria": [
            "Column names, dtypes, missingness, and cardinality documented",
        ],
        "constraints": ["Ground claims in executed profiling only"],
    },
    "2.4": {
        "objective": "Verify data quality and produce the Data Quality Report",
        "requested_outputs": ["du.data_quality_report"],
        "completion_criteria": [
            "Blockers and tolerable issues classified with evidence",
        ],
        "constraints": ["Recommend Loop A only with blocking contradictions"],
    },
    "3.1": {
        "objective": "Select data and document inclusion/exclusion rationale",
        "requested_outputs": ["dp.rationale_for_inclusion_exclusion"],
        "completion_criteria": ["Every retained or excluded field justified"],
        "constraints": ["Respect prediction-time availability"],
    },
    "3.2": {
        "objective": "Clean data and produce the Data Cleaning Report",
        "requested_outputs": ["dp.data_cleaning_report"],
        "completion_criteria": ["Cleaning strategy documented and leakage-safe"],
        "constraints": ["Classify operations as DETERMINISTIC or LEARNED"],
    },
    "3.3": {
        "objective": "Construct derived attributes when justified",
        "requested_outputs": ["dp.derived_attributes", "dp.generated_records"],
        "completion_criteria": ["Derived fields traceable to sources"],
        "constraints": ["No target leakage"],
    },
    "3.4": {
        "objective": "Integrate data sources when applicable",
        "requested_outputs": ["dp.merged_data"],
        "completion_criteria": ["Join cardinality validated"],
        "constraints": ["Document row-count effects"],
    },
    "3.5": {
        "objective": "Format data and produce downstream train/test datasets",
        "requested_outputs": ["dp.dataset", "dp.dataset_description"],
        "completion_criteria": [
            "Prepared train/test artifacts exist and are validated",
        ],
        "constraints": ["Preserve identifiers separately from features"],
    },
}

def _domain_evidence(state: CrispDMState) -> list[Any]:
    bu = state.bu
    inv = bu.inventory_of_resources or {}
    artifacts = inv.get("domain_artifacts") or {}
    evidence: list[Any] = []
    if bu.business_objectives:
        evidence.append({"kind": "business_objectives", "value": bu.business_objectives})
    if bu.data_mining_goals:
        evidence.append({"kind": "data_mining_goals", "value": bu.data_mining_goals})
    if artifacts:
        evidence.append({"kind": "domain_artifacts", "value": artifacts})
    if bu.terminology:
        evidence.append({"kind": "terminology", "value": bu.terminology})
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
        "substep_name": SUBSTEP_NAMES.get(substep, "?"),
        "case_id": state.case_id,
    }


def _inputs_for_task(
    state: CrispDMState,
    artifact_dir: Path,
    *,
    execution_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = state.config
    inputs: dict[str, Any] = {
        "source_locations": [
            cfg.data.train_csv,
            cfg.data.test_csv,
            cfg.data.sample_submission_csv,
        ],
        "config_path": None,
        "metadata_paths": [],
        "upstream_artifacts": [],
        "sample_output_path": cfg.data.sample_submission_csv,
        "accepted_decisions": {
            "target_column": cfg.target_column,
            "id_column": cfg.id_column,
            "evaluation_metric": cfg.evaluation_metric,
            "problem_type": cfg.problem_type,
        },
        "domain_evidence": _domain_evidence(state),
        "revision_feedback": None,
        "data_mining_goals": state.bu.data_mining_goals,
        "existing_data_understanding": state.du.model_dump(exclude_none=True),
        "existing_data_preparation": state.dp.model_dump(exclude_none=True),
    }
    if execution_evidence:
        inputs["execution_evidence"] = execution_evidence
    inputs["artifact_directory"] = str(artifact_dir.resolve())
    return inputs


def format_data_engineer_task(
    state: CrispDMState,
    artifact_dir: Path,
    *,
    execution_evidence: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build the data-engineer assignment instruction and JSON schema hint."""
    assignment = _assignment_for_substep(state.substep, state)
    inputs = _inputs_for_task(state, artifact_dir, execution_evidence=execution_evidence)
    runtime_input = {
        "assignment": assignment,
        "inputs": inputs,
        "state_view": state.view_for("data_engineer"),
        "artifact_directory": str(artifact_dir.resolve()),
    }
    instruction = (
        "Complete the assigned CRISP-DM substep using the runtime input below. "
        "Ground every claim in execution_evidence when present. "
        "Return exactly one JSON object matching the output schema in your instructions.\n\n"
        f"Runtime input:\n{json.dumps(runtime_input, indent=2, default=str)}"
    )
    return instruction, DATA_ENGINEER_OUTPUT_SCHEMA_HINT
