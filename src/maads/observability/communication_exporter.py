"""Write communication sidecar artefacts alongside trace exports."""
from __future__ import annotations

import json
from pathlib import Path

from maads.observability.llm_communications import (
    LLMCommunicationRegistry,
    build_communications_summary,
    get_communication_registry,
    llm_io_mode,
)
from maads.observability.render.communications import render_communications


def write_communication_artifacts(
    registry: LLMCommunicationRegistry,
    out_dir: Path,
) -> None:
    """Write communications.jsonl, communications.md, and communications_summary.json."""
    records = registry.all_records()
    if not records:
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    mode = llm_io_mode()

    jsonl_path = out_dir / "communications.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec.model_dump(mode="json"), default=str) + "\n")

    if mode != "off":
        (out_dir / "communications.md").write_text(
            render_communications(records), encoding="utf-8"
        )

    summary = build_communications_summary(records)
    summary["llm_io_mode"] = mode
    (out_dir / "communications_summary.json").write_text(
        json.dumps(summary, indent=2, default=str),
        encoding="utf-8",
    )


def export_communications(out_dir: Path) -> None:
    write_communication_artifacts(get_communication_registry(), out_dir)
