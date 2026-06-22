"""Tools agents may call.

`PythonExec` and `FileIO` are working. `RAGRetriever` is a stub the team builds.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ────────────────────────────────────────────────────────────────────────────
# PythonExec — the sandbox every agent uses to actually run pandas / sklearn.
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class ExecResult:
    ok: bool
    stdout: str
    stderr: str
    return_code: int
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "timed_out": self.timed_out,
        }


class PythonExec:
    """Run Python code in a subprocess, capture stdout/stderr/return code.

    This is intentionally simple. It is NOT a security sandbox — the
    execution environment is trusted. It enforces a wall-clock
    timeout to stop runaway agent code.
    """

    def __init__(self, workdir: Path, timeout_seconds: int = 90) -> None:
        self.workdir = Path(workdir).resolve()
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds

    def run(self, code: str, extra_env: dict[str, str] | None = None) -> ExecResult:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".py", dir=self.workdir, delete=False
        ) as fh:
            fh.write(code)
            script_path = fh.name

        try:
            proc = subprocess.run(
                [sys.executable, script_path],
                cwd=self.workdir,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env=self._make_env(extra_env),
            )
            return ExecResult(
                ok=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
                return_code=proc.returncode,
            )
        except subprocess.TimeoutExpired as e:
            return ExecResult(
                ok=False,
                stdout=(e.stdout or "") if isinstance(e.stdout, str) else "",
                stderr=f"Timed out after {self.timeout_seconds} seconds.",
                return_code=-1,
                timed_out=True,
            )
        finally:
            try:
                Path(script_path).unlink()
            except OSError:
                pass

    def _make_env(self, extra: dict[str, str] | None) -> dict[str, str]:
        import os
        env = os.environ.copy()
        if extra:
            env.update(extra)
        return env


# ────────────────────────────────────────────────────────────────────────────
# FileIO — read/write helpers under a per-run artifact directory.
# ────────────────────────────────────────────────────────────────────────────

class FileIO:
    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = Path(artifact_dir).resolve()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)

    def write_json(self, name: str, data: Any) -> Path:
        path = self.artifact_dir / name
        path.write_text(json.dumps(data, indent=2, default=str))
        return path

    def write_text(self, name: str, content: str) -> Path:
        path = self.artifact_dir / name
        path.write_text(content)
        return path

    def copy_in(self, src: Path) -> Path:
        dst = self.artifact_dir / Path(src).name
        shutil.copy2(src, dst)
        return dst

    def path_for(self, name: str) -> Path:
        return self.artifact_dir / name


# ────────────────────────────────────────────────────────────────────────────
# RAGRetriever — STUB. The team implements this.
# ────────────────────────────────────────────────────────────────────────────

class RAGRetriever:
    """Stub. Implement a small RAG corpus for the Domain Expert agent.

    Suggested approach:
        - Sources: CRISP-DM spec excerpt, per-case domain notes, Abhishek
          Thakur's "Approaching (Almost) Any ML Problem" chapter excerpts.
        - Chunk into ~200-token pieces.
        - Embed with OpenAI's text-embedding-3-small (cheap).
        - Index in a FAISS flat index or hand-rolled cosine sim over a numpy
          array.

    Keep it under ~100 lines of code. This is not where you spend time.
    """

    def __init__(self, corpus_dir: Path) -> None:
        self.corpus_dir = Path(corpus_dir)
        # TODO: build / load the index.

    def retrieve(self, query: str, k: int = 4) -> list[str]:
        """Return the top-k passages for the query. Currently returns []."""
        # TODO: implement.
        return []
