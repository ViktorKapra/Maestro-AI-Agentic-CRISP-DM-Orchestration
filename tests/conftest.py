"""Pytest configuration and shared fixtures for the maads test suite."""
from __future__ import annotations

import pytest

from maads.paths import repo_root


@pytest.fixture(scope="session")
def project_root():
    """Repository root (directory containing ``pyproject.toml``)."""
    return repo_root()
