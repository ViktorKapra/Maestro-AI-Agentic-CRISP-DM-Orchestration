"""CrewAI plumbing: build LLMs, build agents, run a single-agent JSON task.

This is the thin layer that replaces the deprecated `Agent` ABC. The agent
*wrappers* in `agents.py` call `run_json_task(...)` to get an LLM decision/output;
the deterministic orchestrator still drives the cycle.

Model selection (no architectural compromise for any backend):
    - MODEL=ollama/<name>  -> local Ollama (dev, free)
    - otherwise            -> OpenAI, tiered per agent (PM / Data Scientist -> TOP)
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache

from crewai import LLM, Agent, Crew, Task

from maads.prompts import AGENT_PROMPTS, TASK_TEMPLATE
from maads.state import SUBSTEP_NAMES, CrispDMState

# Per-agent OpenAI tier (mirrors maads.llm.llm_for).
_TOP_AGENTS = {"pm", "data_scientist", "validator"}


def build_llm(agent_name: str) -> LLM:
    """Return a CrewAI LLM for this agent, honoring MODEL / tiering env vars."""
    model = os.getenv("MODEL")
    if model and model.startswith("ollama/"):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return LLM(model=model, base_url=base_url)
    top = os.getenv("OPENAI_MODEL_TOP", "gpt-4o")
    mid = os.getenv("OPENAI_MODEL_MID", "gpt-4o-mini")
    return LLM(model=top if agent_name in _TOP_AGENTS else mid)


@lru_cache(maxsize=None)
def make_agent(agent_name: str) -> Agent:
    """Build (once per process) the CrewAI Agent for a role."""
    p = AGENT_PROMPTS[agent_name]
    return Agent(
        role=p["role"],
        goal=p["goal"],
        backstory=p["backstory"],
        llm=build_llm(agent_name),
        allow_delegation=False,
        verbose=False,
    )


def _extract_json(text: str) -> dict | None:
    """Parse JSON, with one lenient repair pass (strip fences / find the object)."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def run_json_task(
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    schema_hint: str,
) -> dict | None:
    """Run one CrewAI task for `agent_name` and return parsed JSON (or None).

    Sends only `state.view_for(agent_name)` as context (token discipline), and
    folds the reported token usage into `state.token_spend`.
    """
    view = state.view_for(agent_name)
    agent = make_agent(agent_name)
    description = TASK_TEMPLATE.format(
        substep=state.substep,
        substep_name=SUBSTEP_NAMES.get(state.substep, "?"),
        instruction=instruction,
        state_view=json.dumps(view, default=str, ensure_ascii=False),
        schema_hint=schema_hint,
    )
    task = Task(
        description=description,
        expected_output="A single JSON object, no prose, no Markdown fences.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    output = crew.kickoff()

    # Token accounting — CrewAI bypasses maads.llm, so record usage here.
    try:
        state.add_tokens(agent_name, int(output.token_usage.total_tokens))
    except (AttributeError, TypeError, ValueError):
        pass

    return _extract_json(str(output))
