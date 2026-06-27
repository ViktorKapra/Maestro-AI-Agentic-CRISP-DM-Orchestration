"""Tests for the agent code-authoring executor (codegen.run_authored_code)."""
from __future__ import annotations

from pathlib import Path

import pytest

from maads.codegen import _extract_code, run_authored_code
from maads.config import load_case_config
from maads.paths import resolve_path
from maads.state import CrispDMState
from maads.tools import PythonExec


@pytest.fixture
def state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


@pytest.fixture
def pyexec(tmp_path: Path) -> PythonExec:
    return PythonExec(workdir=tmp_path / "sandbox")


def _patch_llm(monkeypatch, replies):
    """Make run_text_task return queued replies (then the last one forever)."""
    it = iter(replies)
    last = {"v": replies[-1]}

    def fake(*_a, **_k):
        try:
            last["v"] = next(it)
        except StopIteration:
            pass
        return last["v"]

    monkeypatch.setattr("maads.crew.run_text_task", fake)


def test_extract_code_handles_fences_and_raw():
    assert _extract_code("```python\nprint(1)\n```") == "print(1)"
    assert _extract_code("```\nprint(2)\n```") == "print(2)"
    assert _extract_code("print(3)") == "print(3)"
    assert _extract_code("   ") is None


def test_extract_code_unwraps_json_object():
    """gpt-class models sometimes return {"code": "...\\n..."} instead of a fence."""
    raw = '{"code": "import json\\nprint(json.dumps({\\"ok\\": True}))"}'
    code = _extract_code(raw)
    assert code == 'import json\nprint(json.dumps({"ok": True}))'
    compile(code, "<t>", "exec")  # real newlines, not literal \n


def test_extract_code_unwraps_json_string():
    raw = '"import os\\nprint(os.getcwd())"'
    assert _extract_code(raw) == "import os\nprint(os.getcwd())"


def test_extract_code_unwraps_json_inside_fence():
    raw = '```json\n{"code": "x = 1\\nprint(x)"}\n```'
    assert _extract_code(raw) == "x = 1\nprint(x)"


def test_extract_code_decodes_escaped_newlines_in_fence():
    """Code escaped inside a fence (literal backslash-n) is decoded if it helps."""
    raw = "```python\\nimport json\\nprint(1)\\n```"
    code = _extract_code(raw)
    assert code is not None
    assert "\\n" not in code
    compile(code, "<t>", "exec")


def test_extract_code_prefers_normal_python():
    """A normal, already-compilable snippet is returned untouched (no JSON guess)."""
    src = "import json\ndata = {'a': 1}\nprint(json.dumps(data))"
    assert _extract_code(src) == src


def test_authored_code_recovers_from_json_wrapped_response(monkeypatch, pyexec, state):
    """End-to-end: a JSON-wrapped code response still runs and satisfies the contract."""
    _patch_llm(monkeypatch, [
        '{"code": "import json\\nprint(json.dumps({\\"n\\": N + 1}))"}',
    ])
    res = run_authored_code(
        pyexec=pyexec, agent_name="data_scientist", state=state,
        instruction="add one to N",
        header_vars={"N": 41},
        contract=lambda p: [] if p.get("n") == 42 else ["wrong n"],
        max_retries=1,
    )
    assert res.ok and res.payload == {"n": 42}


def test_authored_code_success(monkeypatch, pyexec, state):
    _patch_llm(monkeypatch, ['```python\nimport json\nprint(json.dumps({"n": N + 1}))\n```'])
    res = run_authored_code(
        pyexec=pyexec, agent_name="data_engineer", state=state,
        instruction="add one to N",
        header_vars={"N": 41},
        contract=lambda p: [] if p.get("n") == 42 else ["wrong n"],
    )
    assert res.ok and not res.degraded
    assert res.payload == {"n": 42}
    assert res.attempts == 1
    assert "N = 41" in res.code  # header injected


def test_authored_code_retries_then_succeeds(monkeypatch, pyexec, state):
    _patch_llm(monkeypatch, [
        "```python\nraise ValueError('boom')\n```",          # attempt 1: crashes
        "```python\nprint('not json')\n```",                  # attempt 2: no JSON
        '```python\nimport json\nprint(json.dumps({"ok": True}))\n```',  # attempt 3: good
    ])
    res = run_authored_code(
        pyexec=pyexec, agent_name="data_scientist", state=state,
        instruction="print ok",
        header_vars={},
        contract=lambda p: [] if p.get("ok") else ["missing ok"],
    )
    assert res.ok and res.attempts == 3
    assert res.payload == {"ok": True}


def test_authored_code_falls_back_when_exhausted(monkeypatch, pyexec, state):
    _patch_llm(monkeypatch, ["no code block here"])  # never yields code
    res = run_authored_code(
        pyexec=pyexec, agent_name="data_engineer", state=state,
        instruction="whatever",
        header_vars={},
        contract=lambda p: [],
        fallback=lambda: {"from": "fallback"},
        fallback_code="<baseline>",
        max_retries=2,
    )
    assert res.degraded and not res.ok
    assert res.payload == {"from": "fallback"}
    assert res.code == "<baseline>"
    assert res.error  # last failure recorded


def test_contract_violation_triggers_fallback(monkeypatch, pyexec, state):
    # Code runs fine but prints the wrong shape -> contract fails -> fallback.
    _patch_llm(monkeypatch, ['```python\nimport json\nprint(json.dumps({"bad": 1}))\n```'])
    res = run_authored_code(
        pyexec=pyexec, agent_name="data_engineer", state=state,
        instruction="produce good",
        header_vars={},
        contract=lambda p: [] if "good" in p else ["missing good"],
        fallback=lambda: {"good": True},
        max_retries=1,
    )
    assert res.degraded
    assert res.payload == {"good": True}


def test_header_injects_stdlib_imports(monkeypatch, pyexec, state, tmp_path: Path):
    """Authored code may omit import json; preamble supplies it."""
    from maads.codegen import _header

    header = _header({})
    assert "import json" in header
    assert "import pandas as pd" in header

    _patch_llm(
        monkeypatch,
        ['```python\nprint(json.dumps({"ok": True}))\n```'],
    )
    res = run_authored_code(
        pyexec=pyexec, agent_name="data_engineer", state=state,
        instruction="test",
        header_vars={},
        contract=lambda p: [] if p.get("ok") else ["fail"],
        max_retries=1,
        artifact_dir=tmp_path,
    )
    assert res.ok
