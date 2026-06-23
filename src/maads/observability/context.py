"""contextvars for correlating trace events across threads."""
from __future__ import annotations

import contextvars
from pathlib import Path

current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "maads_trace_run_id", default=None
)
current_event_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "maads_trace_event_id", default=None
)
current_substep: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "maads_trace_substep", default=None
)
current_maads_agent: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "maads_trace_maads_agent", default=None
)
current_case_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "maads_trace_case_id", default=None
)
trace_active: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "maads_trace_active", default=False
)
python_trace_active: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "maads_python_trace_active", default=False
)
export_dir: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "maads_trace_export_dir", default=None
)
