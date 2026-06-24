"""Shared filesystem paths for phase crews (CrewAI ``@CrewBase`` config resolution)."""
from __future__ import annotations

from pathlib import Path

# Canonical agent personas — single source of truth in ``maads/config/agents.yaml``.
AGENTS_CONFIG = str(Path(__file__).resolve().parent.parent / "config" / "agents.yaml")
