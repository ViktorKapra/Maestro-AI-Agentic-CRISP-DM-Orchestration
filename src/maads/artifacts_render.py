"""Regenerate trace markdown/mermaid renders from ``trace.json``."""
from __future__ import annotations

import json
from pathlib import Path

from maads.artifact_paths import RunPaths
from maads.observability.render.agent_interaction import render_agent_interaction
from maads.observability.render.call_tree import render_call_tree
from maads.observability.render.communications import render_communications
from maads.observability.render.mermaid_flowchart import render_flowchart
from maads.observability.render.mermaid_sequence import render_sequence
from maads.observability.render.narrative import render_narrative
from maads.observability.render.timeline import render_timeline
from maads.observability.schema import TraceRun
from maads.observability.llm_communications import LLMCommunicationRecord


def render_trace_views(run_dir: Path) -> list[Path]:
    """Write human-readable trace views under ``trace/`` from existing JSON."""
    paths = RunPaths(run_dir)
    trace_path = paths.trace_json()
    if not trace_path.is_file():
        raise FileNotFoundError(f"trace.json not found: {trace_path}")
    run = TraceRun.model_validate_json(trace_path.read_text(encoding="utf-8"))
    out_dir = paths.trace_legacy
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in (
        ("timeline.md", render_timeline(run)),
        ("call_tree.txt", render_call_tree(run)),
        ("sequence.mmd", render_sequence(run)),
        ("flowchart.mmd", render_flowchart(run)),
        ("agent_interaction.mmd", render_agent_interaction(run)),
        ("narrative.md", render_narrative(run)),
    ):
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)

    comm_path = paths.communications_jsonl()
    if comm_path.is_file():
        records: list[LLMCommunicationRecord] = []
        for line in comm_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(LLMCommunicationRecord.model_validate_json(line))
        md_path = out_dir / "communications.md"
        md_path.write_text(render_communications(records), encoding="utf-8")
        written.append(md_path)
    return written
