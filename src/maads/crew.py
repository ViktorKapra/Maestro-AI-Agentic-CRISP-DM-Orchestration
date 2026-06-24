"""CrewAI task assembly + kickoff: run one agent on one task and capture the output.

The agents themselves (personas, LLM tiering) are defined the idiomatic CrewAI way in
`maads.crew_base` (`@CrewBase MaadsCrew`, driven by `config/agents.yaml`). This module
is the per-call seam: `build_task_description` fetches the substep's agent via
`crew_base.agent_for` and renders the task description from the `config/tasks.yaml`
scaffolds; `_kickoff` wraps that agent+task in a one-agent `Crew` and kicks it off,
folding token usage into `state.token_spend`. The agent *wrappers* in `agents.py` call
`run_json_task(...)` / `run_text_task(...)`; the deterministic orchestrator drives the
cycle.

Model selection — CrewAI best practice: one dedicated ``LLM`` per ``Agent`` at
construction time (see ``agent_for``). Resolution order:

    1. ``MODEL_<AGENT>`` per-role override (e.g. ``MODEL_DEVELOPER``)
    2. ``MODEL_CODE`` / ``OPENAI_MODEL_CODE`` for code-authoring roles
    3. ``MODEL_JSON`` for structured-JSON roles (Ollama path)
    4. ``MODEL`` default (Ollama) or OpenAI tiering (``agents.yaml`` tier field)
"""
from __future__ import annotations

import json
import os
import re
from contextvars import ContextVar
from pathlib import Path

from crewai import Agent, Crew, Task

from maads.crew_base import agent_for, build_llm, reset_llm_caches, resolve_model_for_agent
from maads.prompts import (
    AGENT_TASK_TEMPLATES,
    STATE_ONLY_TASK_TEMPLATE,
    TASK_TEMPLATE,
)
from maads.state import SUBSTEP_NAMES, CrispDMState

__all__ = [
    "build_llm",
    "make_agent",
    "resolve_model_for_agent",
    "reset_llm_caches",
    "build_task_description",
    "pop_last_kickoff_output",
    "run_json_task",
    "run_text_task",
    "CrewKickoffError",
]

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


def make_agent(agent_name: str, dataset_name: str = "") -> Agent:
    """Back-compat shim — agents are now built by ``maads.crew_base.agent_for``."""
    return agent_for(agent_name, dataset_name)


def _strip_markdown_wrappers(text: str) -> str:
    """Remove common LLM wrappers: fences, horizontal rules, leading/trailing noise."""
    text = text.strip()
    fence = re.match(
        r"^```(?:json|JSON)?\s*\n?(.*?)\n?```\s*$",
        text,
        re.DOTALL,
    )
    if fence:
        text = fence.group(1).strip()
    else:
        text = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    lines = [
        ln
        for ln in text.splitlines()
        if not re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", ln)
    ]
    return "\n".join(lines).strip()


def _find_balanced_json(text: str) -> str | None:
    """Extract the first top-level ``{...}`` object with balanced braces."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _repair_json(text: str) -> str:
    """Fix common LLM JSON mistakes (e.g. trailing commas)."""
    return re.sub(r",(\s*[}\]])", r"\1", text)


def _try_parse_json(text: str) -> dict | None:
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_json(text: str) -> dict | None:
    """Parse JSON, cleaning up common LLM formatting before retrying."""
    if not text or not str(text).strip():
        return None

    stripped = _strip_markdown_wrappers(str(text))
    candidates: list[str] = []
    for candidate in (str(text).strip(), stripped):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        for body in (candidate, _repair_json(candidate)):
            parsed = _try_parse_json(body)
            if parsed is not None:
                return parsed

    for candidate in candidates:
        fragment = _find_balanced_json(candidate)
        if not fragment:
            continue
        for body in (fragment, _repair_json(fragment)):
            parsed = _try_parse_json(body)
            if parsed is not None:
                return parsed

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
    agent = agent_for(agent_name, dataset_name)
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


def _resolve_llm_provider(agent_name: str) -> str:
    """Infer provider label for token accounting."""
    model = resolve_model_for_agent(agent_name)
    if model.startswith("ollama/"):
        return "ollama"
    if "deepseek" in model.lower():
        return "deepseek"
    if os.getenv("OPENAI_API_KEY") or model.startswith("gpt-"):
        return "openai"
    return "other"


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
            provider = _resolve_llm_provider(agent_name)
            state.add_tokens(agent_name, total_tokens, provider=provider)
    except (AttributeError, TypeError, ValueError):
        pass
    _check_token_budget(state)
    return raw_output


def run_json_task(
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    schema_hint: str = "",
    *,
    artifact_dir: Path | None = None,
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
        if artifact_dir is not None:
            from maads.debug import debug_json_parse

            outcome = debug_json_parse(
                state=state,
                artifact_dir=artifact_dir,
                requesting_agent=agent_name,
                raw_text=raw_output,
                schema_hint=schema_hint,
                instruction=instruction,
            )
            if outcome.status == "FIXED" and outcome.payload is not None:
                return outcome.payload
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
