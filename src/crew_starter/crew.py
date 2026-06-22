"""Defines the crew: which agents exist, which tasks they run, and in what order.

CrewAI's @CrewBase decorator reads the two YAML files in config/ and lets you
attach each entry to a method with @agent / @task. The @crew method assembles
them into a runnable Crew. This is the standard CrewAI project layout, trimmed
to the essentials.
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task


@CrewBase
class CrewStarter:
    """A minimal two-agent crew: a researcher hands its findings to a writer."""

    # These paths point at the YAML files next to this module.
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(config=self.agents_config["researcher"], verbose=True)

    @agent
    def writer(self) -> Agent:
        return Agent(config=self.agents_config["writer"], verbose=True)

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @task
    def write_task(self) -> Task:
        return Task(config=self.tasks_config["write_task"])

    @crew
    def crew(self) -> Crew:
        # Process.sequential runs tasks in the order they are listed; the output
        # of each becomes context for the next. (CrewAI also offers hierarchical.)
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
