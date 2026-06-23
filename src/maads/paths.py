"""Repository-root path resolution (cwd-independent)."""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT: Path | None = None


def repo_root() -> Path:
    """Return the project root (directory containing ``pyproject.toml``)."""
    global _REPO_ROOT
    if _REPO_ROOT is not None:
        return _REPO_ROOT
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            _REPO_ROOT = parent
            return parent
    _REPO_ROOT = Path(__file__).resolve().parents[2]
    return _REPO_ROOT


def resolve_path(path: str | Path) -> Path:
    """Resolve ``path`` against repo root when relative."""
    p = Path(path)
    if p.is_absolute():
        return p
    return (repo_root() / p).resolve()
