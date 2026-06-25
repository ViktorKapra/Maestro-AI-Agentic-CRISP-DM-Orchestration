"""Trace hooks for CrispDMFlow steps."""
from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from maads.observability import context as ctx
from maads.observability.collector import get_collector
from maads.observability.python_tracer import PythonTracer
from maads.run_status import flush_status
from maads.state import SUBSTEP_NAMES, SUBSTEP_OWNER

F = TypeVar("F", bound=Callable[..., Any])


def _flush_trace_snapshot() -> None:
    out = ctx.export_dir.get()
    if out is None:
        flush_status()
        return
    coll = get_collector()
    if coll.run is None:
        flush_status()
        return
    from maads.observability.exporter import write_trace_artifacts

    write_trace_artifacts(coll, out, finalize=False)
    flush_status()


def trace_flow_method(name: str) -> Callable[[F], F]:
    """Decorator for CrispDMFlow methods — emit trace + flush status."""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(self, *args: Any, **kwargs: Any):
            coll = get_collector()
            coll.emit_start(
                "flow.step",
                span_key=f"flow.{name}",
                name=name,
                source="maads.flow.crisp_dm_flow",
                attributes={
                    "case_id": self.state.case_id,
                    "phase": int(self.state.phase),
                    "substep": self.state.substep,
                },
            )
            try:
                result = fn(self, *args, **kwargs)
                coll.emit_end(
                    "flow.step",
                    span_key=f"flow.{name}",
                    attributes={"route": result},
                )
                _flush_trace_snapshot()
                return result
            except Exception as exc:
                coll.emit(
                    "exception",
                    name=type(exc).__name__,
                    source="maads.flow.crisp_dm_flow",
                    attributes={"message": str(exc), "step": name},
                )
                raise

        return wrapper  # type: ignore[return-value]

    return decorator


def trace_substep_dispatch(state, substep: str) -> None:
    coll = get_collector()
    owner = SUBSTEP_OWNER.get(substep, "?")
    ctx.current_substep.set(substep)
    ctx.current_maads_agent.set(owner)
    coll.emit_start(
        "substep.dispatch",
        span_key=f"substep.{substep}",
        name=SUBSTEP_NAMES.get(substep, substep),
        source="maads.flow.crisp_dm_flow",
        attributes={"substep": substep, "owner": owner, "phase": int(state.phase)},
    )


def trace_substep_end(substep: str) -> None:
    from maads.run_status import record_substep_done

    coll = get_collector()
    coll.emit_end("substep.end", span_key=f"substep.{substep}", attributes={"substep": substep})
    record_substep_done(substep)
    ctx.current_substep.set(None)
    ctx.current_maads_agent.set(None)


def trace_loop(label: str, from_phase: int, to_phase: int, reason: str) -> None:
    coll = get_collector()
    coll.emit(
        "loop",
        name=f"loop {label}",
        source="maads.flow.crisp_dm_flow",
        attributes={
            "label": label,
            "from_phase": from_phase,
            "to_phase": to_phase,
            "reason": reason,
        },
    )


def install_flow_run_tracer() -> PythonTracer:
    coll = get_collector()
    tracer = PythonTracer(coll)
    ctx.trace_active.set(True)
    ctx.python_trace_active.set(True)
    tracer.install()
    return tracer
