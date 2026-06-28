"""Tests for provider model metadata fetching."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from maads.model_capabilities import ModelJsonCapabilities, reset_model_capabilities_cache
from maads.model_info import fetch_model_info, resolve_default_model


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAADS_SKIP_MODEL_PROBE", "1")
    reset_model_capabilities_cache()
    yield
    reset_model_capabilities_cache()


def test_resolve_default_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL", "ollama/gemma2:9b")
    assert resolve_default_model() == "ollama/gemma2:9b"


def test_fetch_model_info_empty_without_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MODEL", raising=False)
    payload = fetch_model_info("")
    assert payload["available"] is False
    assert "No model configured" in (payload["error"] or "")


def test_fetch_ollama_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL", "ollama/test:7b")

    show = MagicMock()
    show.model_dump.return_value = {
        "modified_at": "2026-01-01T00:00:00",
        "details": {
            "family": "llama",
            "parameter_size": "7B",
            "quantization_level": "Q4_0",
            "format": "gguf",
        },
        "capabilities": ["completion", "tools"],
        "parameters": "num_ctx 8192",
        "modelinfo": {
            "general.architecture": "llama",
            "general.parameter_count": 7000000000,
            "llama.context_length": 8192,
        },
    }
    list_entry = MagicMock()
    list_entry.model = "test:7b"
    list_entry.model_dump.return_value = {
        "model": "test:7b",
        "size": 4_000_000_000,
        "modified_at": "2026-01-01T00:00:00",
    }
    listed = MagicMock()
    listed.models = [list_entry]

    client = MagicMock()
    client.show.return_value = show
    client.list.return_value = listed
    monkeypatch.setattr("ollama.Client", lambda **_: client)

    payload = fetch_model_info("ollama/test:7b")
    assert payload["provider"] == "ollama"
    assert payload["available"] is True
    assert payload["details"]["family"] == "llama"
    assert payload["details"]["context_length"] == 8192
    assert payload["details"]["size_bytes"] == 4_000_000_000
    assert payload["details"]["capabilities"] == ["completion", "tools"]


def test_fetch_openai_info(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    retrieved = MagicMock()
    retrieved.model_dump.return_value = {
        "id": "gpt-4o-mini",
        "created": 1721172741,
        "object": "model",
        "owned_by": "system",
    }
    listed_model = MagicMock()
    listed_model.id = "gpt-4o-mini"
    list_resp = MagicMock()
    list_resp.data = [listed_model]

    client = MagicMock()
    client.models.retrieve.return_value = retrieved
    client.models.list.return_value = list_resp
    monkeypatch.setattr("openai.OpenAI", lambda: client)

    payload = fetch_model_info("gpt-4o-mini")
    assert payload["provider"] == "openai"
    assert payload["available"] is True
    assert payload["details"]["owned_by"] == "system"
    assert payload["details"]["listed_in_account"] is True


def test_fetch_openai_missing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    payload = fetch_model_info("gpt-4o-mini")
    assert payload["available"] is False
    assert "OPENAI_API_KEY" in (payload["error"] or "")


def test_fetch_model_info_includes_cached_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    from maads import model_capabilities as mc

    mc._capabilities_cache = {
        "gpt-test": ModelJsonCapabilities("gpt-test", True, True),
    }
    payload = fetch_model_info("gpt-test")
    assert payload["json_capabilities"] == {
        "mode": "structured_outputs",
        "structured_outputs": True,
        "json_mode": True,
    }


def test_api_model_info_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from maads.dashboard.server import create_app

    monkeypatch.setattr(
        "maads.model_info.fetch_model_info",
        lambda model, probe=False: {
            "model": model or "ollama/gemma2:9b",
            "provider": "ollama",
            "available": True,
            "error": None,
            "details": {"family": "gemma2"},
            "json_capabilities": None,
        },
    )
    monkeypatch.setattr(
        "maads.model_catalog.model_label",
        lambda mid: "Gemma 2 9B" if "gemma2" in mid else None,
    )

    client = TestClient(create_app())
    resp = client.get("/api/models/info", params={"model": "ollama/gemma2:9b"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "ollama/gemma2:9b"
    assert body["label"] == "Gemma 2 9B"
    assert body["details"]["family"] == "gemma2"
