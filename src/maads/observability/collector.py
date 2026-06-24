"""Central trace event collector."""
from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from maads.observability.context import current_event_id, current_run_id
from maads.observability.schema import TraceEvent, TraceRun

_counter = 0
_counter_lock = threading.Lock()


def _next_event_id() -> str:
    global _counter
    with _counter_lock:
        _counter += 1
        n = _counter
    return f"evt_{n:04d}"


class TraceCollector:
    """Thread-safe append-only event log for a single pipeline run."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._run: TraceRun | None = None
        self._t0_mono = time.monotonic()
        self._open_spans: dict[str, tuple[float, TraceEvent]] = {}
        self._span_parents: dict[str, str | None] = {}
        self._otel_span_map: dict[int, str] = {}

    @property
    def run(self) -> TraceRun | None:
        return self._run

    def start_run(self, case_id: str | None = None, *, run_id: str | None = None) -> str:
        run_id = run_id or str(uuid.uuid4())
        with self._lock:
            self._t0_mono = time.monotonic()
            self._run = TraceRun(run_id=run_id, case_id=case_id)
        current_run_id.set(run_id)
        return run_id

    def end_run(self) -> None:
        with self._lock:
            if self._run is not None:
                self._run.ended_at = datetime.now(timezone.utc)

    def emit(
        self,
        event_type: str,
        *,
        name: str = "",
        source: str = "maads",
        parent_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        span_key: str | None = None,
    ) -> str:
        if self._run is None:
            return ""

        evt_id = _next_event_id()
        parent = parent_id if parent_id is not None else current_event_id.get()

        evt = TraceEvent(
            id=evt_id,
            parent_id=parent,
            ts_mono_ms=round((time.monotonic() - self._t0_mono) * 1000, 2),
            duration_ms=duration_ms,
            type=event_type,
            source=source,
            name=name,
            attributes=dict(attributes or {}),
            thread_id=threading.get_ident(),
        )
        with self._lock:
            self._run.events.append(evt)
        if span_key:
            self._open_spans[span_key] = (time.monotonic(), evt)
        return evt_id

    def emit_start(self, event_type: str, *, span_key: str, **kwargs: Any) -> str:
        evt_id = self.emit(event_type, **kwargs)
        # Store the parent explicitly — ContextVar reset tokens are invalid across
        # asyncio/thread boundaries (CrewAI event bus), but .set() always works.
        self._span_parents[span_key] = current_event_id.get()
        current_event_id.set(evt_id)
        with self._lock:
            if self._run is not None:
                for e in reversed(self._run.events):
                    if e.id == evt_id:
                        self._open_spans[span_key] = (time.monotonic(), e)
                        break
        return evt_id

    def emit_end(
        self,
        event_type: str,
        *,
        span_key: str,
        attributes: dict[str, Any] | None = None,
    ) -> str | None:
        start_info = self._open_spans.pop(span_key, None)
        duration_ms = None
        parent_id = None
        attrs = dict(attributes or {})
        if start_info:
            t0, start_evt = start_info
            duration_ms = round((time.monotonic() - t0) * 1000, 2)
            parent_id = start_evt.parent_id
            for key in ("agent_name", "maads_agent", "role", "substep"):
                if attrs.get(key) is None and start_evt.attributes.get(key) is not None:
                    attrs[key] = start_evt.attributes[key]
        if span_key in self._span_parents:
            current_event_id.set(self._span_parents.pop(span_key))
        if duration_ms is not None:
            attrs.setdefault("duration_ms", duration_ms)
        return self.emit(
            event_type,
            parent_id=parent_id,
            attributes=attrs,
            duration_ms=duration_ms,
        )

    def register_otel_span(self, span_id: int, evt_id: str) -> None:
        with self._lock:
            self._otel_span_map[span_id] = evt_id

    def otel_parent_id(self, parent_span_id: int | None) -> str | None:
        if parent_span_id is None:
            return current_event_id.get()
        with self._lock:
            return self._otel_span_map.get(parent_span_id)

    def to_trace_run(self) -> TraceRun:
        with self._lock:
            if self._run is None:
                return TraceRun(run_id="unknown", events=[])
            return self._run.model_copy(deep=True)


_collector: TraceCollector | None = None


def get_collector() -> TraceCollector:
    global _collector
    if _collector is None:
        _collector = TraceCollector()
    return _collector


def reset_collector() -> TraceCollector:
    global _collector
    _collector = TraceCollector()
    return _collector
