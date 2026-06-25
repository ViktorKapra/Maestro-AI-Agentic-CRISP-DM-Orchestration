"""Storyteller crew — report evidence and storytelling substeps."""
from __future__ import annotations

from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from typing import List

from maads.crew_base import build_agent
from maads.crews.kickoff import kickoff_json
from maads.crews.paths import AGENTS_CONFIG
from maads.prompts import AGENT_PROMPTS
from maads.prompts.identities.storyteller import format_storyteller_task
from maads.state import CrispDMState

_OWNED = frozenset({"6.2", "6.3"})


@CrewBase
class StorytellerCrew:
    agents_config = AGENTS_CONFIG
    tasks_config = "config/tasks.yaml"

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def storyteller(self) -> Agent:
        return build_agent("storyteller", AGENT_PROMPTS["storyteller"])

    @task
    def substep_json(self) -> Task:
        return Task(config=self.tasks_config["substep_json"])  # type: ignore[index]

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=False,
        )

    def kickoff_substep(
        self,
        substep: str,
        state: CrispDMState,
        artifact_dir: Path,
        *,
        execution_evidence: dict | None = None,
    ) -> dict | None:
        if substep not in _OWNED:
            raise ValueError(f"storyteller crew does not own substep {substep}")
        instruction, schema_hint = format_storyteller_task(
            state, artifact_dir, execution_evidence=execution_evidence,
        )
        return kickoff_json(
            "storyteller",
            instruction,
            state,
            schema_hint=schema_hint,
            artifact_dir=artifact_dir,
        )
