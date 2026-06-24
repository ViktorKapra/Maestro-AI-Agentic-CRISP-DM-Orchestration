"""Load agent personas and task scaffolds from the config YAML + markdown files.

`config/agents.yaml` (+ the referenced `backstories/*.md`) and `config/tasks.yaml`
are the single source of truth for the five agent identities and the three CrewAI
task scaffolds. `AGENT_PROMPTS` and the task templates in ``maads.prompts`` are
derived views built from these files at import time, so the YAML/markdown — not a
Python literal — is what you edit to change an agent's persona.

Files are resolved via ``importlib.resources`` so they load identically from a
source checkout (``uv run``) and from an installed wheel.
"""
from __future__ import annotations

from functools import lru_cache

import yaml
from importlib.resources import files


def _read(relpath: str) -> str:
    """Read a package-relative text file (POSIX-style path under ``maads/``)."""
    return files("maads").joinpath(relpath).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_agent_prompts() -> dict[str, dict[str, str]]:
    """Build the ``{agent: {role, goal, backstory}}`` map from agents.yaml + md."""
    spec = yaml.safe_load(_read("config/agents.yaml"))
    return {
        name: {
            "role": fields["role"],
            "goal": fields["goal"],
            "backstory": _read(fields["backstory_file"]),
        }
        for name, fields in spec.items()
    }


@lru_cache(maxsize=1)
def load_task_scaffolds() -> dict[str, dict[str, str]]:
    """Return the static CrewAI task scaffolds keyed by kind (description + expected_output)."""
    return yaml.safe_load(_read("config/tasks.yaml"))


def task_scaffold(kind: str) -> dict[str, str]:
    """Return the ``{description?, expected_output}`` scaffold for one task kind."""
    return load_task_scaffolds()[kind]
