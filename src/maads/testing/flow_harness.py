"""Test helpers for CrispDMFlow and RunContext."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from maads.agents import (
    DataEngineerAgent,
    DataScientistAgent,
    DeveloperAgent,
    DomainExpertAgent,
    ProjectManagerAgent,
)
from maads.flow.crisp_dm_flow import CrispDMFlow
from maads.flow.phase_runner import RunContext
from maads.state import CrispDMState


def make_flow(state: CrispDMState, artifact_dir: Path) -> CrispDMFlow:
    return CrispDMFlow(state, artifact_dir)


def make_run_context(state: CrispDMState, artifact_dir: Path) -> RunContext:
    pm = ProjectManagerAgent(artifact_dir=artifact_dir)
    agents = {
        "pm": pm,
        "domain": DomainExpertAgent(artifact_dir=artifact_dir),
        "data_engineer": DataEngineerAgent(artifact_dir=artifact_dir),
        "data_scientist": DataScientistAgent(artifact_dir=artifact_dir),
        "developer": DeveloperAgent(artifact_dir=artifact_dir),
    }
    return RunContext.create(state, artifact_dir, agents, pm)


def make_run_context_stub(state: CrispDMState, artifact_dir: Path) -> RunContext:
    """RunContext with mock agents (dispatch tracking without real agent work)."""
    pm = MagicMock()
    agents = {name: MagicMock() for name in (
        "pm", "domain", "data_engineer", "data_scientist", "developer",
    )}
    agents["pm"] = pm
    return RunContext.create(state, artifact_dir, agents, pm)
