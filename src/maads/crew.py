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
from contextvars import ContextVar
from functools import lru_cache

from crewai import LLM, Agent, Crew, Task

from maads.prompts import (
    AGENT_TASK_TEMPLATES,
    AGENT_PROMPTS,
    STATE_ONLY_TASK_TEMPLATE,
    TASK_TEMPLATE,
)
from maads.prompts.identities.domain import domain_identity
from maads.state import SUBSTEP_NAMES, CrispDMState

# Per-agent OpenAI tier: PM and Data Scientist use the top model.
_TOP_AGENTS = {"pm", "data_scientist"}

_last_crew_output: ContextVar[str | None] = ContextVar("_last_crew_output", default=None)
_last_crew_tokens: ContextVar[int | None] = ContextVar("_last_crew_tokens", default=None)


def pop_last_kickoff_output() -> tuple[str | None, int | None]:
    """Return (raw_output, total_tokens) from the most recent kickoff in this context."""
    raw = _last_crew_output.get()
    tokens = _last_crew_tokens.get()
    _last_crew_output.set(None)
    _last_crew_tokens.set(None)
    return raw, tokens


class CrewKickoffError(RuntimeError):
    """CrewAI kickoff failed (LLM timeout, provider error, etc.)."""


def build_llm(agent_name: str) -> LLM:
    """Return a CrewAI LLM for this agent, honoring MODEL / tiering env vars."""
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


@lru_cache(maxsize=32)
def make_agent(agent_name: str, dataset_name: str = "") -> Agent:
    """Build (once per process per dataset) the CrewAI Agent for a role."""
    if agent_name == "domain" and dataset_name:
        p = domain_identity(dataset_name)
    else:
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
    """Parse JSON, with one lenient repair pass (strip fences / find the object).

    Reasoning models (e.g. minimax-m3) prepend a ``<think>...</think>`` block whose
    prose contains braces, which would otherwise derail the greedy object search
    below. Strip such blocks first so only the real answer is parsed.
    """
    if not text or not str(text).strip():
        return None
    text = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", str(text),
                  flags=re.DOTALL | re.IGNORECASE).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _check_token_budget(state: CrispDMState) -> None:
    cap = os.getenv("MAX_TOKENS_PER_RUN")
    if not cap:
        return
    try:
        limit = int(cap)
    except ValueError:
        return
    if sum(state.token_spend.values()) >= limit:
        raise RuntimeError(
            f"Run-wide token cap of {cap} reached. Halting to avoid runaway cost."
        )


def build_task_description(
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    schema_hint: str = "",
) -> tuple[str, str, Agent]:
    """Assemble the CrewAI Task description; returns (description, state_view_json, agent)."""
    view = state.view_for(agent_name)
    dataset_name = state.case_id if agent_name == "domain" else ""
    agent = make_agent(agent_name, dataset_name)
    state_view = json.dumps(view, default=str, ensure_ascii=False)
    template_kind = AGENT_TASK_TEMPLATES.get(agent_name, "substep_json")
    if template_kind == "state_only":
        description = STATE_ONLY_TASK_TEMPLATE.format(
            state_view=state_view,
            instruction=instruction,
        )
    else:
        description = TASK_TEMPLATE.format(
            substep=state.substep,
            substep_name=SUBSTEP_NAMES.get(state.substep, "?"),
            instruction=instruction,
            state_view=state_view,
            schema_hint=schema_hint,
        )
    return description, state_view, agent


def _kickoff(
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    schema_hint: str,
    expected_output: str,
) -> str:
    """Run one CrewAI task and return its raw string output.

    Sends only `state.view_for(agent_name)` as context (token discipline) and
    folds the reported token usage into `state.token_spend`.

    Raises:
        CrewKickoffError: when CrewAI kickoff fails.
        RuntimeError: when MAX_TOKENS_PER_RUN is exceeded after the call.
    """
    description, _state_view, agent = build_task_description(
        agent_name, instruction, state, schema_hint
    )
    task = Task(description=description, expected_output=expected_output, agent=agent)
    crew = Crew(agents=[agent], tasks=[task], verbose=False)
    try:
        output = crew.kickoff()
    except Exception as exc:
        raise CrewKickoffError(f"CrewAI kickoff failed for {agent_name}: {exc}") from exc

    raw_output = str(output)
    _last_crew_output.set(raw_output)
    total_tokens = None
    try:
        total_tokens = int(output.token_usage.total_tokens)
    except (AttributeError, TypeError, ValueError):
        pass
    _last_crew_tokens.set(total_tokens)

    # Token accounting — record CrewAI usage on shared state.
    try:
        if total_tokens is not None:
            state.add_tokens(agent_name, total_tokens)
    except (AttributeError, TypeError, ValueError):
        pass
    _check_token_budget(state)
    return raw_output


def run_json_task(
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    schema_hint: str = "",
) -> dict | None:
    """Run one CrewAI task for `agent_name` and return parsed JSON (or None).

    Raises:
        CrewKickoffError: when kickoff fails or the output is not JSON.
        RuntimeError: when MAX_TOKENS_PER_RUN is exceeded after the call.
    """
    raw_output = _kickoff(
        agent_name, instruction, state, schema_hint,
        expected_output="A single JSON object, no prose, no Markdown fences.",
    )
    parsed = _extract_json(raw_output)
    if parsed is None and raw_output.strip():
        raise CrewKickoffError(
            f"CrewAI returned non-JSON output for {agent_name} at substep {state.substep}"
        )
    return parsed


def run_text_task(
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    expected_output: str = "The requested output.",
) -> str:
    """Run one CrewAI task and return the raw text output (no JSON parsing).

    Used for code authoring, where demanding JSON-wrapped code would force the
    model to escape quotes/newlines inside a string — exactly what small models
    get wrong. Instead the agent returns a fenced code block we extract verbatim.

    Raises:
        CrewKickoffError: when CrewAI kickoff fails.
        RuntimeError: when MAX_TOKENS_PER_RUN is exceeded after the call.
    """
    return _kickoff(agent_name, instruction, state, "", expected_output)
