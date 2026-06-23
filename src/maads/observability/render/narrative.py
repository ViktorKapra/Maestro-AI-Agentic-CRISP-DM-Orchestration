"""Deterministic narrative from trace events."""
from __future__ import annotations

from maads.observability.schema import TraceRun


def _sentence_for_event(evt_type: str, name: str, attrs: dict) -> str | None:
    if evt_type == "run.start":
        return f"The workflow started for case `{attrs.get('case_id', 'unknown')}` at substep {attrs.get('substep', '?')}."
    if evt_type == "substep.dispatch":
        return (
            f"The orchestrator dispatched substep **{attrs.get('substep')}** "
            f"({name}) to agent `{attrs.get('owner', '?')}`."
        )
    if evt_type == "crew.start":
        return f"Agent `{attrs.get('agent_name', name)}` started a CrewAI crew for substep {attrs.get('substep', '?')}."
    if evt_type == "llm.start":
        model = attrs.get("model")
        return f"An LLM call began{f' (model={model})' if model else ''}."
    if evt_type == "llm.end":
        tokens = attrs.get("total_tokens")
        return f"The LLM returned a response{f' using {tokens} tokens' if tokens else ''}."
    if evt_type == "crew.end":
        return f"The CrewAI crew completed for agent `{attrs.get('agent_name', '?')}`."
    if evt_type == "python.subprocess":
        if attrs.get("return_code") is not None:
            return (
                f"A Python baseline snippet executed via PythonExec "
                f"(exit code {attrs.get('return_code')}, ok={attrs.get('ok')})."
            )
        return "A Python baseline snippet started in a subprocess sandbox."
    if evt_type == "phase.transition":
        return (
            f"The pipeline advanced from phase {attrs.get('from_phase')} "
            f"to phase {attrs.get('to_phase')} (substep {attrs.get('to_substep')})."
        )
    if evt_type == "branch":
        return f"A conditional branch skipped substep {attrs.get('substep')}: {attrs.get('reason')}."
    if evt_type == "loop":
        return f"A loop-back fired ({attrs.get('label')}): phase {attrs.get('to_phase')} — {attrs.get('reason')}."
    if evt_type == "tool.end" and name.startswith("FileIO"):
        return f"A file was written: `{attrs.get('path', '?')}`."
    if evt_type == "run.end":
        reason = attrs.get("halt_reason", "completed")
        return f"The workflow ended: {reason}."
    if evt_type == "exception":
        return f"An exception occurred ({name}): {attrs.get('message') or attrs.get('error', '')}."
    return None


def render_narrative(run: TraceRun) -> str:
    lines = [
        "# Execution Narrative",
        "",
        f"This is an automated step-by-step account of run `{run.run_id}`.",
        "",
    ]
    step = 1
    for evt in run.events:
        sentence = _sentence_for_event(evt.type, evt.name, evt.attributes)
        if sentence:
            lines.append(f"{step}. {sentence}")
            step += 1
    if step == 1:
        lines.append("No narrative events were recorded.")
    return "\n".join(lines) + "\n"
