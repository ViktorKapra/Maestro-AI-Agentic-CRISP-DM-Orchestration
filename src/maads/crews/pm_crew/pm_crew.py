"""PM crew — checkpoint decisions and phase-5 substeps."""
from __future__ import annotations

from pathlib import Path

from maads.crew_base import build_agent
from maads.crews.paths import AGENTS_CONFIG
from maads.prompts import AGENT_PROMPTS
from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from typing import List

from maads.crews.kickoff import kickoff_json
from maads.prompts import (
    PM_DECISION_INSTRUCTION,
    PM_NEXT_STEPS_INSTRUCTION,
    PM_REVIEW_INSTRUCTION,
)
from maads.state import CrispDMState


@CrewBase
class PMCrew:
    """Project manager crew for decisions and PM-owned substeps."""

    agents_config = AGENTS_CONFIG
    tasks_config = "config/tasks.yaml"

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def pm(self) -> Agent:
        return build_agent("pm", AGENT_PROMPTS["pm"])

    @task
    def decision_task(self) -> Task:
        return Task(config=self.tasks_config["decision_task"])  # type: ignore[index]

    @task
    def review_task(self) -> Task:
        return Task(config=self.tasks_config["review_task"])  # type: ignore[index]

    @task
    def next_steps_task(self) -> Task:
        return Task(config=self.tasks_config["next_steps_task"])  # type: ignore[index]

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=False,
        )

    def kickoff_decision(
        self,
        state: CrispDMState,
        artifact_dir: Path,
    ) -> dict | None:
        return kickoff_json(
            "pm",
            PM_DECISION_INSTRUCTION,
            state,
            artifact_dir=artifact_dir,
        )

    def kickoff_substep(
        self,
        substep: str,
        state: CrispDMState,
        artifact_dir: Path,
    ) -> dict | None:
        if substep == "5.2":
            return kickoff_json(
                "pm",
                PM_REVIEW_INSTRUCTION,
                state,
                artifact_dir=artifact_dir,
            )
        if substep == "5.3":
            return kickoff_json(
                "pm",
                PM_NEXT_STEPS_INSTRUCTION,
                state,
                artifact_dir=artifact_dir,
            )
        raise ValueError(f"pm crew does not own substep {substep}")
