"""Write communication sidecar artefacts alongside trace exports."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.artifact_config import write_renders
from maads.artifact_paths import RunPaths
from maads.observability.llm_communications import (
    LLMCommunicationRecord,
    LLMCommunicationRegistry,
    build_communications_summary,
    get_communication_registry,
    llm_io_mode,
    record_for_export,
)
from maads.observability.render.communications import render_communications


def _comm_paths(out_dir: Path) -> tuple[Path, Path, Path]:
    """Return (collected_jsonl, legacy_jsonl, summary_path)."""
    run_root = out_dir.parent if out_dir.name == "trace" else out_dir
    paths = RunPaths(run_root)
    paths.collected.mkdir(parents=True, exist_ok=True)
    paths.derived.mkdir(parents=True, exist_ok=True)
    collected = paths.collected / "communications.jsonl"
    legacy = paths.trace_legacy / "communications.jsonl"
    summary = paths.derived / "communications_summary.json"
    return collected, legacy, summary


def append_communication_record(
    registry: LLMCommunicationRegistry,
    record: LLMCommunicationRecord,
    out_dir: Path,
) -> None:
    """Append one closed comm record to collected + legacy JSONL."""
    collected, legacy, _ = _comm_paths(out_dir)
    collected.parent.mkdir(parents=True, exist_ok=True)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record_for_export(record), default=str) + "\n"
    for path in (collected, legacy):
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    registry.mark_exported(record.id)


def write_communication_artifacts(
    registry: LLMCommunicationRegistry,
    out_dir: Path,
) -> None:
    """Write communications.jsonl, optional markdown, and communications_summary.json."""
    records = registry.all_records()
    if not records:
        return

    collected, legacy, summary_path = _comm_paths(out_dir)
    mode = llm_io_mode()

    payload_lines = [json.dumps(record_for_export(rec), default=str) for rec in records]
    text = "\n".join(payload_lines) + "\n"
    collected.write_text(text, encoding="utf-8")
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(text, encoding="utf-8")
    for rec in records:
        registry.mark_exported(rec.id)

    if mode != "off" and write_renders():
        (RunPaths(collected.parent.parent).trace_legacy / "communications.md").write_text(
            render_communications(records), encoding="utf-8",
        )

    summary: dict[str, Any] = build_communications_summary(records)
    summary["llm_io_mode"] = mode
    summary_text = json.dumps(summary, indent=2, default=str)
    summary_path.write_text(summary_text, encoding="utf-8")
    legacy_summary = legacy.parent / "communications_summary.json"
    legacy_summary.write_text(summary_text, encoding="utf-8")


def export_communications(out_dir: Path) -> None:
    write_communication_artifacts(get_communication_registry(), out_dir)
