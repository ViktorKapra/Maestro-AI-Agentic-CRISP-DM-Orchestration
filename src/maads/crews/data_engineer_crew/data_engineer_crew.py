"""Data engineer crew — Data Understanding and Data Preparation substeps."""
from __future__ import annotations

from pathlib import Path

from maads.crew_base import _build_agent
from maads.prompts import AGENT_PROMPTS
from crewai import Agent, Crew, Process, Task
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task
from typing import List

from maads.crews.kickoff import kickoff_json
from maads.prompts.identities.data_engineer import format_data_engineer_task
from maads.state import CrispDMState

_OWNED = frozenset({"2.1", "2.2", "2.4", "3.1", "3.2", "3.3", "3.4", "3.5"})


@CrewBase
class DataEngineerCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def data_engineer(self) -> Agent:
        return _build_agent("data_engineer", AGENT_PROMPTS["data_engineer"])

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
            raise ValueError(f"data engineer crew does not own substep {substep}")
        instruction, schema_hint = format_data_engineer_task(
            state, artifact_dir, execution_evidence=execution_evidence,
        )
        return kickoff_json(
            "data_engineer",
            instruction,
            state,
            schema_hint=schema_hint,
            artifact_dir=artifact_dir,
        )
