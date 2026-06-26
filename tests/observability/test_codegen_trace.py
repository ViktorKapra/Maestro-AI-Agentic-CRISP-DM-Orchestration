"""Codegen LLM calls must be traced via crew.run_text_task for communications export."""
from __future__ import annotations

import pytest

from maads.observability.patches import apply_patches


@pytest.fixture(autouse=True)
def trace_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MAADS_TRACE", "1")
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")


def test_codegen_run_text_task_traced_after_apply_patches():
    apply_patches()
    import maads.crew as crew_mod

    assert getattr(crew_mod.run_text_task, "_maads_traced", False)
