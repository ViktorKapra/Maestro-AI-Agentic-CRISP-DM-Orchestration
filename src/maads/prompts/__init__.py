"""Per-agent prompts embedded as Python constants."""
from __future__ import annotations

from maads.prompts.identities.data_engineer import (
    DE_BACKSTORY,
    DE_GOAL,
    DE_ROLE,
    format_data_engineer_task,
)
from maads.prompts.identities.data_scientist import (
    DS_BACKSTORY,
    DS_GOAL,
    DS_ROLE,
    format_data_scientist_task,
)
from maads.prompts.identities.domain import (
    DOMAIN_BACKSTORY,
    DOMAIN_GOAL,
    DOMAIN_ROLE_TEMPLATE,
    format_domain_understanding_task,
)
from maads.prompts.identities.pm import PM_BACKSTORY, PM_GOAL, PM_ROLE

AGENT_PROMPTS: dict[str, dict[str, str]] = {
    "pm": {"role": PM_ROLE, "goal": PM_GOAL, "backstory": PM_BACKSTORY},
    "domain": {
        "role": DOMAIN_ROLE_TEMPLATE,
        "goal": DOMAIN_GOAL,
        "backstory": DOMAIN_BACKSTORY,
    },
    "data_engineer": {
        "role": DE_ROLE,
        "goal": DE_GOAL,
        "backstory": DE_BACKSTORY,
    },
    "data_scientist": {
        "role": DS_ROLE,
        "goal": DS_GOAL,
        "backstory": DS_BACKSTORY,
    },
    "developer": {
        "role": "Developer & On-call Debugger",
        "goal": (
            "Produce the deployment artefacts (a valid submission.csv) and fix "
            "broken code for the other agents."
        ),
        "backstory": (
            "You keep the crew from drowning in its own errors: diagnose first, "
            "propose the smallest fix, validate the submission schema before writing."
        ),
    },
}

AGENT_TASK_TEMPLATES: dict[str, str] = {
    "pm": "state_only",
    "domain": "substep_json",
    "data_engineer": "substep_json",
    "data_scientist": "substep_json",
    "developer": "substep_json",
}

STATE_ONLY_TASK_TEMPLATE = (
    "Current CRISP-DM state (JSON):\n{state_view}\n\n{instruction}"
)

TASK_TEMPLATE = (
    "CRISP-DM substep {substep} ({substep_name}).\n"
    "{instruction}\n\n"
    "Relevant state (JSON):\n{state_view}\n\n"
    "Respond ONLY with JSON matching: {schema_hint}"
)

PM_DECISION_INSTRUCTION = (
    "Review the state view below and issue exactly one directive JSON object "
    "as specified in your instructions."
)
