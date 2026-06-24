"""Shared helpers for phase-crew substep kickoffs."""
from __future__ import annotations

from pathlib import Path

from maads.state import CrispDMState


def kickoff_json(
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    schema_hint: str = "",
    *,
    artifact_dir: Path | None = None,
) -> dict | None:
    """Run one JSON task for a phase crew substep."""
    from maads.agents import run_json_task

    return run_json_task(
        agent_name,
        instruction,
        state,
        schema_hint=schema_hint,
        artifact_dir=artifact_dir,
    )


def kickoff_text(
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    expected_output: str = "The requested output.",
) -> str:
    """Run one text/code task for a phase crew substep."""
    from maads.agents import run_text_task

    return run_text_task(agent_name, instruction, state, expected_output=expected_output)

