"""Render timeline.md from trace events."""
from __future__ import annotations

from maads.observability.schema import TraceRun

_TIMELINE_TYPES = frozenset({
    "run.start", "run.end", "phase.transition", "substep.dispatch", "substep.end",
    "agent.activate", "agent.complete", "crew.start", "crew.end",
    "task.start", "task.end", "tool.start", "tool.end",
    "llm.start", "llm.end", "python.subprocess", "flow.start", "flow.end",
    "branch", "loop", "exception",
})


def render_timeline(run: TraceRun) -> str:
    lines = [
        "# Execution Timeline",
        "",
        f"Run: `{run.run_id}` | Case: `{run.case_id or 'n/a'}`",
        "",
    ]
    for evt in run.events:
        if evt.type not in _TIMELINE_TYPES:
            continue
        label = evt.name or evt.type
        dur = f" ({evt.duration_ms}ms)" if evt.duration_ms is not None else ""
        attrs = evt.attributes
        extra = ""
        if evt.type == "substep.dispatch":
            sub = attrs.get("substep", "")
            extra = f" [{sub}] → {attrs.get('owner', '?')}" if sub else f" → {attrs.get('owner', '?')}"
        elif evt.type in {"llm.end", "crew.end"} and attrs.get("total_tokens"):
            extra = f" tokens={attrs['total_tokens']}"
        comm = attrs.get("communication_id")
        if comm and evt.type in {"llm.start", "llm.end", "crew.start", "crew.end"}:
            extra += f" {comm}"
        if evt.type == "llm.end":
            pc = attrs.get("prompt_chars")
            rc = attrs.get("response_chars")
            if pc or rc:
                extra += f" {pc or '?'}→{rc or '?'} chars"
        elif evt.type == "python.subprocess":
            extra = f" rc={attrs.get('return_code', '?')}"
        lines.append(f"T+{evt.ts_mono_ms:>7.0f}ms  {evt.type:<22} {label}{extra}{dur}")
    return "\n".join(lines) + "\n"
