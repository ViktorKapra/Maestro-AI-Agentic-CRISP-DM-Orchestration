"""Per-agent prompts and CrewAI task scaffolds.

The agent personas (role/goal/backstory) and the task scaffolds live in
``config/agents.yaml`` + ``identities/backstories/*.md`` and ``config/tasks.yaml``;
``maads.prompts.loader`` turns them into the derived views exported here. Edit the
YAML/markdown, not these constants.
"""
from __future__ import annotations

from maads.prompts.identities.data_engineer import format_data_engineer_task
from maads.prompts.identities.data_scientist import format_data_scientist_task
from maads.prompts.identities.domain import format_domain_understanding_task
from maads.prompts.loader import load_agent_prompts, task_scaffold

# {agent: {role, goal, backstory}} from config/agents.yaml + backstories/*.md.
AGENT_PROMPTS: dict[str, dict[str, str]] = load_agent_prompts()

# Which CrewAI task scaffold each agent's substep work uses.
AGENT_TASK_TEMPLATES: dict[str, str] = {
    "pm": "state_only",
    "domain": "substep_json",
    "data_engineer": "substep_json",
    "data_scientist": "substep_json",
    "developer": "substep_json",
}

# Task description skeletons — single-sourced from config/tasks.yaml.
STATE_ONLY_TASK_TEMPLATE = task_scaffold("state_only")["description"]
TASK_TEMPLATE = task_scaffold("substep_json")["description"]

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
    "format_data_engineer_task",
    "format_data_scientist_task",
    "format_domain_understanding_task",
]
