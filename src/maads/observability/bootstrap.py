"""Bootstrap Runtime Execution Intelligence."""
from __future__ import annotations

import atexit
import os
from pathlib import Path

from maads.observability import context as ctx
from maads.observability.collector import get_collector, reset_collector
from maads.observability.crewai_listener import register_crewai_listener
from maads.observability.exporter import export_trace
from maads.observability.otel import setup_otel
from maads.observability.patches import apply_patches

_enabled = False
_patched = False


def is_enabled() -> bool:
    return os.getenv("MAADS_TRACE", "1").lower() not in {"0", "false", "no", "off"}


def auto_enable() -> None:
    """Install tracing hooks once per process (no-op when MAADS_TRACE=0)."""
    global _enabled, _patched
    if not is_enabled():
        return
    if _patched:
        return

    reset_collector()
    register_crewai_listener()
    setup_otel()
    apply_patches()
    _patched = True
    _enabled = True

    atexit.register(_flush_on_exit)


def begin_run(case_id: str | None, artifact_dir: Path) -> None:
    if not is_enabled():
        return
    coll = get_collector()
    coll.start_run(case_id)
    ctx.current_case_id.set(case_id)
    ctx.export_dir.set(artifact_dir / "trace")


def end_run(artifact_dir: Path) -> Path | None:
    if not is_enabled():
        return None
    trace_dir = artifact_dir / "trace"
    ctx.export_dir.set(trace_dir)
    path = export_trace(get_collector(), trace_dir)
    print(f"Trace artefacts written to {trace_dir}")
    return path


def _flush_on_exit() -> None:
    export_path = ctx.export_dir.get()
    if export_path is None:
        return
    coll = get_collector()
    if coll.run is None or coll.run.ended_at is not None:
        return
    try:
        export_trace(coll, export_path)
    except OSError:
        pass
