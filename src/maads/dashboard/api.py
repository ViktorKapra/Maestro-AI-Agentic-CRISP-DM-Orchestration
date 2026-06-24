"""FastAPI routes for the trace monitoring dashboard."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from maads.dashboard import aggregators, store
from maads.observability.llm_communications import LLMCommunicationRecord

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, Any]:
    root = _artifact_root()
    cases = store.list_cases(root)
    return {
        "ok": True,
        "artifact_root": str(root.resolve()),
        "case_count": len(cases),
        "cases": [c["case_id"] for c in cases],
    }


def _artifact_root() -> Path:
    from maads.dashboard.server import get_artifact_root

    return get_artifact_root()


@router.get("/cases")
def list_cases() -> list[dict[str, Any]]:
    return store.list_cases(_artifact_root())


@router.get("/cases/{case_id}/status")
def get_status(case_id: str) -> dict[str, Any]:
    try:
        return store.read_status(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/trace/summary")
def get_trace_summary(case_id: str) -> dict[str, Any]:
    try:
        artifact_dir = store.case_dir(_artifact_root(), case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = store.read_trace_optional(artifact_dir, case_id=case_id)
    return aggregators.trace_summary(run)


@router.get("/cases/{case_id}/trace/events")
def get_trace_events(
    case_id: str,
    since_id: str | None = Query(None, alias="since_id"),
) -> dict[str, Any]:
    try:
        artifact_dir = store.case_dir(_artifact_root(), case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = store.read_trace_optional(artifact_dir, case_id=case_id)
    return aggregators.trace_events_since(run, since_id)


@router.get("/cases/{case_id}/communications")
def get_communications(case_id: str) -> list[dict[str, Any]]:
    try:
        records = store.read_communications(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_comm_dict(r) for r in records]


@router.get("/cases/{case_id}/communications/summary")
def get_communications_summary(case_id: str) -> dict[str, Any]:
    try:
        return store.read_communications_summary(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/graph")
def get_graph(case_id: str) -> dict[str, Any]:
    try:
        artifact_dir = store.case_dir(_artifact_root(), case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = store.read_trace_optional(artifact_dir, case_id=case_id)
    return aggregators.build_graph(run)


@router.get("/cases/{case_id}/process")
def get_process(case_id: str) -> dict[str, Any]:
    try:
        artifact_dir = store.case_dir(_artifact_root(), case_id)
        status = store.read_status(artifact_dir)
        run = store.read_trace_optional(artifact_dir, case_id=case_id)
        snapshot = store.read_process_snapshot(artifact_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return aggregators.build_process_view(
        status, run, snapshot, artifact_dir=artifact_dir,
    )


@router.get("/cases/{case_id}/state")
def get_state(case_id: str) -> dict[str, Any]:
    try:
        artifact_dir = store.case_dir(_artifact_root(), case_id)
        return store.read_state(artifact_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/rag")
def get_rag(case_id: str) -> dict[str, Any]:
    """RAG corpus, embedder, and passages for the Domain Expert (live from state)."""
    from maads.config import load_case_config
    from maads.dashboard.rag_view import build_rag_view
    from maads.paths import resolve_path
    from maads.state import CrispDMState

    state: CrispDMState | None = None
    try:
        artifact_dir = store.case_dir(_artifact_root(), case_id)
        raw = store.read_state(artifact_dir)
        state = CrispDMState.model_validate(raw["state"])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        config_path = resolve_path("configs") / f"{case_id}.yaml"
        if config_path.is_file():
            state = CrispDMState.from_config(load_case_config(config_path))
    return build_rag_view(state, case_id=case_id)


def _comm_dict(record: LLMCommunicationRecord) -> dict[str, Any]:
    return record.model_dump(mode="json")
