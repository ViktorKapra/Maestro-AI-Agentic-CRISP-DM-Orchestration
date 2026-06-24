"""Run agent-authored Python with validation, self-debug retry, and fallback.

The owning agent's LLM proposes Python code; `PythonExec` runs it; the code must
print a single JSON line matching a *contract*. On failure (crash, timeout, or a
contract violation) we feed the captured stderr back to the agent for a revision
(self-debug) up to a retry budget, then fall back to a fixed baseline snippet so
a single bad generation never kills the whole run.

This is the seam that turns the agents from narrators into doers: the parquet /
model / submission they describe is the parquet / model / submission their own
code actually produced. The fixed snippets in `agents.py` survive only as the
last-resort fallback — and a fallback is itself a signal (degraded run) that the
PM can treat as grounds for a Loop B.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable

from maads.crew import CrewKickoffError, run_text_task
from maads.state import CrispDMState
from maads.tools import PythonExec

MAX_CODE_RETRIES = 3

# A contract validates the JSON the authored code printed: returns a list of
# human-readable errors (empty list == the payload satisfies the contract).
Contract = Callable[[dict], list[str]]


@dataclass
class CodeResult:
    payload: dict[str, Any]          # contract-valid JSON the code printed
    code: str                        # the code that produced it (authored or fallback)
    attempts: int                    # how many authoring attempts were made
    degraded: bool = False           # True when we fell back to the fixed snippet
    error: str | None = None         # last failure reason (when degraded)

    @property
    def ok(self) -> bool:
        return not self.degraded


def _extract_code(text: str) -> str | None:
    """Pull a Python block out of LLM output (fenced ``` or raw)."""
    if not text or not text.strip():
        return None
    m = re.search(r"```(?:python|py)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip() or None
    return text.strip()


def _header(header_vars: dict[str, Any]) -> str:
    """Render predefined variables the authored code may use, safely quoted."""
    lines = ["# --- injected by maads; do not redefine ---"]
    for name, value in header_vars.items():
        lines.append(f"{name} = {value!r}")
    return "\n".join(lines) + "\n"


def _last_json_line(stdout: str) -> dict | None:
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _build_instruction(
    base: str,
    header_vars: dict[str, Any],
    contract_hint: str,
    prior_code: str | None,
    prior_error: str | None,
) -> str:
    var_list = ", ".join(header_vars.keys())
    parts = [
        base,
        "",
        "Write Python 3 code to accomplish the task above.",
        f"These variables are ALREADY DEFINED for you (do not redefine): {var_list}.",
        "Your code MUST finish by printing exactly one line to stdout: a single "
        f"JSON object. {contract_hint}",
        "Return ONLY a ```python ...``` code block — no prose before or after.",
    ]
    if prior_code and prior_error:
        parts += [
            "",
            "Your previous attempt FAILED. Fix it. Previous code:",
            "```python",
            prior_code,
            "```",
            f"Error / reason it failed:\n{prior_error}",
        ]
    return "\n".join(parts)


def run_authored_code(
    *,
    pyexec: PythonExec,
    agent_name: str,
    instruction: str,
    state: CrispDMState,
    header_vars: dict[str, Any],
    contract: Contract,
    contract_hint: str = "",
    fallback: Callable[[], dict] | None = None,
    fallback_code: str = "<fixed baseline snippet>",
    max_retries: int = MAX_CODE_RETRIES,
) -> CodeResult:
    """Have `agent_name` author Python, run it, validate, self-debug, then fall back.

    `header_vars` are injected as predefined variables before the agent's code.
    `contract` validates the JSON the code prints. `fallback` (if given) runs the
    fixed baseline when all authoring attempts fail.
    """
    header = _header(header_vars)
    prior_code: str | None = None
    prior_error: str | None = None

    for attempt in range(1, max_retries + 1):
        def warn(outcome: str) -> None:
            state.append_log(
                agent_name, f"authored code attempt {attempt} -> {outcome}", level="warn"
            )

        prompt = _build_instruction(
            instruction, header_vars, contract_hint, prior_code, prior_error
        )
        try:
            raw = run_text_task(agent_name, prompt, state, expected_output="A Python code block.")
        except (CrewKickoffError, RuntimeError) as exc:
            prior_error = f"LLM call failed: {exc}"
            warn("LLM error")
            continue

        code = _extract_code(raw)
        if not code:
            prior_error = "no Python code block found in the response"
            warn("no code")
            continue

        full_code = header + code
        res = pyexec.run(full_code)
        if not res.ok:
            prior_code = code
            prior_error = (res.stderr or "").strip()[-1500:] or "non-zero exit, no stderr"
            warn("failed")
            continue

        payload = _last_json_line(res.stdout)
        if payload is None:
            prior_code = code
            prior_error = "code ran but printed no JSON object on its last line"
            warn("no JSON output")
            continue

        errors = contract(payload)
        if errors:
            prior_code = code
            prior_error = "output failed validation: " + "; ".join(errors)
            warn("invalid output")
            continue

        state.append_log(agent_name, f"authored code attempt {attempt} -> ok")
        return CodeResult(payload=payload, code=full_code, attempts=attempt)

    # All authoring attempts failed -> fall back (degraded).
    if fallback is not None:
        state.append_log(
            agent_name,
            f"authored code exhausted {max_retries} attempts; using fallback. "
            f"last error: {(prior_error or '')[:300]}",
            level="warn",
        )
        payload = fallback()
        return CodeResult(
            payload=payload,
            code=fallback_code,
            attempts=max_retries,
            degraded=True,
            error=prior_error,
        )

    raise CrewKickoffError(
        f"{agent_name} authored code failed after {max_retries} attempts "
        f"and no fallback was provided: {prior_error}"
    )
