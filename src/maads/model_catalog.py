"""Curated catalog of selectable models for the dashboard Launch UI.

Constants only — no ``maads`` imports — so this module can be safely imported
from the dashboard API without risking import cycles. The lists are grouped by
provider and surfaced via ``GET /api/models``; each entry is a ``{"id", "label"}``
pair where ``id`` is the value fed to the ``MODEL`` env for a run.

Ollama cloud model tags come from ollama.com/search?c=cloud and may change over
time; keep this list as the single place to update.
"""

from __future__ import annotations

# Ollama Cloud models (run on Ollama's servers; require `ollama signin` or
# OLLAMA_API_KEY). Use the ``ollama/`` LiteLLM prefix that crew_base expects.
# Only free-tier tags are listed here — subscription-gated models (glm-5*,
# deepseek-v4*, kimi-*) return 403 without a paid Ollama plan, so they are
# omitted. Verified runnable via POST /api/generate on the free tier.
OLLAMA_CLOUD_MODELS: list[dict[str, str]] = [
    {"id": "ollama/gpt-oss:120b-cloud", "label": "gpt-oss 120b (cloud)"},
    {"id": "ollama/gpt-oss:20b-cloud", "label": "gpt-oss 20b (cloud)"},
    {"id": "ollama/qwen3-coder:480b-cloud", "label": "Qwen3 Coder 480b (cloud)"},
    {"id": "ollama/minimax-m3:cloud", "label": "MiniMax M3 (cloud)"},
]

# OpenAI / ChatGPT API models (require OPENAI_API_KEY). Current as of 2026-06;
# IDs from https://developers.openai.com/api/docs/models/all
OPENAI_MODELS: list[dict[str, str]] = [
    {"id": "gpt-5.5", "label": "GPT-5.5 (flagship)"},
    {"id": "gpt-5.5-pro", "label": "GPT-5.5 Pro"},
    {"id": "gpt-5.4", "label": "GPT-5.4"},
    {"id": "gpt-5.4-mini", "label": "GPT-5.4 mini"},
    {"id": "gpt-5.4-nano", "label": "GPT-5.4 nano (cheapest)"},
]


def model_catalog() -> dict[str, list[dict[str, str]]]:
    """Return the selectable models grouped by provider."""
    return {
        "ollama_cloud": list(OLLAMA_CLOUD_MODELS),
        "openai": list(OPENAI_MODELS),
    }


def model_label(model_id: str) -> str | None:
    """Return the curated display label for ``model_id``, if known."""
    for group in model_catalog().values():
        for entry in group:
            if entry["id"] == model_id:
                return entry["label"]
    return None
