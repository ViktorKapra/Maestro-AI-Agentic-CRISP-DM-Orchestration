"""Senior Developer — task formatting (persona in backstories/developer.md)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.state import CrispDMState, SUBSTEP_NAMES

MAX_DEBUG_RETRIES = 3

DEVELOPER_OUTPUT_SCHEMA_HINT = "{\n  \"assignment_id\": \"string\",\n  \"agent\": \"developer\",\n  \"mode\": \"string\",\n  \"status\": \"COMPLETED|PARTIAL|FIXED|REVISION_REQUIRED|BLOCKED|STUCK|HANDOFF_REQUIRED\",\n  \"summary\": \"string\",\n  \"state_updates\": {\n    \"dep\": {\n      \"deployment_plan\": \"string|null\",\n      \"submission_path\": \"path|null\",\n      \"monitoring_and_maintenance_plan\": \"string|null\",\n      \"final_report_path\": \"path|null\",\n      \"final_presentation_path\": \"path|null\",\n      \"experience_documentation\": \"string|null\"\n    }\n  },\n  \"diagnosis\": {\n    \"error_class\": \"schema_error|shape_mismatch|type_error|leakage_signal|lib_version|oom|timeout|syntax_error|json_parse|other|none\",\n    \"root_cause\": \"string|null\",\n    \"offending_columns\": [\"string\"],\n    \"smallest_fix\": \"string|null\"\n  },\n  \"fix_attempts\": [{\"attempt\": \"integer\", \"change\": \"string\", \"exec_status\": \"EXECUTED|FAILED|TIMED_OUT\", \"stdout_excerpt\": \"string\", \"stderr_excerpt\": \"string\"}],\n  \"operations\": [{\"operation_id\": \"string\", \"operation\": \"string\", \"operation_kind\": \"DETERMINISTIC|LEARNED\", \"status\": \"EXECUTED|SKIPPED|FAILED\", \"input_artifacts\": [\"string\"], \"output_artifacts\": [\"string\"], \"evidence\": \"string\"}],\n  \"validations\": [{\"validation_id\": \"string\", \"check\": \"string\", \"status\": \"PASS|WARNING|FAIL|NOT_RUN\", \"evidence\": \"string\"}],\n  \"artifacts\": [{\"artifact_id\": \"string\", \"artifact_type\": \"string\", \"path\": \"string\", \"version\": \"string\", \"fingerprint\": \"string|null\", \"source_lineage\": [\"string\"], \"intended_use\": \"string\", \"validation_status\": \"string\"}],\n  \"assumptions\": [{\"assumption_id\": \"string\", \"statement\": \"string\", \"evidence\": \"string\", \"risk_if_wrong\": \"string\", \"confirmation_owner\": \"string\"}],\n  \"risks\": [{\"risk_id\": \"string\", \"severity\": \"string\", \"description\": \"string\", \"mitigation\": \"string\", \"owner\": \"string\"}],\n  \"blockers\": [{\"blocker_id\": \"string\", \"description\": \"string\", \"missing_requirement\": \"string\", \"requested_owner\": \"string\"}],\n  \"handoffs\": [{\"target_role\": \"string\", \"reason\": \"string\", \"requested_action\": \"string\", \"supporting_artifacts\": [\"string\"]}],\n  \"loop_signal\": {\"recommended\": false, \"contour\": \"NONE|B_4_TO_3\", \"reason\": \"string|null\", \"evidence_ids\": [\"string\"]},\n  \"completion_evidence\": {\n    \"input_contract_valid\": true,\n    \"required_outputs_present\": true,\n    \"execution_succeeded\": true,\n    \"artifacts_verified\": true,\n    \"submission_schema_matches_template\": \"boolean|null\",\n    \"reproducibility_checks_passed\": true,\n    \"safe_for_downstream_use\": true\n  }\n}"

_SUBSTEP_ASSIGNMENTS: dict[str, dict[str, Any]] = {
    "6.1": {
        "mode": "DEPLOY",
        "objective": "Plan deployment and build a schema-valid submission.csv",
        "requested_outputs": [
            "dep.deployment_plan",
            "dep.submission_path"
        ],
        "completion_criteria": [
            "submission validated against sample_submission_csv before write",
            "dep.submission_path set to verified artifact"
        ],
        "constraints": [
            "Never treat sample submission as ground-truth labels"
        ]
    },
    "6.2": {
        "mode": "DEPLOY",
        "objective": "Plan monitoring and maintenance for the deployed model",
        "requested_outputs": [
            "dep.monitoring_and_maintenance_plan"
        ],
        "completion_criteria": [
            "Drift signals and retrain triggers specific to this model and metric"
        ],
        "constraints": []
    },
    "6.3": {
        "mode": "DEPLOY",
        "objective": "Produce the final report from run evidence",
        "requested_outputs": [
            "dep.final_report_path"
        ],
        "completion_criteria": [
            "final_report.md assembled from objective, scores, loops, submission result"
        ],
        "constraints": []
    },
    "6.4": {
        "mode": "DEPLOY",
        "objective": "Review the project and document experience",
        "requested_outputs": [
            "dep.experience_documentation"
        ],
        "completion_criteria": [
            "Honest review of what worked, broke, and lessons for next runs"
        ],
        "constraints": []
    }
}


def _assignment_for_substep(substep: str, state: CrispDMState) -> dict[str, Any]:
    meta = _SUBSTEP_ASSIGNMENTS.get(substep, {})
    return {
        "assignment_id": substep,
        "mode": meta.get("mode", "DEPLOY"),
        "objective": meta.get("objective", f"Complete CRISP-DM substep {substep}"),
        "crisp_dm_substeps": [substep],
        "requesting_agent": None,
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
        "dataset": state.dp.dataset,
        "chosen_model": (
            state.md.chosen_model.model_dump() if state.md.chosen_model else None
        ),
        "sample_submission_csv": cfg.data.sample_submission_csv,
        "retry_budget": 3,
        "upstream_artifacts": [],
    }
    if execution_evidence:
        inputs["execution_evidence"] = execution_evidence
    inputs["artifact_directory"] = str(artifact_dir.resolve())
    return inputs


def format_developer_debug_task(
    state: CrispDMState,
    artifact_dir: Path,
    *,
    failure_kind: str,
    requesting_agent: str,
    error_class: str,
    last_error: str,
    stderr_excerpt: str,
    failing_code: str,
    header_var_names: list[str],
    contract_hint: str,
    schema_columns: list[str],
    attempt: int = 1,
    max_retries: int = MAX_DEBUG_RETRIES,
    malformed_json: str = "",
    task_instruction: str = "",
) -> str:
    """Build a DEBUG-mode instruction for the Developer LLM."""
    runtime_input = {
        "assignment": {
            "assignment_id": f"debug-{state.substep}",
            "mode": "DEBUG",
            "objective": f"Repair {failure_kind} failure from {requesting_agent}",
            "requesting_agent": requesting_agent,
            "crisp_dm_substep": state.substep,
            "case_id": state.case_id,
        },
        "failure": {
            "kind": failure_kind,
            "error_class": error_class,
            "last_error": last_error,
            "stderr_excerpt": stderr_excerpt,
            "attempt": attempt,
            "retry_budget": max_retries,
        },
        "inputs": {
            "failing_code": failing_code or None,
            "header_variables": header_var_names,
            "contract_hint": contract_hint,
            "schema_columns": schema_columns,
            "malformed_json": malformed_json or None,
            "original_task_instruction": task_instruction or None,
            "data_description_report": state.du.data_description_report,
        },
        "state_view": state.view_for("developer"),
        "artifact_directory": str(artifact_dir.resolve()),
    }
    if failure_kind == "python_exec":
        deliverable = (
            "Return ONLY a ```python ...``` code block containing the SMALLEST fix. "
            "Do not redefine injected header variables. The code must print exactly "
            "one JSON object line to stdout when executed."
        )
    else:
        deliverable = (
            "Return ONLY a single valid JSON object matching the contract_hint / "
            "original task shape. No markdown fences, no commentary."
        )
    return (
        "DEBUG mode — you are the on-call Developer. Diagnose the failure below, "
        "apply the smallest correct fix, and return executable output.\n"
        f"{deliverable}\n\n"
        f"Runtime input:\n{json.dumps(runtime_input, indent=2, default=str)}"
    )


def format_developer_task(
    state: CrispDMState,
    artifact_dir: Path,
    *,
    execution_evidence: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Build the developer assignment instruction and JSON schema hint."""
    assignment = _assignment_for_substep(state.substep, state)
    inputs = _inputs_for_task(state, artifact_dir, execution_evidence=execution_evidence)
    runtime_input = {
        "assignment": assignment,
        "inputs": inputs,
        "state_view": state.view_for("developer"),
        "artifact_directory": str(artifact_dir.resolve()),
    }
    instruction = (
        "Complete the assigned CRISP-DM substep using the runtime input below. "
        "Ground every claim in execution_evidence when present. "
        "Return exactly one JSON object matching the output schema in your instructions.\n\n"
        f"Runtime input:\n{json.dumps(runtime_input, indent=2, default=str)}"
    )
    return instruction, DEVELOPER_OUTPUT_SCHEMA_HINT
