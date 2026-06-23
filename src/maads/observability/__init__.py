"""Runtime Execution Intelligence for MAADS."""
from __future__ import annotations

from maads.observability.bootstrap import auto_enable, begin_run, end_run, flush_trace, is_enabled
from maads.observability.collector import get_collector, reset_collector
from maads.observability.exporter import export_trace, write_trace_artifacts

__all__ = [
    "auto_enable",
    "begin_run",
    "end_run",
    "export_trace",
    "flush_trace",
    "get_collector",
    "is_enabled",
    "reset_collector",
    "write_trace_artifacts",
]
