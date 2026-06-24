"""Tests for execution tools (PythonExec script retention)."""
from __future__ import annotations

import json
from pathlib import Path

from maads.tools import PythonExec


def test_python_exec_keeps_scripts_and_io(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    pyexec = PythonExec(workdir=sandbox)

    res = pyexec.run('print("hello")', label="smoke")
    assert res.ok
    assert res.script_path is not None
    assert res.script_path.exists()
    assert res.script_path.read_text(encoding="utf-8") == 'print("hello")'

    stdout_path = res.script_path.with_suffix(".stdout.txt")
    stderr_path = res.script_path.with_suffix(".stderr.txt")
    assert stdout_path.read_text(encoding="utf-8") == "hello\n"
    assert stderr_path.read_text(encoding="utf-8") == ""

    manifest = sandbox / "exec" / "manifest.jsonl"
    lines = manifest.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["label"] == "smoke"
    assert record["ok"] is True
    assert record["script"] == res.script_path.name


def test_python_exec_keeps_failed_runs(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    pyexec = PythonExec(workdir=sandbox)

    res = pyexec.run("raise RuntimeError('boom')", label="fail")
    assert not res.ok
    assert res.script_path is not None
    assert res.script_path.exists()
    assert "boom" in res.script_path.with_suffix(".stderr.txt").read_text(encoding="utf-8")


def test_python_exec_can_delete_when_disabled(tmp_path: Path):
    sandbox = tmp_path / "sandbox"
    pyexec = PythonExec(workdir=sandbox, keep_scripts=False)

    res = pyexec.run('print("ephemeral")')
    assert res.ok
    assert res.script_path is None
    assert not list(sandbox.rglob("*.py"))


def test_rag_retriever_finds_passages(tmp_path: Path):
    from maads.tools import RAGRetriever

    corpus = tmp_path / "knowledge"
    corpus.mkdir()
    (corpus / "a.md").write_text("Titanic survival prediction uses passenger features.")
    rag = RAGRetriever(corpus)
    hits = rag.retrieve("Titanic survival", k=2)
    assert hits and "Titanic" in hits[0]
