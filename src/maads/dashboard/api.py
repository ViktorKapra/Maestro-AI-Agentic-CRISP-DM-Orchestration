"""FastAPI routes for the trace monitoring dashboard."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from maads.dashboard import aggregators, store
from maads.observability.llm_communications import LLMCommunicationRecord, record_for_export
from maads.reports.debug_index import build_substep_debug_index

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


@router.get("/cases/{case_id}/runs")
def get_case_runs(case_id: str) -> list[dict[str, Any]]:
    case_path = _artifact_root() / case_id
    if not case_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    return store.list_runs(case_path)


@router.get("/cases/{case_id}/live_summary")
def get_live_summary(case_id: str) -> dict[str, Any]:
    try:
        return store.read_live_summary(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/status")
def get_status(case_id: str) -> dict[str, Any]:
    try:
        return store.read_status(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/manifest")
def get_manifest(case_id: str) -> dict[str, Any]:
    try:
        return store.read_manifest(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/trace/summary")
def get_trace_summary(
    case_id: str,
    limit: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    try:
        artifact_dir = store.case_dir(_artifact_root(), case_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run = store.read_trace_optional(artifact_dir, case_id=case_id)
    return aggregators.trace_summary(run, tail_limit=limit)


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
def get_communications(
    case_id: str,
    since_id: str | None = Query(None, alias="since_id"),
    limit: int | None = Query(None, ge=1, le=500),
) -> list[dict[str, Any]]:
    try:
        records = store.read_communications(
            store.case_dir(_artifact_root(), case_id),
            since_id=since_id,
            limit=limit,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_comm_dict(r) for r in records]


@router.get("/cases/{case_id}/communications/{comm_id}")
def get_communication(case_id: str, comm_id: str) -> dict[str, Any]:
    try:
        record = store.read_communication(
            store.case_dir(_artifact_root(), case_id), comm_id,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail=f"Communication not found: {comm_id}")
    return _comm_dict(record)


@router.get("/cases/{case_id}/communications/summary")
def get_communications_summary(case_id: str) -> dict[str, Any]:
    try:
        return store.read_communications_summary(store.case_dir(_artifact_root(), case_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/debug/substep/{substep}")
def get_substep_debug(case_id: str, substep: str) -> dict[str, Any]:
    try:
        artifact_dir = store.case_dir(_artifact_root(), case_id)
        run = store.read_trace_optional(artifact_dir, case_id=case_id)
        comms = store.read_communications(artifact_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from maads.artifact_paths import RunPaths

    return build_substep_debug_index(
        substep, RunPaths(artifact_dir), trace=run, communications=comms,
    )


@router.get("/cases/{case_id}/reports/postmortem")
def get_postmortem(case_id: str) -> dict[str, Any]:
    try:
        return store.read_report(store.case_dir(_artifact_root(), case_id), "postmortem.json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/reports/case_report")
def get_case_report(case_id: str) -> dict[str, Any]:
    try:
        return store.read_report(store.case_dir(_artifact_root(), case_id), "case_report.json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/reports/case_report.md", response_class=PlainTextResponse)
def get_case_report_md(case_id: str) -> str:
    try:
        return store.read_report_text(
            store.case_dir(_artifact_root(), case_id), "case_report.md",
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cases/{case_id}/reports/improvement_bundle")
def get_improvement_bundle(case_id: str) -> dict[str, Any]:
    try:
        return store.read_report(
            store.case_dir(_artifact_root(), case_id), "improvement_bundle.json",
        )
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


@router.get("/configs")
def list_configs() -> list[dict[str, Any]]:
    """Return available case configs from the configs/ directory."""
    from maads.paths import repo_root
    import yaml as _yaml

    configs_dir = repo_root() / "configs"
    result = []
    for yaml_path in sorted(configs_dir.glob("*.yaml")):
        try:
            raw = _yaml.safe_load(yaml_path.read_text())
            result.append({
                "case_id": raw.get("case_id", yaml_path.stem),
                "problem_type": raw.get("problem_type"),
                "evaluation_metric": raw.get("evaluation_metric"),
                "problem_statement": (raw.get("problem_statement") or "").strip(),
                "success_threshold": (raw.get("success_criterion") or {}).get("threshold"),
            })
        except Exception:
            result.append({"case_id": yaml_path.stem, "problem_type": None, "evaluation_metric": None, "problem_statement": None, "success_threshold": None})
    return result


class RunRequest(BaseModel):
    case_id: str


@router.post("/run")
def start_run(req: RunRequest) -> dict[str, Any]:
    """Launch a pipeline run for the given case in the background."""
    from maads.paths import repo_root

    root = repo_root()
    configs_dir = root / "configs"
    config_path = configs_dir / f"{req.case_id}.yaml"
    if not config_path.is_file():
        raise HTTPException(status_code=404, detail=f"Config not found: {req.case_id}")

    proc = subprocess.Popen(
        [sys.executable, "-m", "maads", "run", "--case", req.case_id],
        cwd=str(root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"status": "started", "case_id": req.case_id, "pid": proc.pid}


def _comm_dict(record: LLMCommunicationRecord) -> dict[str, Any]:
    return record_for_export(record)
