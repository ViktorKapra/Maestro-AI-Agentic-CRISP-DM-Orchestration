"""Write trace.json and rendered artefacts."""
from __future__ import annotations

import json
from pathlib import Path

from maads.observability.collector import TraceCollector
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
    """Write trace.json and rendered artefacts.

    When ``finalize`` is False the run stays open so later events can be appended
    and flushed again (live tracing during a long pipeline run).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    if finalize:
        collector.end_run()
    run = collector.to_trace_run()

    trace_path = out_dir / "trace.json"
    trace_path.write_text(
        json.dumps(run.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )

    (out_dir / "timeline.md").write_text(render_timeline(run), encoding="utf-8")
    (out_dir / "call_tree.txt").write_text(render_call_tree(run), encoding="utf-8")
    (out_dir / "sequence.mmd").write_text(render_sequence(run), encoding="utf-8")
    (out_dir / "flowchart.mmd").write_text(render_flowchart(run), encoding="utf-8")
    (out_dir / "agent_interaction.mmd").write_text(
        render_agent_interaction(run), encoding="utf-8"
    )
    (out_dir / "narrative.md").write_text(render_narrative(run), encoding="utf-8")

    return trace_path


def export_trace(collector: TraceCollector, out_dir: Path) -> Path:
    """Write the final trace snapshot and mark the run complete."""
    return write_trace_artifacts(collector, out_dir, finalize=True)
