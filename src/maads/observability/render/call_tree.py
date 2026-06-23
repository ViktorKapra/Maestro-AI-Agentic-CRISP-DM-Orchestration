"""Render ASCII call tree from trace events."""
from __future__ import annotations

from collections import defaultdict

from maads.observability.schema import TraceEvent, TraceRun


def _children_map(events: list[TraceEvent]) -> dict[str | None, list[TraceEvent]]:
    children: dict[str | None, list[TraceEvent]] = defaultdict(list)
    for evt in events:
        children[evt.parent_id].append(evt)
    return children


def _render_node(evt: TraceEvent, children: dict[str | None, list[TraceEvent]], prefix: str, is_last: bool) -> list[str]:
    branch = "└─ " if is_last else "├─ "
    label = f"{evt.type}"
    if evt.name:
        label += f" {evt.name}"
    lines = [f"{prefix}{branch}{label}"]
    child_prefix = prefix + ("   " if is_last else "│  ")
    kids = children.get(evt.id, [])
    for i, child in enumerate(kids):
        lines.extend(_render_node(child, children, child_prefix, i == len(kids) - 1))
    return lines


def render_call_tree(run: TraceRun) -> str:
    children = _children_map(run.events)
    roots = children[None]
    lines = ["run (maads)", f"case_id={run.case_id or 'n/a'}"]
    for i, root in enumerate(roots):
        lines.extend(_render_node(root, children, "", i == len(roots) - 1))
    return "\n".join(lines) + "\n"
