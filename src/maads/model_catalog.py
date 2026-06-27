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
OLLAMA_CLOUD_MODELS: list[dict[str, str]] = [
    {"id": "ollama/gpt-oss:120b-cloud", "label": "gpt-oss 120b (cloud)"},
    {"id": "ollama/gpt-oss:20b-cloud", "label": "gpt-oss 20b (cloud)"},
    {"id": "ollama/qwen3-coder:480b-cloud", "label": "Qwen3 Coder 480b (cloud)"},
    {"id": "ollama/deepseek-v4-flash:cloud", "label": "DeepSeek V4 Flash (cloud)"},
    {"id": "ollama/deepseek-v4-pro:cloud", "label": "DeepSeek V4 Pro (cloud)"},
    {"id": "ollama/glm-5:cloud", "label": "GLM-5 (cloud)"},
    {"id": "ollama/glm-5.2:cloud", "label": "GLM-5.2 (cloud)"},
    {"id": "ollama/minimax-m3:cloud", "label": "MiniMax M3 (cloud)"},
    {"id": "ollama/kimi-k2.7-code:cloud", "label": "Kimi K2.7 Code (cloud)"},
    {"id": "ollama/qwen3.5:122b-cloud", "label": "Qwen3.5 122b (cloud)"},
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
