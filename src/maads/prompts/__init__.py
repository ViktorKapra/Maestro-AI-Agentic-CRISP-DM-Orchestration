"""Per-agent prompts loaded from config YAML + markdown backstories."""
from __future__ import annotations

from maads.prompts.loader import load_agent_prompts, task_scaffold
from maads.prompts.identities.data_engineer import format_data_engineer_task
from maads.prompts.identities.data_scientist import format_data_scientist_task
from maads.prompts.identities.domain import format_domain_understanding_task
from maads.prompts.identities.developer import format_developer_task

AGENT_PROMPTS: dict[str, dict[str, str]] = load_agent_prompts()

AGENT_TASK_TEMPLATES: dict[str, str] = {
    "pm": "state_only",
    "domain": "substep_json",
    "data_engineer": "substep_json",
    "data_scientist": "substep_json",
    "developer": "substep_json",
}

STATE_ONLY_TASK_TEMPLATE = task_scaffold("state_only")["description"]

TASK_TEMPLATE = task_scaffold("substep_json")["description"]

PM_REVIEW_INSTRUCTION = (
    "Produce an honest CRISP-DM 5.2 process review as JSON with key "
    '"review_of_process" (string). Reference loop_history, degraded_flags, '
    "and which phases produced weak outputs."
)

PM_NEXT_STEPS_INSTRUCTION = (
    "Produce CRISP-DM 5.3 next steps as JSON with keys: "
    '"list_of_possible_actions" (list of strings) and "decision" (string: '
    'deploy|loop_c|halt). Ground the decision in assessment_of_dm_results.'
)

PM_DECISION_INSTRUCTION = (
    "Review the state view below and issue exactly one directive JSON object "
    "as specified in your instructions."
)

__all__ = [
    "AGENT_PROMPTS",
    "AGENT_TASK_TEMPLATES",
    "STATE_ONLY_TASK_TEMPLATE",
    "TASK_TEMPLATE",
    "PM_DECISION_INSTRUCTION",
    "PM_REVIEW_INSTRUCTION",
    "PM_NEXT_STEPS_INSTRUCTION",
    "format_data_engineer_task",
    "format_data_scientist_task",
    "format_domain_understanding_task",
    "format_developer_task",
]
