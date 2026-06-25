"""Substep debug index — comm + sandbox + trace pointers."""
from __future__ import annotations

import json
from typing import Any

from maads.artifact_paths import RunPaths
from maads.observability.llm_communications import LLMCommunicationRecord
from maads.observability.schema import TraceRun


def build_substep_debug_index(
    substep: str,
    paths: RunPaths,
    *,
    trace: TraceRun | None = None,
    communications: list[LLMCommunicationRecord] | None = None,
) -> dict[str, Any]:
    comms = [
        c.model_dump(mode="json")
        for c in (communications or [])
        if c.substep == substep
    ]
    trace_events: list[dict[str, Any]] = []
    if trace:
        for evt in trace.events:
            if evt.attributes.get("substep") == substep:
                trace_events.append({
                    "id": evt.id,
                    "type": evt.type,
                    "name": evt.name,
                    "ts": evt.ts.isoformat(),
                    "duration_ms": evt.duration_ms,
                })
    sandbox_runs: list[dict[str, Any]] = []
    manifest = paths.sandbox_manifest()
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("substep") == substep:
                sandbox_runs.append(row)
    return {
        "substep": substep,
        "communications": comms,
        "trace_events": trace_events,
        "sandbox_runs": sandbox_runs,
        "files": {
            "state": "state.json",
            "process": "process.json",
            "communications": "collected/communications.jsonl",
        },
    }
