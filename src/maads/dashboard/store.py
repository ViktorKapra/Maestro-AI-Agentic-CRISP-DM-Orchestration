"""Read trace artifacts from the filesystem."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from maads.artifact_runs import resolve_active_run_dir
from maads.observability.llm_communications import LLMCommunicationRecord
from maads.observability.schema import TraceRun


def list_cases(artifact_root: Path) -> list[dict[str, Any]]:
    """Scan ``artifact_root/<case>/`` for the active run's ``status.json``."""
    if not artifact_root.is_dir():
        return []
    cases: list[dict[str, Any]] = []
    for child in sorted(artifact_root.iterdir()):
        if not child.is_dir():
            continue
        run_dir = resolve_active_run_dir(child)
        if run_dir is None:
            continue
        status_path = run_dir / "status.json"
        if not status_path.is_file():
            continue
        try:
            payload = json.loads(status_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cases.append(_case_summary(child.name, run_dir, payload))
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
    case_path = artifact_root / case_id
    run_dir = resolve_active_run_dir(case_path)
    if run_dir is None:
        raise FileNotFoundError(f"Case not found: {case_id}")
    return run_dir


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


def read_trace_optional(artifact_dir: Path, *, case_id: str = "") -> TraceRun:
    """Return trace data or an empty run shell when tracing has not flushed yet."""
    path = artifact_dir / "trace" / "trace.json"
    if path.is_file():
        return TraceRun.model_validate_json(path.read_text(encoding="utf-8"))
    status_path = artifact_dir / "status.json"
    case = case_id
    if status_path.is_file():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            case = status.get("case_id") or case
        except (json.JSONDecodeError, OSError):
            pass
    return TraceRun(run_id=artifact_dir.name, case_id=case or None, events=[])


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


def read_process_snapshot(artifact_dir: Path) -> dict[str, Any]:
    """Read live ``process.json`` or fall back to ``final_state.json``."""
    process_path = artifact_dir / "process.json"
    if process_path.is_file():
        return json.loads(process_path.read_text(encoding="utf-8"))
    final_path = artifact_dir / "final_state.json"
    if final_path.is_file():
        return _process_snapshot_from_final_state(
            json.loads(final_path.read_text(encoding="utf-8"))
        )
    return {}


def _process_snapshot_from_final_state(state: dict[str, Any]) -> dict[str, Any]:
    """Map a ``final_state.json`` payload to the ``process.json`` shape."""
    from maads.state import CrispDMState

    parsed = CrispDMState.model_validate(state)
    from maads.run_status import _build_process_snapshot

    return _build_process_snapshot(parsed)


def read_state(artifact_dir: Path) -> dict[str, Any]:
    """Read live ``state.json`` or fall back to ``final_state.json``."""
    live_path = artifact_dir / "state.json"
    if live_path.is_file():
        raw = json.loads(live_path.read_text(encoding="utf-8"))
        if "state" in raw:
            return {
                "updated_at": raw.get("updated_at"),
                "source": "live",
                "state": raw["state"],
            }
        return {"updated_at": None, "source": "live", "state": raw}

    final_path = artifact_dir / "final_state.json"
    if final_path.is_file():
        return {
            "updated_at": None,
            "source": "final",
            "state": json.loads(final_path.read_text(encoding="utf-8")),
        }

    raise FileNotFoundError("state.json not found")
