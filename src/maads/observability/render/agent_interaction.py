"""Render agent interaction diagram."""
from __future__ import annotations

from maads.observability.schema import TraceRun


def render_agent_interaction(run: TraceRun) -> str:
    lines = [
        "flowchart LR",
        "    subgraph orchestrator [Orchestrator]",
        "        Orch[Orchestrator]",
        "    end",
    ]
    agents: set[str] = set()
    for evt in run.events:
        if evt.type in {"agent.activate", "substep.dispatch"}:
            a = evt.attributes.get("agent") or evt.attributes.get("owner")
            if a:
                agents.add(str(a))

    for agent in sorted(agents):
        aid = agent.replace(" ", "_")
        lines.append(f"    subgraph {aid} [{agent}]")
        lines.append(f"        A_{aid}[{agent}]")
        lines.append("    end")
        lines.append(f"    Orch --> A_{aid}")

    lines.append("")
    lines.append("    subgraph tools [Tools_and_LLM]")
    has_llm = any(e.type.startswith("llm.") for e in run.events)
    has_tool = any(e.type.startswith("tool.") for e in run.events)
    has_py = any(e.type == "python.subprocess" for e in run.events)
    if has_llm:
        lines.append("        LLM[LLM]")
    if has_tool:
        lines.append("        Tool[Tool]")
    if has_py:
        lines.append("        PyExec[PythonExec]")
    lines.append("    end")

    current_agent: str | None = None
    for evt in run.events:
        if evt.type == "agent.activate":
            current_agent = evt.attributes.get("role") or evt.name or evt.attributes.get("agent")
        elif evt.type == "substep.dispatch":
            current_agent = evt.attributes.get("owner")
        elif current_agent and evt.type == "llm.start" and has_llm:
            aid = str(current_agent).replace(" ", "_")
            lines.append(f"    A_{aid} --> LLM")
        elif current_agent and evt.type == "tool.start" and has_tool:
            aid = str(current_agent).replace(" ", "_")
            lines.append(f"    A_{aid} --> Tool")
        elif current_agent and evt.type == "python.subprocess" and has_py:
            aid = str(current_agent).replace(" ", "_")
            lines.append(f"    A_{aid} --> PyExec")

    return "\n".join(lines) + "\n"
