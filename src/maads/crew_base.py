"""The CrewAI crew definition — the idiomatic `@CrewBase` surface for maads.

Agent personas come from ``config/agents.yaml`` (+ ``identities/backstories/*.md``)
and the task scaffolds from ``config/tasks.yaml``; the ``@CrewBase`` class wires them
with ``@agent`` / ``@task`` decorators exactly as the CrewAI docs prescribe. The
``agents_config`` / ``tasks_config`` paths resolve relative to this module, i.e. to
``src/maads/config/``.

The maads orchestrator runs **one** agent per CRISP-DM substep on a task whose
instruction is generated at runtime from live state + execution evidence, so there
is deliberately no static multi-task ``@crew`` here — that would misrepresent the
hub-and-spoke state machine. The per-call single-agent ``Crew`` is assembled in
``maads.crew._kickoff``; fetch an agent for a substep with :func:`agent_for`.
"""
from __future__ import annotations

import os
from functools import lru_cache

from crewai import LLM, Agent, Task
from crewai.project import CrewBase, agent, task

from maads.prompts import AGENT_PROMPTS
from maads.prompts.identities.domain import domain_identity

# PM and Data Scientist get the top OpenAI model; the others the mid model.
_TOP_AGENTS = {"pm", "data_scientist"}


def build_llm(agent_name: str) -> LLM:
    """Return a CrewAI LLM for this agent, honoring MODEL / tiering env vars.

    ``MODEL=ollama/<name>`` selects local Ollama (with optional request timeout);
    otherwise OpenAI, tiered per agent (PM / Data Scientist → ``OPENAI_MODEL_TOP``).
    """
    model = os.getenv("MODEL")
    if model and model.startswith("ollama/"):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        kwargs: dict = {"model": model, "base_url": base_url}
        timeout = os.getenv("OLLAMA_REQUEST_TIMEOUT")
        if timeout:
            try:
                kwargs["timeout"] = int(timeout)
            except ValueError:
                pass
        return LLM(**kwargs)
    top = os.getenv("OPENAI_MODEL_TOP", "gpt-4o")
    mid = os.getenv("OPENAI_MODEL_MID", "gpt-4o-mini")
    return LLM(model=top if agent_name in _TOP_AGENTS else mid)


def _build_agent(name: str, persona: dict[str, str]) -> Agent:
    """Build a CrewAI Agent from a {role, goal, backstory} persona + its tiered LLM."""
    return Agent(
        role=persona["role"],
        goal=persona["goal"],
        backstory=persona["backstory"],
        llm=build_llm(name),
        allow_delegation=False,
        verbose=False,
    )


@CrewBase
class MaadsCrew:
    """The five CRISP-DM agents and the task scaffolds, defined the CrewAI way."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def pm(self) -> Agent:
        return _build_agent("pm", AGENT_PROMPTS["pm"])

    @agent
    def domain(self) -> Agent:
        return _build_agent("domain", AGENT_PROMPTS["domain"])

    @agent
    def data_engineer(self) -> Agent:
        return _build_agent("data_engineer", AGENT_PROMPTS["data_engineer"])

    @agent
    def data_scientist(self) -> Agent:
        return _build_agent("data_scientist", AGENT_PROMPTS["data_scientist"])

    @agent
    def developer(self) -> Agent:
        return _build_agent("developer", AGENT_PROMPTS["developer"])

    @task
    def state_only_task(self) -> Task:
        """PM directive scaffold (description skeleton + expected_output from tasks.yaml)."""
        return Task(config=self.tasks_config["state_only"])

    @task
    def substep_json_task(self) -> Task:
        """Specialist substep scaffold (description skeleton + expected_output)."""
        return Task(config=self.tasks_config["substep_json"])


# One crew instance per process (replaces the old lru_cache on make_agent).
_CREW = MaadsCrew()

# Map agent slug -> its @agent method on the singleton.
_AGENT_METHODS = {
    "pm": _CREW.pm,
    "domain": _CREW.domain,
    "data_engineer": _CREW.data_engineer,
    "data_scientist": _CREW.data_scientist,
    "developer": _CREW.developer,
}


@lru_cache(maxsize=32)
def agent_for(name: str, dataset_name: str = "") -> Agent:
    """Return the CrewAI Agent for a role (cached per role + dataset).

    The Domain Expert's role/goal carry a ``{dataset_name}`` placeholder, rendered
    per dataset via :func:`maads.prompts.identities.domain.domain_identity`; all
    other agents ignore ``dataset_name``.
    """
    if name == "domain" and dataset_name:
        return _build_agent("domain", domain_identity(dataset_name))
    return _AGENT_METHODS[name]()
