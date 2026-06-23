"""FastAPI routes for the trace monitoring dashboard."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from maads.dashboard import aggregators, store
from maads.observability.llm_communications import LLMCommunicationRecord

router = APIRouter(prefix="/api")


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
        run = store.read_trace(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return aggregators.trace_summary(run)


@router.get("/cases/{case_id}/trace/events")
def get_trace_events(
    case_id: str,
    since_id: str | None = Query(None, alias="since_id"),
) -> dict[str, Any]:
    try:
        run = store.read_trace(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
        run = store.read_trace(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return aggregators.build_graph(run)


def _comm_dict(record: LLMCommunicationRecord) -> dict[str, Any]:
    return record.model_dump(mode="json")
