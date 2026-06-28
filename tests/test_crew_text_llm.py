"""Tests for plain LLM config on codegen text tasks."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from maads.crew_base import build_llm, reset_llm_caches


@pytest.fixture(autouse=True)
def _isolate_llm_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAADS_SKIP_MODEL_PROBE", "1")
    monkeypatch.setenv("MODEL", "gpt-5.5")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    reset_llm_caches()
    yield
    reset_llm_caches()


def test_build_llm_plain_text_omits_response_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "maads.crew_base._json_response_format_for_agent",
        lambda agent_name, model: {"type": "json_object"},
    )
    llm = build_llm("data_scientist", json_enforced=False)
    assert getattr(llm, "response_format", None) is None

    llm_json = build_llm("data_scientist", json_enforced=True)
    assert getattr(llm_json, "response_format", None) == {"type": "json_object"}
