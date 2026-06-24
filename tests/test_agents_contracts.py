"""Contract validation for agent-authored execution payloads."""
from __future__ import annotations

import json

import pytest

from maads.capabilities.shared import describe_data_contract as _describe_data_contract
from maads.codegen import run_authored_code
from maads.config import load_case_config
from maads.paths import resolve_path
from maads.state import CrispDMState
from maads.tools import PythonExec


@pytest.fixture
def state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


@pytest.fixture
def pyexec(tmp_path) -> PythonExec:
    return PythonExec(workdir=tmp_path / "sandbox")


def test_describe_data_contract_rejects_parallel_lists():
    """Regression: LLM emitted list missing/dtypes; only key presence was checked."""
    payload = json.loads(
        '{"n_rows": 7613, "n_cols": 5, '
        '"columns": ["id", "keyword", "location", "text", "target"], '
        '"dtypes": ["int64", "object", "object", "object", "int64"], '
        '"missing": [0, 61, 2533, 0, 0]}'
    )
    errors = _describe_data_contract(payload)
    assert any("missing" in e and "dict" in e for e in errors)
    assert any("dtypes" in e and "dict" in e for e in errors)


def test_describe_data_contract_accepts_column_maps():
    payload = {
        "n_rows": 891,
        "n_cols": 12,
        "columns": ["Age", "Fare"],
        "dtypes": {"Age": "float64", "Fare": "float64"},
        "missing": {"Age": 177, "Fare": 0},
    }
    assert _describe_data_contract(payload) == []


def test_describe_contract_violation_triggers_fallback(monkeypatch, pyexec, state):
    bad = (
        '```python\nimport json\nprint(json.dumps({"n_rows": 1, "n_cols": 1, '
        '"columns": ["a"], "dtypes": ["int64"], "missing": [0]}))\n```'
    )
    replies = iter([bad])
    last = {"v": bad}

    def fake(*_a, **_k):
        try:
            last["v"] = next(replies)
        except StopIteration:
            pass
        return last["v"]

    monkeypatch.setattr("maads.codegen.run_text_task", fake)

    good = {
        "n_rows": 1,
        "n_cols": 1,
        "columns": ["a"],
        "dtypes": {"a": "int64"},
        "missing": {"a": 0},
    }
    res = run_authored_code(
        pyexec=pyexec,
        agent_name="data_engineer",
        state=state,
        instruction="describe data",
        header_vars={},
        contract=_describe_data_contract,
        fallback=lambda: good,
        max_retries=1,
    )
    assert res.degraded
    assert res.payload == good
    assert isinstance(res.payload["missing"], dict)
