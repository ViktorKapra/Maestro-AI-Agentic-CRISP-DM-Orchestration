"""Read trace artifacts from the filesystem."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.observability.llm_communications import LLMCommunicationRecord
from maads.observability.schema import TraceRun


def list_cases(artifact_root: Path) -> list[dict[str, Any]]:
    """Scan ``artifact_root/*/status.json`` for known runs."""
    if not artifact_root.is_dir():
        return []
    cases: list[dict[str, Any]] = []
    for child in sorted(artifact_root.iterdir()):
        if not child.is_dir():
            continue
        status_path = child / "status.json"
        if not status_path.is_file():
            continue
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cases.append(_case_summary(child.name, child, payload))
    return cases


def _case_summary(case_id: str, artifact_dir: Path, status: dict[str, Any]) -> dict[str, Any]:
    trace_path = artifact_dir / "trace" / "trace.json"
    ended_at: str | None = None
    if trace_path.is_file():
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            ended_at = trace.get("ended_at")
        except (json.JSONDecodeError, OSError):
            pass
    halted = bool(status.get("halted"))
    if halted:
        run_status = "halted"
    elif ended_at:
        run_status = "complete"
    else:
        run_status = "running"
    return {
        "case_id": case_id,
        "artifact_dir": str(artifact_dir.resolve()),
        "status": run_status,
        "updated_at": status.get("updated_at"),
        "phase": status.get("phase"),
        "phase_name": status.get("phase_name"),
        "completed_substeps": status.get("completed_substeps"),
        "total_substeps": status.get("total_substeps"),
    }


def case_dir(artifact_root: Path, case_id: str) -> Path:
    path = artifact_root / case_id
    if not path.is_dir():
        raise FileNotFoundError(f"Case not found: {case_id}")
    return path


def read_status(artifact_dir: Path) -> dict[str, Any]:
    path = artifact_dir / "status.json"
    if not path.is_file():
        raise FileNotFoundError("status.json not found")
    return json.loads(path.read_text(encoding="utf-8"))


def read_trace(artifact_dir: Path) -> TraceRun:
    path = artifact_dir / "trace" / "trace.json"
    if not path.is_file():
        raise FileNotFoundError("trace.json not found")
    return TraceRun.model_validate_json(path.read_text(encoding="utf-8"))


def read_communications(artifact_dir: Path) -> list[LLMCommunicationRecord]:
    path = artifact_dir / "trace" / "communications.jsonl"
    if not path.is_file():
        return []
    records: list[LLMCommunicationRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(LLMCommunicationRecord.model_validate_json(line))
    return records


def read_communications_summary(artifact_dir: Path) -> dict[str, Any]:
    path = artifact_dir / "trace" / "communications_summary.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
