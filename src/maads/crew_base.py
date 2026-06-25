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
from typing import Any

import yaml
from crewai import LLM, Agent, Task
from crewai.project import CrewBase, agent, task
from importlib.resources import files

from maads.crew_tools import read_case_config_summary, validate_submission_file
from maads.knowledge_setup import skills_for
from maads.prompts import AGENT_PROMPTS
from maads.prompts.identities.domain import domain_identity

# Structured JSON / orchestration (PM decisions, domain understanding).
_JSON_AGENTS = frozenset({"pm", "domain"})
_STRUCTURED_OUTPUT_AGENTS = frozenset({"pm", "domain", "data_engineer", "data_scientist", "storyteller"})
# Python authoring and DEBUG repair (code-first workloads).
_CODE_AGENTS = frozenset({"developer", "data_engineer", "data_scientist"})


def _env_model(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


@lru_cache(maxsize=1)
def _agent_tiers() -> dict[str, str]:
    """Return agent slug -> tier (``top`` | ``mid``) from ``config/agents.yaml``."""
    spec = yaml.safe_load(
        files("maads").joinpath("config/agents.yaml").read_text(encoding="utf-8")
    )
    return {name: fields.get("tier", "mid") for name, fields in spec.items()}


def resolve_model_for_agent(agent_name: str) -> str:
    """Return the model id string for ``agent_name`` from environment variables.

    Resolution order:

        1. ``MODEL_<AGENT>`` per-role override (e.g. ``MODEL_DEVELOPER``)
        2. ``MODEL_CODE`` / ``OPENAI_MODEL_CODE`` for code-authoring roles
        3. ``MODEL_JSON`` for structured-JSON roles (Ollama path)
        4. ``MODEL`` default (Ollama) or OpenAI tiering from ``agents.yaml`` tier
    """
    override = _env_model(f"MODEL_{agent_name.upper()}")
    if override:
        return override

    default = _env_model("MODEL") or ""
    is_ollama = default.startswith("ollama/")

    if agent_name in _CODE_AGENTS:
        code = _env_model("MODEL_CODE") or _env_model("OPENAI_MODEL_CODE")
        if code:
            return code

    if agent_name in _JSON_AGENTS:
        json_model = _env_model("MODEL_JSON")
        if json_model:
            return json_model

    if is_ollama:
        return default

    top = _env_model("OPENAI_MODEL_TOP") or default or "gpt-4o"
    mid = _env_model("OPENAI_MODEL_MID") or default or "gpt-4o-mini"
    tier = _agent_tiers().get(agent_name, "mid")
    return top if tier == "top" else mid


def structured_outputs_enabled(agent_name: str, model: str) -> bool:
    """Whether to request OpenAI-style json_schema strict mode for this agent."""
    setting = os.getenv("MAADS_STRUCTURED_OUTPUTS", "auto").lower()
    if setting in {"0", "false", "no", "off"}:
        return False
    if agent_name not in _STRUCTURED_OUTPUT_AGENTS:
        return False
    if model.startswith("ollama/"):
        return setting in {"1", "true", "yes", "on", "force"}
    if setting in {"1", "true", "yes", "on", "force"}:
        return True
    return setting == "auto"


@lru_cache(maxsize=32)
def build_llm(agent_name: str) -> LLM:
    """Return a dedicated CrewAI LLM instance for this agent role."""
    model = resolve_model_for_agent(agent_name)
    if model.startswith("ollama/"):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        kwargs: dict = {"model": model, "base_url": base_url}
        timeout = os.getenv("OLLAMA_REQUEST_TIMEOUT")
        if timeout:
            try:
                kwargs["timeout"] = int(timeout)
            except ValueError:
                pass
        return LLM(**kwargs)

    kwargs = {"model": model}
    if structured_outputs_enabled(agent_name, model):
        from maads.output_contracts import output_model_for_agent

        output_model = output_model_for_agent(agent_name)
        if output_model is not None:
            kwargs["response_format"] = output_model
    try:
        return LLM(**kwargs)
    except (ImportError, TypeError, ValueError):
        kwargs.pop("response_format", None)
        return LLM(**kwargs)


def _tools_for(name: str) -> list[Any]:
    if name in {"pm", "domain"}:
        return [read_case_config_summary]
    if name == "developer":
        return [validate_submission_file]
    return []


def build_agent(name: str, persona: dict[str, str], *, case_id: str = "") -> Agent:
    """Build a CrewAI Agent from persona + tiered LLM + skills/tools/knowledge."""
    kwargs: dict[str, Any] = {
        "role": persona["role"],
        "goal": persona["goal"],
        "backstory": persona["backstory"],
        "llm": build_llm(name),
        "allow_delegation": False,
        "verbose": False,
        "tools": _tools_for(name),
    }
    skills = skills_for(name)
    if skills:
        kwargs["skills"] = skills
    return Agent(**kwargs)


@CrewBase
class MaadsCrew:
    """The five CRISP-DM agents and the task scaffolds, defined the CrewAI way."""

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def pm(self) -> Agent:
        return build_agent("pm", AGENT_PROMPTS["pm"])

    @agent
    def domain(self) -> Agent:
        return build_agent("domain", AGENT_PROMPTS["domain"])

    @agent
    def data_engineer(self) -> Agent:
        return build_agent("data_engineer", AGENT_PROMPTS["data_engineer"])

    @agent
    def data_scientist(self) -> Agent:
        return build_agent("data_scientist", AGENT_PROMPTS["data_scientist"])

    @agent
    def developer(self) -> Agent:
        return build_agent("developer", AGENT_PROMPTS["developer"])

    @agent
    def storyteller(self) -> Agent:
        return build_agent("storyteller", AGENT_PROMPTS["storyteller"])

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
    "storyteller": _CREW.storyteller,
}


@lru_cache(maxsize=32)
def agent_for(name: str, dataset_name: str = "") -> Agent:
    """Return the CrewAI Agent for a role (cached per role + dataset).

    The Domain Expert's role/goal carry a ``{dataset_name}`` placeholder, rendered
    per dataset via :func:`maads.prompts.identities.domain.domain_identity`; all
    other agents ignore ``dataset_name`` except Domain knowledge attachment.
    """
    case_id = dataset_name
    if name == "domain" and dataset_name:
        return build_agent("domain", domain_identity(dataset_name), case_id=case_id)
    if name == "domain" and case_id:
        return build_agent("domain", AGENT_PROMPTS["domain"], case_id=case_id)
    return _AGENT_METHODS[name]()


def reset_llm_caches() -> None:
    """Clear cached agents/LLMs (for tests after env changes)."""
    from maads.rag import clear_rag_cache

    build_llm.cache_clear()
    agent_for.cache_clear()
    _agent_tiers.cache_clear()
    domain_knowledge_sources.cache_clear()
    clear_rag_cache()
