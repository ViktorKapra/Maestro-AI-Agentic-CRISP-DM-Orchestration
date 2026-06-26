"""Run agent-authored Python with validation, self-debug retry, and optional fallback.

The owning agent's LLM proposes Python code; `PythonExec` runs it; the code must
print a single JSON line matching a *contract*. On failure (crash, timeout, or a
contract violation) we feed the captured stderr back to the agent for a revision
(self-debug) up to a retry budget. DE/DS/Developer execution substeps have no
baseline fallback — a failed generation surfaces as a halt the PM can respond to.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import maads.crew as crew
from maads.state import CrispDMState
from maads.tools import ExecResult, PythonExec

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
    lines = [
        "# --- injected by maads; do not redefine ---",
        "import json",
        "from pathlib import Path",
        "import pandas as pd",
    ]
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
        "DATASET_INSPECT_JSON is a JSON string from inspect_dataset — parse with json.loads if needed.",
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
    artifact_dir: Path | None = None,
) -> CodeResult:
    """Have `agent_name` author Python, run it, validate, self-debug, then fall back.

    `header_vars` are injected as predefined variables before the agent's code.
    `contract` validates the JSON the code prints. `fallback` (if given) runs the
    fixed baseline when all authoring attempts fail.
    """
    header = _header(header_vars)
    prior_code: str | None = None
    prior_error: str | None = None
    last_exec: ExecResult | None = None

    for attempt in range(1, max_retries + 1):
        prompt = _build_instruction(
            instruction, header_vars, contract_hint, prior_code, prior_error
        )
        try:
            raw = crew.run_text_task(agent_name, prompt, state, expected_output="A Python code block.")
        except (crew.CrewKickoffError, RuntimeError) as exc:
            prior_error = f"LLM call failed: {exc}"
            state.append_log(agent_name, f"authored code attempt {attempt} -> LLM error", level="warn")
            continue

        code = _extract_code(raw)
        if not code:
            prior_error = "no Python code block found in the response"
            state.append_log(agent_name, f"authored code attempt {attempt} -> no code", level="warn")
            continue

        full_code = header + code
        res = pyexec.run(full_code, label=f"{agent_name}_attempt{attempt}")
        last_exec = res
        if not res.ok:
            prior_code = code
            prior_error = (res.stderr or "").strip()[-1500:] or "non-zero exit, no stderr"
            state.append_log(agent_name, f"authored code attempt {attempt} -> failed", level="warn")
            continue

        payload = _last_json_line(res.stdout)
        if payload is None:
            prior_code = code
            prior_error = "code ran but printed no JSON object on its last line"
            state.append_log(agent_name, f"authored code attempt {attempt} -> no JSON output", level="warn")
            continue

        errors = contract(payload)
        if errors:
            prior_code = code
            prior_error = "output failed validation: " + "; ".join(errors)
            state.append_log(agent_name, f"authored code attempt {attempt} -> invalid output", level="warn")
            continue

        state.append_log(agent_name, f"authored code attempt {attempt} -> ok")
        return CodeResult(payload=payload, code=full_code, attempts=attempt)

    # Specialist retries exhausted — route to Developer DEBUG before baseline fallback.
    if prior_code and artifact_dir is not None:
        from maads.debug import debug_python_exec

        debug_out = debug_python_exec(
            pyexec=pyexec,
            state=state,
            artifact_dir=artifact_dir,
            requesting_agent=agent_name,
            failing_code=prior_code,
            header_vars=header_vars,
            contract=contract,
            contract_hint=contract_hint,
            last_error=prior_error or "",
            last_exec=last_exec,
        )
        if debug_out.status == "FIXED" and debug_out.payload is not None:
            return CodeResult(
                payload=debug_out.payload,
                code=debug_out.code or header + prior_code,
                attempts=max_retries + len(debug_out.fix_attempts),
                degraded=False,
            )

    # DEBUG stuck or unavailable -> fall back (degraded).
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

    raise crew.CrewKickoffError(
        f"{agent_name} authored code failed after {max_retries} attempts "
        f"and no fallback was provided: {prior_error}"
    )
