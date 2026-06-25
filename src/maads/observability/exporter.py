"""Write trace.json and rendered artefacts."""
from __future__ import annotations

import json
from pathlib import Path

from maads.artifact_config import write_renders
from maads.artifact_paths import RunPaths
from maads.observability.collector import TraceCollector
from maads.observability.communication_exporter import write_communication_artifacts
from maads.observability.llm_communications import get_communication_registry
from maads.observability.render.agent_interaction import render_agent_interaction
from maads.observability.render.call_tree import render_call_tree
from maads.observability.render.mermaid_flowchart import render_flowchart
from maads.observability.render.mermaid_sequence import render_sequence
from maads.observability.render.narrative import render_narrative
from maads.observability.render.timeline import render_timeline


def write_trace_artifacts(
    collector: TraceCollector,
    out_dir: Path,
    *,
    finalize: bool = False,
) -> Path:
    """Write trace.json and optional rendered artefacts.

    When ``finalize`` is False the run stays open so later events can be appended
    and flushed again (live tracing during a long pipeline run).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if finalize:
        collector.end_run()
    run = collector.to_trace_run()

    run_root = out_dir.parent if out_dir.name == "trace" else out_dir
    paths = RunPaths(run_root)
    paths.derived.mkdir(parents=True, exist_ok=True)

    trace_payload = json.dumps(run.model_dump(mode="json"), indent=2, default=str)
    derived_trace = paths.derived / "trace.json"
    legacy_trace = paths.trace_legacy / "trace.json"
    derived_trace.write_text(trace_payload, encoding="utf-8")
    legacy_trace.write_text(trace_payload, encoding="utf-8")

    if write_renders():
        legacy = paths.trace_legacy
        legacy.mkdir(parents=True, exist_ok=True)
        (legacy / "timeline.md").write_text(render_timeline(run), encoding="utf-8")
        (legacy / "call_tree.txt").write_text(render_call_tree(run), encoding="utf-8")
        (legacy / "sequence.mmd").write_text(render_sequence(run), encoding="utf-8")
        (legacy / "flowchart.mmd").write_text(render_flowchart(run), encoding="utf-8")
        (legacy / "agent_interaction.mmd").write_text(
            render_agent_interaction(run), encoding="utf-8",
        )
        (legacy / "narrative.md").write_text(render_narrative(run), encoding="utf-8")

    write_communication_artifacts(get_communication_registry(), out_dir)

    return derived_trace


def export_trace(collector: TraceCollector, out_dir: Path) -> Path:
    """Write the final trace snapshot and mark the run complete."""
    return write_trace_artifacts(collector, out_dir, finalize=True)
