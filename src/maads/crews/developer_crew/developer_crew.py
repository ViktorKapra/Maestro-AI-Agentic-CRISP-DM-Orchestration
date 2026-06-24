"""Developer crew — deployment substeps (mostly deterministic via capabilities)."""
from __future__ import annotations

from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from typing import List

from maads.crew_base import _build_agent
from maads.prompts import AGENT_PROMPTS


@CrewBase
class DeveloperCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def developer(self) -> Agent:
        return _build_agent("developer", AGENT_PROMPTS["developer"])

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
