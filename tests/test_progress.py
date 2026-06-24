"""Tests for live CLI progress."""
from __future__ import annotations

import pytest

from maads.progress import (
    AGENT_LABELS,
    TOTAL_SUBSTEPS,
    format_substep_header,
    is_progress_enabled,
)
from maads.prompts import AGENT_PROMPTS


def test_total_substeps_is_24():
    assert TOTAL_SUBSTEPS == 24


def test_format_substep_header():
    text = format_substep_header("1.1", 1)
    assert "1.1" in text
    assert "Determine Business Objectives" in text
    assert "Business Understanding" in text


def test_agent_labels_cover_roles():
    for agent_id, meta in AGENT_PROMPTS.items():
        assert AGENT_LABELS[agent_id] == meta["role"]


@pytest.mark.parametrize(
    ("env", "quiet", "expected"),
    [
        ("0", False, False),
        ("false", False, False),
        ("1", False, True),
        (None, True, False),
    ],
)
def test_is_progress_enabled(monkeypatch: pytest.MonkeyPatch, env, quiet, expected):
    if env is None:
        monkeypatch.delenv("MAADS_PROGRESS", raising=False)
    else:
        monkeypatch.setenv("MAADS_PROGRESS", env)
    assert is_progress_enabled(quiet=quiet) is expected
