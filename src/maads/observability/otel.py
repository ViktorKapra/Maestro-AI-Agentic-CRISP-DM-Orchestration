"""OpenTelemetry bridge into TraceCollector."""
from __future__ import annotations

import os
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from maads.observability.collector import TraceCollector, get_collector

_instrumented = False


class CollectorSpanProcessor(SpanProcessor):
    """Mirror OTEL spans into the MAADS trace collector."""

    def __init__(self, collector: TraceCollector) -> None:
        self._collector = collector
        self._span_evt: dict[int, str] = {}

    def on_start(self, span: Any, parent_context: Any = None) -> None:  # noqa: ARG002
        ctx = span.get_span_context()
        span_id = ctx.span_id
        parent_span_id = None
        if span.parent is not None:
            parent_span_id = span.parent.span_id
        parent_evt = self._collector.otel_parent_id(parent_span_id)
        name = getattr(span, "name", "span")
        attrs = dict(getattr(span, "attributes", None) or {})
        evt_id = self._collector.emit(
            "otel.span.start",
            name=name,
            source="opentelemetry",
            parent_id=parent_evt,
            attributes={
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(span_id, "016x"),
                **{str(k): v for k, v in attrs.items()},
            },
        )
        self._span_evt[span_id] = evt_id
        self._collector.register_otel_span(span_id, evt_id)

    def on_end(self, span: ReadableSpan) -> None:
        ctx = span.get_span_context()
        span_id = ctx.span_id
        parent_evt = self._span_evt.pop(span_id, None)
        attrs = dict(span.attributes or {})
        duration_ms = None
        if span.end_time and span.start_time:
            duration_ms = (span.end_time - span.start_time) / 1_000_000
        self._collector.emit(
            "otel.span.end",
            name=span.name,
            source="opentelemetry",
            parent_id=parent_evt,
            duration_ms=duration_ms,
            attributes={
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(span_id, "016x"),
                "status": str(getattr(span.status, "status_code", "")),
                **{str(k): v for k, v in attrs.items()},
            },
        )

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:  # noqa: ARG002
        return True


def setup_otel(collector: TraceCollector | None = None) -> TracerProvider:
    global _instrumented
    coll = collector or get_collector()
    resource = Resource.create({"service.name": "maads"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(CollectorSpanProcessor(coll))

    if os.getenv("MAADS_TRACE_OTEL_CONSOLE", "").lower() in {"1", "true", "yes"}:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)

    if not _instrumented:
        try:
            from openinference.instrumentation.crewai import CrewAIInstrumentor

            CrewAIInstrumentor().instrument(
                tracer_provider=provider,
                use_event_listener=True,
            )
        except Exception:
            # openinference may require a newer crewai; MaadsCrewAIListener still captures events.
            pass
        _instrumented = True

    return provider
