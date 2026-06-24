"""Per-run artifact directories with archival of previous executions.

Layout under ``artifacts/<case_id>/``::

    current -> runs/<run_id>   # symlink to the active run
    runs/<run_id>/             # one directory per ``maads run`` invocation
    archive/<run_id>/          # superseded runs (and legacy flat layouts)

Each execution writes only into its own ``runs/<run_id>/`` tree. Starting a new
run moves the previous active run into ``archive/`` and relocates any legacy
flat artifacts that lived directly under the case folder.
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
    current = case_root_path / "current"
    if current.is_symlink() or current.is_file():
        target = current.resolve()
        if target.is_dir() and (target / "status.json").is_file():
            return target
        if target.is_dir():
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

    current_link = case_root_path / "current"
    if current_link.is_symlink() or current_link.is_file():
        prev = current_link.resolve()
        current_link.unlink()
        if prev.is_dir() and prev.parent == runs_dir.resolve():
            shutil.move(str(prev), str(archive_dir / prev.name))

    run_dir = runs_dir / run_id
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    run_dir.mkdir(parents=True)

    current_link.symlink_to(Path("runs") / run_id)
    return run_dir


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
