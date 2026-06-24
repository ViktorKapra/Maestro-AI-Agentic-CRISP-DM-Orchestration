"""Domain expert crew — Business Understanding substeps 1.1–1.3."""
from __future__ import annotations

from pathlib import Path

from maads.crew_base import _build_agent
from maads.prompts import AGENT_PROMPTS
from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from typing import List

from maads.crews.kickoff import kickoff_json
from maads.prompts.identities.domain import (
    format_domain_refine_goals_task,
    format_domain_situation_task,
    format_domain_understanding_task,
)
from maads.state import CrispDMState

_SUBSTEP_TASKS = {
    "1.1": ("task_1_1", format_domain_understanding_task),
    "1.2": ("task_1_2", format_domain_situation_task),
    "1.3": ("task_1_3", format_domain_refine_goals_task),
}


@CrewBase
class DomainCrew:
    """Domain knowledge crew for phase 1 substeps."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def domain(self) -> Agent:
        return _build_agent("domain", AGENT_PROMPTS["domain"])

    @task
    def task_1_1(self) -> Task:
        return Task(config=self.tasks_config["task_1_1"])  # type: ignore[index]

    @task
    def task_1_2(self) -> Task:
        return Task(config=self.tasks_config["task_1_2"])  # type: ignore[index]

    @task
    def task_1_3(self) -> Task:
        return Task(config=self.tasks_config["task_1_3"])  # type: ignore[index]

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
    ) -> dict | None:
        """Run one domain substep via the shared JSON kickoff seam."""
        if substep not in _SUBSTEP_TASKS:
            raise ValueError(f"domain crew does not own substep {substep}")
        _task_name, formatter = _SUBSTEP_TASKS[substep]
        instruction, schema_hint = formatter(state)
        return kickoff_json(
            "domain",
            instruction,
            state,
            schema_hint=schema_hint,
            artifact_dir=artifact_dir,
        )
