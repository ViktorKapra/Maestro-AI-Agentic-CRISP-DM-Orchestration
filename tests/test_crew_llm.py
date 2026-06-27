"""Tests for per-agent LLM model resolution."""

from __future__ import annotations

import pytest

from maads.crew import build_llm, make_agent, reset_llm_caches, resolve_model_for_agent


@pytest.fixture(autouse=True)
def _clear_llm_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate env and bust lru_cache between tests."""
    for name in (
        "MODEL",
        "MODEL_CODE",
        "MODEL_JSON",
        "MODEL_DEVELOPER",
        "MODEL_DATA_ENGINEER",
        "OPENAI_MODEL_TOP",
        "OPENAI_MODEL_MID",
        "OPENAI_MODEL_CODE",
        "MAADS_SKIP_MODEL_PROBE",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("MAADS_SKIP_MODEL_PROBE", "1")
    reset_llm_caches()
    yield
    reset_llm_caches()


def test_ollama_single_model_backward_compatible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL", "ollama/gemma4:12b")
    assert resolve_model_for_agent("pm") == "ollama/gemma4:12b"
    assert resolve_model_for_agent("developer") == "ollama/gemma4:12b"
    assert resolve_model_for_agent("data_engineer") == "ollama/gemma4:12b"


def test_ollama_code_and_json_tiers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL", "ollama/gemma4:12b")
    monkeypatch.setenv("MODEL_CODE", "ollama/qwen2.5-coder:14b")
    monkeypatch.setenv("MODEL_JSON", "ollama/gemma4:12b")
    assert resolve_model_for_agent("pm") == "ollama/gemma4:12b"
    assert resolve_model_for_agent("domain") == "ollama/gemma4:12b"
    assert resolve_model_for_agent("developer") == "ollama/qwen2.5-coder:14b"
    assert resolve_model_for_agent("data_engineer") == "ollama/qwen2.5-coder:14b"
    assert resolve_model_for_agent("data_scientist") == "ollama/qwen2.5-coder:14b"


def test_per_agent_override_beats_tier(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL", "ollama/gemma4:12b")
    monkeypatch.setenv("MODEL_CODE", "ollama/qwen2.5-coder:14b")
    monkeypatch.setenv("MODEL_DEVELOPER", "ollama/qwen2.5-coder:7b")
    assert resolve_model_for_agent("developer") == "ollama/qwen2.5-coder:7b"
    assert resolve_model_for_agent("data_engineer") == "ollama/qwen2.5-coder:14b"


def test_cloud_openai_tiering_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL_TOP", "gpt-4o")
    monkeypatch.setenv("OPENAI_MODEL_MID", "gpt-4o-mini")
    assert resolve_model_for_agent("pm") == "gpt-4o"
    assert resolve_model_for_agent("data_scientist") == "gpt-4o"
    assert resolve_model_for_agent("developer") == "gpt-4o-mini"
    assert resolve_model_for_agent("domain") == "gpt-4o-mini"


def test_cloud_developer_code_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL_TOP", "gpt-4o")
    monkeypatch.setenv("OPENAI_MODEL_MID", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_MODEL_CODE", "gpt-4o-mini")
    assert resolve_model_for_agent("developer") == "gpt-4o-mini"
    assert resolve_model_for_agent("data_engineer") == "gpt-4o-mini"


def test_each_agent_gets_own_llm_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL", "ollama/gemma4:12b")
    monkeypatch.setenv("MODEL_CODE", "ollama/qwen2.5-coder:14b")
    reset_llm_caches()
    pm_llm = build_llm("pm")
    dev_llm = build_llm("developer")
    assert pm_llm is not dev_llm
    assert resolve_model_for_agent("pm") == "ollama/gemma4:12b"
    assert resolve_model_for_agent("developer") == "ollama/qwen2.5-coder:14b"


def test_make_agent_binds_resolved_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL", "ollama/gemma4:12b")
    monkeypatch.setenv("MODEL_CODE", "ollama/qwen2.5-coder:14b")
    reset_llm_caches()
    agent = make_agent("developer")
    assert agent.llm is build_llm("developer")
    assert resolve_model_for_agent("developer") == "ollama/qwen2.5-coder:14b"
