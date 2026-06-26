"""Pytest configuration and shared fixtures for the maads test suite."""
from __future__ import annotations

import pytest

from maads.paths import repo_root
from tests.fixtures.titanic_exec import fake_run_text_task


@pytest.fixture(scope="session")
def project_root():
    """Repository root (directory containing ``pyproject.toml``)."""
    return repo_root()


@pytest.fixture(autouse=True)
def stub_de_ds_codegen(monkeypatch: pytest.MonkeyPatch):
    """Provide titanic-oriented authored code for DE/DS integration tests."""
    monkeypatch.setattr("maads.crew.run_text_task", fake_run_text_task)
