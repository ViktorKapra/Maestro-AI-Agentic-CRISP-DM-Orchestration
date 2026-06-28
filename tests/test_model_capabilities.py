"""Tests for startup model JSON capability probing."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from maads.crew_base import reset_llm_caches, structured_outputs_enabled
from maads.model_capabilities import (
    JsonFormatMode,
    ModelJsonCapabilities,
    ensure_model_capabilities_probed,
    get_model_capabilities,
    probe_model,
    reset_model_capabilities_cache,
)


@pytest.fixture(autouse=True)
def _isolate_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAADS_SKIP_MODEL_PROBE", "1")
    reset_model_capabilities_cache()
    reset_llm_caches()
    yield
    reset_model_capabilities_cache()
    reset_llm_caches()


def test_model_capabilities_mode_priority() -> None:
    caps = ModelJsonCapabilities("gpt-test", structured_outputs=True, json_mode=True)
    assert caps.mode == JsonFormatMode.STRUCTURED_OUTPUTS

    caps_json = ModelJsonCapabilities("gpt-test", structured_outputs=False, json_mode=True)
    assert caps_json.mode == JsonFormatMode.JSON_MODE

    caps_none = ModelJsonCapabilities("gpt-test", structured_outputs=False, json_mode=False)
    assert caps_none.mode == JsonFormatMode.NONE


def test_probe_openai_prefers_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAADS_SKIP_MODEL_PROBE", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"ok": true}'))]
    )
    monkeypatch.setattr(
        "maads.model_capabilities._probe_openai_compatible",
        lambda model: ModelJsonCapabilities(model, True, True),
    )
    caps = probe_model("gpt-5.4-mini")
    assert caps.structured_outputs is True
    assert caps.mode == JsonFormatMode.STRUCTURED_OUTPUTS


def test_probe_openai_json_mode_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAADS_SKIP_MODEL_PROBE", raising=False)

    def fake_probe(model: str) -> ModelJsonCapabilities:
        return ModelJsonCapabilities(model, False, True)

    monkeypatch.setattr("maads.model_capabilities.probe_model", fake_probe)
    reset_model_capabilities_cache()
    caps = get_model_capabilities("gpt-4-turbo")
    assert caps.mode == JsonFormatMode.JSON_MODE


def test_json_response_format_uses_probe_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAADS_STRUCTURED_OUTPUTS", "auto")
    monkeypatch.setenv("MODEL", "gpt-5.4-mini")

    def fake_caps(model: str) -> ModelJsonCapabilities:
        return ModelJsonCapabilities(model, True, True)

    monkeypatch.setattr("maads.model_capabilities.get_model_capabilities", fake_caps)
    assert structured_outputs_enabled("pm", "gpt-5.4-mini") is True

    monkeypatch.setattr(
        "maads.model_capabilities.get_model_capabilities",
        lambda model: ModelJsonCapabilities(model, False, True),
    )
    assert structured_outputs_enabled("pm", "gpt-5.4-mini") is False


def test_json_response_format_force_overrides_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAADS_STRUCTURED_OUTPUTS", "force")
    monkeypatch.setattr(
        "maads.model_capabilities.get_model_capabilities",
        lambda model: ModelJsonCapabilities(model, False, False),
    )
    assert structured_outputs_enabled("pm", "gpt-old") is True


def test_ensure_model_capabilities_probed_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAADS_SKIP_MODEL_PROBE", "1")
    monkeypatch.setenv("MODEL", "ollama/gemma2:9b")
    reset_model_capabilities_cache()
    caps = ensure_model_capabilities_probed()
    assert caps
    assert all(c.mode == JsonFormatMode.NONE for c in caps.values())
