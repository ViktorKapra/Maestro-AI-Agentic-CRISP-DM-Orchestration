"""Bootstrap Runtime Execution Intelligence."""
from __future__ import annotations

import atexit
import os
from pathlib import Path

from maads.observability import context as ctx
from maads.observability.collector import get_collector, reset_collector
from maads.observability.crewai_listener import register_crewai_listener
from maads.observability.exporter import export_trace, write_trace_artifacts
from maads.observability.llm_communications import reset_communication_registry
from maads.observability.otel import setup_otel
from maads.observability.patches import apply_patches

_enabled = False
_patched = False


def is_enabled() -> bool:
    return os.getenv("MAADS_TRACE", "1").lower() not in {"0", "false", "no", "off"}


def configure_crewai_runtime() -> None:
    """Tune CrewAI env before any crew imports run.

    MAADS persists traces under ``artifacts/<case>/runs/<run_id>/trace/`` via
    ``MAADS_TRACE``. CrewAI's optional cloud tracing (``CREWAI_TRACING_ENABLED``)
    uploads to app.crewai.com and fails offline or without a linked project
    (404 EphemeralTraceBatch). Disable it unless explicitly opted in.
    """
    if os.getenv("MAADS_CREWAI_CLOUD_TRACING", "").lower() not in {
        "1", "true", "yes", "on",
    }:
        os.environ["CREWAI_TRACING_ENABLED"] = "false"
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")


def auto_enable() -> None:
    """Install tracing hooks once per process (no-op when MAADS_TRACE=0)."""
    global _enabled, _patched
    if not is_enabled():
        return
    if _patched:
        return

    reset_collector()
    reset_communication_registry()
    register_crewai_listener()
    setup_otel()
    apply_patches()
    _patched = True
    _enabled = True

    atexit.register(_flush_on_exit)


def begin_run(
    case_id: str | None,
    artifact_dir: Path,
    *,
    run_id: str | None = None,
) -> str:
    if not is_enabled():
        return run_id or ""
    coll = get_collector()
    run_id = coll.start_run(case_id, run_id=run_id)
    ctx.current_case_id.set(case_id)
    trace_dir = artifact_dir / "trace"
    ctx.export_dir.set(trace_dir)
    flush_trace(trace_dir)
    return run_id


def flush_trace(trace_dir: Path | None = None) -> Path | None:
    """Persist the in-memory trace without closing the run (live updates)."""
    if not is_enabled():
        return None
    out = trace_dir or ctx.export_dir.get()
    if out is None:
        return None
    coll = get_collector()
    if coll.run is None:
        return None
    return write_trace_artifacts(coll, out, finalize=False)


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
