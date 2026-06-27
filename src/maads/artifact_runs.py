"""Per-run artifact directories with archival of previous executions.

Layout under ``artifacts/<case_id>/``::

    current                    # text file naming the active run id
    runs/<run_id>/             # one directory per ``maads run`` invocation
    archive/<run_id>/          # superseded runs (and legacy flat layouts)

Each execution writes only into its own ``runs/<run_id>/`` tree. Runs accumulate
under ``runs/`` so several executions of the same case can run concurrently
without disturbing one another; starting a new run only relocates any legacy
flat artifacts that lived directly under the case folder and repoints ``current``
at the newly started run.

``current`` is a plain text pointer (not a filesystem symlink): nothing
navigates through it as a directory, so a one-line run id is enough and avoids
the OS-specific symlink/junction privileges Windows would otherwise require.
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

_PRESERVE_NAMES = frozenset({"archive", "runs", "current"})


def case_root(artifact_root: Path, case_id: str) -> Path:
    return Path(artifact_root) / case_id


def resolve_active_run_dir(case_root_path: Path) -> Path | None:
    """Return the directory for the live or most recent run of a case."""
    case_root_path = Path(case_root_path)
    target = _current_target(case_root_path)
    if target is not None and target.is_dir():
        return target

    if (case_root_path / "status.json").is_file():
        return case_root_path

    runs_dir = case_root_path / "runs"
    if runs_dir.is_dir():
        candidates = sorted(
            (p for p in runs_dir.iterdir() if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for candidate in candidates:
            if (candidate / "status.json").is_file():
                return candidate
        if candidates:
            return candidates[0]
    return None


def prepare_run_dir(case_root_path: Path, run_id: str) -> Path:
    """Archive prior output and return a fresh run directory for this execution."""
    case_root_path = Path(case_root_path)
    case_root_path.mkdir(parents=True, exist_ok=True)

    archive_dir = case_root_path / "archive"
    archive_dir.mkdir(exist_ok=True)
    runs_dir = case_root_path / "runs"
    runs_dir.mkdir(exist_ok=True)

    if _has_legacy_artifacts(case_root_path):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = archive_dir / f"legacy_{stamp}"
        _relocate_children(case_root_path, dest, preserve=_PRESERVE_NAMES)

    # Note: prior runs are deliberately NOT archived here. Several runs of the
    # same case may execute concurrently, so moving a previous run dir (which a
    # live process may still be writing) would corrupt it.
    run_dir = runs_dir / run_id
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    _write_current(case_root_path, run_id)
    return run_dir


def _current_target(case_root_path: Path) -> Path | None:
    """Return the run directory named by the ``current`` pointer, or ``None``.

    Reads ``current`` as text. Legacy symlinks/junctions from older runs fail
    the text read and are ignored — ``resolve_active_run_dir`` falls back to
    scanning ``runs/`` by mtime, and the next run rewrites the pointer.
    """
    try:
        run_id = (case_root_path / "current").read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return case_root_path / "runs" / run_id if run_id else None


def _write_current(case_root_path: Path, run_id: str) -> None:
    """Point ``current`` at ``runs/<run_id>``, replacing any prior pointer."""
    pointer = case_root_path / "current"
    if pointer.is_symlink() or pointer.exists():
        try:
            pointer.unlink()
        except (IsADirectoryError, PermissionError, OSError):
            pointer.rmdir()  # legacy directory junction; removes the link only
    pointer.write_text(run_id, encoding="utf-8")


def _has_legacy_artifacts(case_root_path: Path) -> bool:
    if (case_root_path / "status.json").is_file():
        return True
    if (case_root_path / "trace" / "trace.json").is_file():
        return True
    sandbox = case_root_path / "sandbox"
    return sandbox.is_dir() and any(sandbox.iterdir())


def _relocate_children(src: Path, dest: Path, *, preserve: frozenset[str]) -> None:
    dest.mkdir(parents=True, exist_ok=False)
    for child in list(src.iterdir()):
        if child.name in preserve:
            continue
        shutil.move(str(child), str(dest / child.name))
