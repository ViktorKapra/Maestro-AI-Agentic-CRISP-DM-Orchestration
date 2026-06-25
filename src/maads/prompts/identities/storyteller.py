"""Storyteller — task formatting."""
from __future__ import annotations

import json
from pathlib import Path

from maads.output_contracts import schema_hint_for_agent
from maads.state import CrispDMState, SUBSTEP_NAMES

STORYTELLER_OUTPUT_SCHEMA_HINT = schema_hint_for_agent("storyteller")

_SUBSTEP_ASSIGNMENTS: dict[str, dict] = {
    "6.2": {
        "objective": "Generate report evidence and storytelling specification from evaluation_bundle",
        "requested_outputs": ["story_spec", "dep.story_spec_path"],
        "completion_criteria": [
            "story_spec references only metrics present in evaluation_bundle",
            "interpretations use real class names from class_labels",
            "methodological warnings flag imbalance or degraded steps when present",
        ],
        "constraints": [
            "Do not invent metrics or figures not in evaluation_bundle",
        ],
    },
    "6.3": {
        "objective": "Produce final_report.md (handled deterministically by capability layer)",
        "requested_outputs": ["dep.final_report_path"],
        "completion_criteria": ["Report path recorded after render"],
        "constraints": [],
    },
}


def format_storyteller_task(
    state: CrispDMState,
    artifact_dir: Path,
    *,
    execution_evidence: dict | None = None,
) -> tuple[str, str]:
    substep = state.substep
    assignment = _SUBSTEP_ASSIGNMENTS.get(substep, {})
    view = state.view_for("storyteller")
    if execution_evidence:
        view["execution_evidence"] = execution_evidence
    instruction = (
        f"CRISP-DM {substep} ({SUBSTEP_NAMES.get(substep, substep)}): "
        f"{assignment.get('objective', 'Complete storyteller substep')}. "
        f"Requested outputs: {assignment.get('requested_outputs', [])}. "
        f"Completion criteria: {assignment.get('completion_criteria', [])}. "
        f"Constraints: {assignment.get('constraints', [])}. "
        f"Artifact directory: {artifact_dir}."
    )
    if substep == "6.2":
        instruction += (
            " Build story_spec from evaluation_bundle in the state view. "
            "Every interpretation must cite a metric that exists in the bundle."
        )
    return instruction, STORYTELLER_OUTPUT_SCHEMA_HINT
