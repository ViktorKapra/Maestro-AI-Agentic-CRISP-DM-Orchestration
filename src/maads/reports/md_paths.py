"""Relative paths and markdown links for report files."""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path


def run_meta_md(
    case_id: str | None, model: str | None, run_id: str | None,
) -> str:
    """A one-line metadata banner placed at the top of each report so it's
    clear which dataset and LLM model produced it."""
    return (
        f"> **Dataset:** `{case_id or '?'}`  ·  "
        f"**LLM model:** `{model or 'default (.env)'}`  ·  "
        f"**Run ID:** `{run_id or '?'}`\n\n"
    )


def resolve_artifact_path(path: str | Path | None, run_dir: Path) -> Path | None:
    if not path:
        return None
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    return (run_dir / p).resolve()


def relative_md_path(
    path: str | Path | None,
    *,
    md_dir: Path,
    run_dir: Path,
    remap: Callable[[Path], Path] | None = None,
) -> str | None:
    """Return a POSIX path relative to the markdown file directory."""
    resolved = resolve_artifact_path(path, run_dir)
    if resolved is None:
        return None
    target = remap(resolved) if remap else resolved
    md_resolved = md_dir.resolve()
    try:
        rel = os.path.relpath(target, md_resolved)
    except ValueError:
        return target.as_posix()
    return Path(rel).as_posix()


def md_file_link(
    path: str | Path | None,
    *,
    md_dir: Path,
    run_dir: Path,
    label: str | None = None,
    remap: Callable[[Path], Path] | None = None,
) -> str | None:
    rel = relative_md_path(path, md_dir=md_dir, run_dir=run_dir, remap=remap)
    if not rel:
        return None
    text = label or Path(rel).name
    return f"[{text}]({rel})"


def handoff_path_remap(resolved: Path, run_dir: Path, handoff_root: Path) -> Path:
    """Map a run artifact path to its location inside a Standard handoff bundle."""
    try:
        rel = resolved.relative_to(run_dir.resolve())
    except ValueError:
        return handoff_root / resolved.name

    if rel == Path("final_report.md"):
        return handoff_root / "reports" / "final_report.md"
    if rel.name in {"submission.csv", "train.parquet", "test.parquet"}:
        return handoff_root / "artifacts" / rel.name
    if rel.parts and rel.parts[0] == "figures":
        return handoff_root / "artifacts" / rel
    if rel.parts and rel.parts[0] == "reports":
        return handoff_root / rel
    return handoff_root / rel


def handoff_remap_factory(run_dir: Path, handoff_root: Path) -> Callable[[Path], Path]:
    def _remap(resolved: Path) -> Path:
        return handoff_path_remap(resolved, run_dir, handoff_root)

    return _remap
