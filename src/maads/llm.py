"""Thin LLM client.

OpenAI is the primary backend. DeepSeek is an optional cost-effective fallback;
its API is OpenAI-compatible so the same SDK works.

This wrapper exists so agents don't each re-implement retries and token counting.
Keep it small. If you find yourself wanting features (streaming, tools, function
calling), add them here — do not import a heavier library.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import tiktoken
from openai import APIError, OpenAI, RateLimitError


# Cap, enforced in code, on tokens spent in one process.
_RUN_TOTAL_TOKENS = 0


@dataclass
class LLMReply:
    text: str
    input_tokens: int
    output_tokens: int
    model: str

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLM:
    """Provider-agnostic LLM call. Default: OpenAI. Optional: DeepSeek."""

    def __init__(self, provider: str = "openai", model: str | None = None) -> None:
        self.provider = provider
        if provider == "openai":
            self.client = OpenAI()  # picks up OPENAI_API_KEY
            self.model = model or os.environ.get("OPENAI_MODEL_MID", "gpt-4o-mini")
        elif provider == "deepseek":
            key = os.environ.get("DEEPSEEK_API_KEY")
            if not key:
                raise RuntimeError("DEEPSEEK_API_KEY not set")
            self.client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
            self.model = model or "deepseek-chat"
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def chat(
        self,
        system: str,
        user: str,
        *,
        agent_name: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_output_tokens: int = 2000,
    ) -> LLMReply:
        """Make one chat completion. Retries on rate limit / transient errors."""
        self._enforce_run_cap()

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_err: Exception | None = None
        for attempt in range(4):
            try:
                resp = self.client.chat.completions.create(**kwargs)
                break
            except (RateLimitError, APIError) as err:
                last_err = err
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"LLM call failed after retries: {last_err}")

        text = resp.choices[0].message.content or ""
        usage = resp.usage
        reply = LLMReply(
            text=text,
            input_tokens=usage.prompt_tokens if usage else _approx_tokens(system + user),
            output_tokens=usage.completion_tokens if usage else _approx_tokens(text),
            model=self.model,
        )
        self._record_spend(reply.total_tokens)
        return reply

    @staticmethod
    def _enforce_run_cap() -> None:
        cap_str = os.environ.get("MAX_TOKENS_PER_RUN")
        if not cap_str:
            return
        if _RUN_TOTAL_TOKENS >= int(cap_str):
            raise RuntimeError(
                f"Run-wide token cap of {cap_str} reached. Halting to avoid runaway cost."
            )

    @staticmethod
    def _record_spend(n_tokens: int) -> None:
        global _RUN_TOTAL_TOKENS
        _RUN_TOTAL_TOKENS += n_tokens


def _approx_tokens(s: str) -> int:
    """Approximate token count for usage accounting when the API doesn't return it."""
    try:
        return len(tiktoken.get_encoding("cl100k_base").encode(s))
    except Exception:
        return len(s) // 4  # crude fallback


# ── Per-agent default models ────────────────────────────────────────────────
# Override in each agent's __init__ if needed. These are suggestions only.

def llm_for(agent_name: str) -> LLM:
    top = os.environ.get("OPENAI_MODEL_TOP", "gpt-4o")
    mid = os.environ.get("OPENAI_MODEL_MID", "gpt-4o-mini")
    routing = {
        "pm":             ("openai", top),
        "domain":         ("openai", mid),
        "data_engineer":  ("openai", mid),
        "data_scientist": ("openai", top),
        "developer":      ("openai", mid),
        "validator":      ("openai", top),
    }
    provider, model = routing.get(agent_name, ("openai", mid))
    return LLM(provider=provider, model=model)
