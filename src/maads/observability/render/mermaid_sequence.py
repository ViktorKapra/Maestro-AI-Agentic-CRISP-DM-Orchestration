"""Render Mermaid sequence diagram."""
from __future__ import annotations

from maads.observability.schema import TraceRun

_KEY_TYPES = {
    "run.start": ("Orch", "run"),
    "substep.dispatch": ("Orch", "dispatch"),
    "agent.activate": ("Agent", "activate"),
    "crew.start": ("Crew", "kickoff"),
    "llm.start": ("LLM", "prompt"),
    "llm.end": ("LLM", "response"),
    "crew.end": ("Crew", "complete"),
    "task.start": ("Task", "start"),
    "task.end": ("Task", "complete"),
    "python.subprocess": ("PythonExec", "run"),
    "agent.complete": ("Agent", "done"),
    "phase.transition": ("Orch", "phase"),
}


def render_sequence(run: TraceRun) -> str:
    lines = [
        "sequenceDiagram",
        "    participant Orch as Orchestrator",
        "    participant Agent as Agent",
        "    participant Crew as CrewAI_Crew",
        "    participant Task as Task",
        "    participant LLM as LLM",
        "    participant PythonExec as PythonExec",
        "",
    ]
    for evt in run.events:
        if evt.type not in _KEY_TYPES and not evt.type.startswith("substep."):
            if evt.type not in {"crew.start", "crew.end", "llm.start", "llm.end",
                                "agent.activate", "agent.complete", "python.subprocess",
                                "substep.dispatch", "phase.transition", "task.start", "task.end"}:
                continue
        mapping = _KEY_TYPES.get(evt.type)
        if not mapping:
            if evt.type == "substep.dispatch":
                sub = evt.attributes.get("substep", "?")
                owner = evt.attributes.get("owner", "agent")
                lines.append(f"    Orch->>Agent: dispatch {sub} ({owner})")
            continue
        src, msg = mapping
        if evt.type == "llm.end":
            lines.append(f"    LLM-->>Crew: {msg}")
        elif evt.type == "crew.end":
            lines.append(f"    Crew-->>Agent: {msg}")
        elif evt.type == "agent.complete":
            lines.append(f"    Agent-->>Orch: {msg}")
        elif evt.type == "python.subprocess":
            lines.append(f"    Agent->>PythonExec: {msg}")
            lines.append(f"    PythonExec-->>Agent: done")
        elif src == "Orch":
            lines.append(f"    Orch->>Agent: {evt.name or msg}")
        elif src == "Agent":
            lines.append(f"    Agent->>Crew: {msg}")
        elif src == "Crew":
            lines.append(f"    Crew->>LLM: {msg}")
        elif src == "Task":
            lines.append(f"    Crew->>Task: {msg}")
    return "\n".join(lines) + "\n"
