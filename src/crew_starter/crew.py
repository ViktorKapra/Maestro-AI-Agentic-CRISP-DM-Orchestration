"""Defines the crew: which agents exist, which tasks they run, and in what order.

CrewAI's @CrewBase decorator reads the two YAML files in config/ and lets you
attach each entry to a method with @agent / @task. The @crew method assembles
them into a runnable Crew. This is the standard CrewAI project layout, trimmed
to the essentials.
"""

import os
from functools import lru_cache

from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task


@lru_cache(maxsize=1)
def _build_llm() -> LLM | None:
    """Pick the LLM from the MODEL env var.

    - "ollama/<name>" (e.g. "ollama/gemma2:9b") -> talk to a local Ollama server,
      so you can develop offline/for free before switching to a smarter model.
    - anything else (e.g. "gpt-4o-mini") -> pass straight through to LiteLLM,
      which uses OPENAI_API_KEY.
    - unset -> return None and let CrewAI fall back to its own default.
    """
    model = os.getenv("MODEL")
    if not model:
        return None
    if model.startswith("ollama/"):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return LLM(model=model, base_url=base_url)
    return LLM(model=model)


@CrewBase
class CrewStarter:
    """A minimal two-agent crew: a researcher hands its findings to a writer."""

    # These paths point at the YAML files next to this module.
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # _build_llm() is cached, so every agent shares one model instance. It is
    # called here (at agent-construction time) rather than at import, so it runs
    # after main.py's load_dotenv() and actually sees MODEL.
    @agent
    def researcher(self) -> Agent:
        return Agent(config=self.agents_config["researcher"], llm=_build_llm(), verbose=True)

    @agent
    def writer(self) -> Agent:
        return Agent(config=self.agents_config["writer"], llm=_build_llm(), verbose=True)

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
