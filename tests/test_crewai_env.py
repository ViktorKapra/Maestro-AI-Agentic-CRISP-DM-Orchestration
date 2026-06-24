"""Tests for CrewAI runtime env tuning."""
from __future__ import annotations

import os

from maads.observability.bootstrap import configure_crewai_runtime


def test_disables_crewai_cloud_tracing_by_default(monkeypatch):
    monkeypatch.setenv("CREWAI_TRACING_ENABLED", "true")
    monkeypatch.delenv("MAADS_CREWAI_CLOUD_TRACING", raising=False)
    configure_crewai_runtime()
    assert os.environ["CREWAI_TRACING_ENABLED"] == "false"


def test_cloud_tracing_opt_in(monkeypatch):
    monkeypatch.setenv("CREWAI_TRACING_ENABLED", "true")
    monkeypatch.setenv("MAADS_CREWAI_CLOUD_TRACING", "1")
    configure_crewai_runtime()
    assert os.environ["CREWAI_TRACING_ENABLED"] == "true"
