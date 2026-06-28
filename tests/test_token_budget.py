"""Tests for centralized token budget guards."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from maads.codegen import run_authored_code
from maads.config import load_case_config
from maads.crew import run_json_task
from maads.flow.phase_runner import RunContext, run_phase_substeps
from maads.paths import resolve_path
from maads.state import CrispDMState, Phase
from maads.token_budget import (
    HALT_REASON,
    TokenBudgetExceeded,
    assert_can_spend,
    budget_status,
    build_spending_summary,
    check_after_spend,
    clear_caches,
    code_retries,
    debug_retries,
    repairs_allowed,
    soft_limit_reached,
)
from maads.tools import PythonExec


@pytest.fixture(autouse=True)
def _clear_token_budget_caches():
    clear_caches()
    yield
    clear_caches()


@pytest.fixture
def titanic_state() -> CrispDMState:
    cfg = load_case_config(resolve_path("configs/titanic.yaml"))
    return CrispDMState.from_config(cfg)


def test_run_cap_raises_when_exceeded(titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "100")
    titanic_state.token_spend["pm"] = 100
    with pytest.raises(TokenBudgetExceeded, match="Run-wide token cap"):
        assert_can_spend(titanic_state, "pm")


def test_per_agent_cap_blocks_only_that_agent(
    titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_TOKENS_PER_AGENT", "pm:50")
    titanic_state.token_spend["pm"] = 50
    with pytest.raises(TokenBudgetExceeded, match="Per-agent token cap"):
        assert_can_spend(titanic_state, "pm")
    assert_can_spend(titanic_state, "domain")


def test_check_after_spend_matches_assert(
    titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "200")
    titanic_state.token_spend["pm"] = 200
    with pytest.raises(TokenBudgetExceeded):
        check_after_spend(titanic_state, "pm")


def test_soft_limit_reached_at_pct(titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "1000")
    monkeypatch.setenv("TOKEN_BUDGET_SOFT_PCT", "90")
    titanic_state.token_spend["pm"] = 899
    assert soft_limit_reached(titanic_state) is False
    titanic_state.token_spend["pm"] = 900
    assert soft_limit_reached(titanic_state) is True
    assert repairs_allowed(titanic_state) is False


def test_code_retries_soft_uses_one(titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAX_CODE_RETRIES", "3")
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "100")
    monkeypatch.setenv("TOKEN_BUDGET_SOFT_PCT", "90")
    titanic_state.token_spend["data_engineer"] = 90
    assert code_retries(soft=True) == 1
    assert code_retries(soft=False) == 3


def test_debug_retries_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAX_DEBUG_RETRIES", "2")
    assert debug_retries() == 2


def test_budget_status_serializes(titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "1000")
    monkeypatch.setenv("MAX_TOKENS_PER_AGENT", "pm:100")
    titanic_state.token_spend["pm"] = 40
    status = budget_status(titanic_state)
    assert status["cap"] == 1000
    assert status["spent"] == 40
    assert status["remaining"] == 960
    assert status["pct"] == 4.0
    assert status["per_agent"]["pm"]["cap"] == 100


def test_build_spending_summary_orders_agents(
    titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "1000")
    titanic_state.token_spend = {"pm": 100, "developer": 300}
    summary = build_spending_summary(titanic_state)
    assert summary["top_agent"] == "developer"
    assert summary["by_agent"][0]["agent"] == "developer"


@patch("maads.crew.Crew")
def test_kickoff_pre_call_guard_skips_llm(
    mock_crew_cls, titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "100")
    titanic_state.token_spend["pm"] = 100
    with pytest.raises(TokenBudgetExceeded):
        run_json_task("pm", "plan", titanic_state)
    mock_crew_cls.assert_not_called()


@patch("maads.crew.run_text_task")
def test_codegen_does_not_retry_on_budget_exceeded(
    mock_run_text, titanic_state: CrispDMState, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "100")
    titanic_state.token_spend["data_engineer"] = 100
    mock_run_text.side_effect = TokenBudgetExceeded("cap reached")
    pyexec = MagicMock(spec=PythonExec)
    with pytest.raises(TokenBudgetExceeded):
        run_authored_code(
            pyexec=pyexec,
            agent_name="data_engineer",
            instruction="describe data",
            state=titanic_state,
            header_vars={},
            contract=lambda _p: [],
            max_retries=3,
        )
    assert mock_run_text.call_count == 1


def test_run_phase_substeps_halts_on_budget_exception(
    titanic_state: CrispDMState, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "100")
    titanic_state.phase = Phase.BUSINESS_UNDERSTANDING
    titanic_state.substep = "1.2"
    titanic_state.token_spend["domain"] = 100

    class DomainAgent:
        def act(self, state: CrispDMState):
            raise TokenBudgetExceeded("cap")

    ctx = RunContext.create(
        state=titanic_state,
        artifact_dir=tmp_path,
        agents={"domain": DomainAgent(), "pm": MagicMock()},
        pm=MagicMock(),
    )
    route = run_phase_substeps(ctx, Phase.BUSINESS_UNDERSTANDING)
    assert route == "halt"
    assert titanic_state.halt_reason == HALT_REASON


def test_cli_max_tokens_sets_env(monkeypatch: pytest.MonkeyPatch):
    import argparse
    import os

    from maads.__main__ import cmd_run

    captured: dict[str, str | None] = {}

    def _stop_after_env(_path):
        captured["env"] = os.environ.get("MAX_TOKENS_PER_RUN")
        raise RuntimeError("stop test")

    monkeypatch.setenv("MAX_TOKENS_PER_RUN", "")
    monkeypatch.setattr("maads.__main__.ensure_embedding_model_available", lambda: None)
    monkeypatch.setattr("maads.__main__.load_case_config", _stop_after_env)
    args = argparse.Namespace(
        config=None,
        case="titanic",
        config_dir="configs",
        artifact_dir="artifacts",
        quiet=True,
        model=None,
        max_tokens=500000,
    )
    with pytest.raises(RuntimeError, match="stop test"):
        cmd_run(args)
    assert captured["env"] == "500000"
