"""Tests for serving run artifacts via the dashboard API."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from maads.artifact_paths import ensure_run_layout
from maads.dashboard.server import create_app

_MIN_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415478da6364a0000000050001a4d4e4d2a000000000049454"
    "44ae426082"
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("MAADS_ARTIFACT_ROOT", str(tmp_path))
    from maads.dashboard import server

    server._artifact_root = tmp_path
    return TestClient(create_app())


def test_get_run_artifact_serves_figure(client: TestClient, tmp_path: Path) -> None:
    run_dir = tmp_path / "titanic" / "runs" / "run-1"
    ensure_run_layout(run_dir, run_id="run-1", case_id="titanic")
    fig = run_dir / "figures" / "plot.png"
    fig.parent.mkdir(parents=True, exist_ok=True)
    fig.write_bytes(_MIN_PNG)

    res = client.get("/api/cases/titanic/artifacts/figures/plot.png?run_id=run-1")
    assert res.status_code == 200
    assert res.content == _MIN_PNG
    assert res.headers["content-type"].startswith("image/png")


def test_get_run_artifact_rejects_path_traversal(client: TestClient, tmp_path: Path) -> None:
    run_dir = tmp_path / "titanic" / "runs" / "run-1"
    ensure_run_layout(run_dir, run_id="run-1", case_id="titanic")

    res = client.get("/api/cases/titanic/artifacts/../status.json?run_id=run-1")
    assert res.status_code == 404
