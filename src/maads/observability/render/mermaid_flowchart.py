"""Render Mermaid flowchart of substeps."""
from __future__ import annotations

from maads.observability.schema import TraceRun


def _safe_id(substep: str) -> str:
    return "S" + substep.replace(".", "_")


def render_flowchart(run: TraceRun) -> str:
    substeps: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for evt in run.events:
        if evt.type == "substep.dispatch":
            sub = evt.attributes.get("substep", "")
            if sub and sub not in seen:
                seen.add(sub)
                owner = evt.attributes.get("owner", "?")
                name = evt.name or sub
                substeps.append((sub, owner, name))

    lines = ["flowchart TD", "    Start([Start])"]
    if not substeps:
        lines.append("    End([End])")
        lines.append("    Start --> End")
        return "\n".join(lines) + "\n"

    prev = "Start"
    for sub, owner, name in substeps:
        nid = _safe_id(sub)
        label = f"{sub} {name}\\n({owner})"
        lines.append(f'    {nid}["{label}"]')
        lines.append(f"    {prev} --> {nid}")
        prev = nid
    lines.append("    End([End])")
    lines.append(f"    {prev} --> End")
    return "\n".join(lines) + "\n"
