"""Bounded bundle for maads improvement sessions (Cursor / optimizers)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from maads.artifact_config import report_excerpt_chars
from maads.artifact_paths import RunPaths, load_manifest
from maads.conclusions import build_conclusions_summary
from maads.observability.llm_communications import LLMCommunicationRecord
from maads.outcome import ml_outcome_deficits, ml_run_succeeded
from maads.state import CrispDMState, SUBSTEP_OWNER


def _preview(text: str | None, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


def _comm_excerpt(rec: LLMCommunicationRecord, limit: int) -> dict[str, Any]:
    raw = rec.outcome.get("raw_response") or rec.provider.get("raw_response")
    if isinstance(raw, dict):
        raw_text = raw.get("text") or json.dumps(raw, default=str)
    else:
        raw_text = str(raw) if raw else ""
    desc = rec.maads.get("task_description") or rec.maads.get("instruction") or ""
    parsed = rec.outcome.get("parsed_json")
    return {
        "id": rec.id,
        "substep": rec.substep,
        "agent": rec.agent_name,
        "parse_ok": rec.outcome.get("parse_ok"),
        "json_valid": rec.outcome.get("json_valid"),
        "schema_ok": rec.outcome.get("schema_ok"),
        "schema_errors": rec.outcome.get("schema_errors"),
        "tokens": rec.tokens.get("total"),
        "prompt_preview": _preview(str(desc), limit),
        "response_preview": _preview(raw_text, limit),
        "parsed_json_keys": list(parsed.keys()) if isinstance(parsed, dict) else [],
    }


def _sandbox_highlights(paths: RunPaths, limit: int) -> list[dict[str, Any]]:
    manifest = paths.sandbox_manifest()
    if not manifest.is_file():
        return []
    by_label: dict[str, list[dict[str, Any]]] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        label = row.get("label") or "unknown"
        by_label.setdefault(label, []).append(row)
    highlights: list[dict[str, Any]] = []
    for label, rows in by_label.items():
        if not rows:
            continue
        winner = next((r for r in reversed(rows) if r.get("ok")), None)
        near_misses = [r.get("seq") for r in rows if not r.get("ok")][-3:]
        entry: dict[str, Any] = {
            "label": label,
            "attempts": len(rows),
            "winner_seq": winner.get("seq") if winner else None,
            "near_miss_seqs": near_misses,
        }
        if winner and winner.get("stderr"):
            stderr_path = paths.sandbox_exec() / winner["stderr"]
            if stderr_path.is_file():
                entry["stderr_tail"] = _preview(stderr_path.read_text(encoding="utf-8"), limit)
        highlights.append(entry)
    return highlights[:20]


def _decision_chain(
    records: list[LLMCommunicationRecord],
    state: CrispDMState,
) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    seen_substeps: set[str] = set()
    priority = ("1.1", "1.3", "2.4", "3.1", "3.5", "4.1", "4.4", "5.1", "5.3", "6.1")
    for sub in priority:
        owner = SUBSTEP_OWNER.get(sub, "")
        phase_key = {"pm": "bu", "domain": "du", "data_engineer": "dp",
                     "data_scientist": "md", "developer": "ev"}.get(owner, owner)
        comm_ids = [r.id for r in records if r.substep == sub and r.closed]
        if not comm_ids and sub not in seen_substeps:
            continue
        seen_substeps.add(sub)
        chain.append({
            "phase": phase_key,
            "substep": sub,
            "owner": owner,
            "comm_ids": comm_ids[:3],
        })
    return chain


def _prior_run_id(case_root: Path, current_run_id: str) -> str | None:
    index_path = case_root / "runs_index.json"
    if not index_path.is_file():
        archive = case_root / "archive"
        if not archive.is_dir():
            return None
        candidates = sorted(
            (p.name for p in archive.iterdir() if p.is_dir()),
            reverse=True,
        )
        for cid in candidates:
            if cid != current_run_id:
                return cid
        return None
    try:
        raw = json.loads(index_path.read_text(encoding="utf-8"))
        for entry in raw.get("runs") or []:
            rid = entry.get("run_id")
            if rid and rid != current_run_id:
                return rid
    except (json.JSONDecodeError, OSError):
        pass
    return None


def build_improvement_bundle(
    state: CrispDMState,
    paths: RunPaths,
    records: list[LLMCommunicationRecord],
    *,
    case_root: Path | None = None,
) -> dict[str, Any]:
    limit = report_excerpt_chars()
    conclusions = build_conclusions_summary(state)
    substantive = [
        r for r in records
        if r.closed and (r.outcome.get("parsed_json") or r.maads.get("task_description"))
    ]
  # include successes and checkpoint turns
    excerpts = [_comm_excerpt(r, limit) for r in substantive[-30:]]
    prior = None
    if case_root is not None:
        prior_id = _prior_run_id(case_root, paths.run_dir.name)
        if prior_id:
            prior = f"archive/{prior_id}/reports/postmortem.json"
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "case_id": state.case_id,
            "run_id": paths.run_dir.name,
            "prior_run_id": prior,
        },
        "outcome": {
            "ml_success": ml_run_succeeded(state),
            "ml_deficits": ml_outcome_deficits(state),
            "cv_score": (
                state.md.chosen_model.cv_score if state.md.chosen_model else None
            ),
            "chosen_model": (
                state.md.chosen_model.technique if state.md.chosen_model else None
            ),
            "submission_path": state.dep.submission_path,
        },
        "decision_chain": _decision_chain(records, state),
        "degraded_paths": list(state.degraded_flags),
        "sandbox_highlights": _sandbox_highlights(paths, limit),
        "comm_excerpts": excerpts,
        "conclusions_summary": {
            "workflow_complete": conclusions.get("workflow_complete"),
            "ml_success": conclusions.get("ml_success"),
            "data_quality_blockers": conclusions.get("data_quality_blockers"),
            "decision": conclusions.get("decision"),
        },
        "cross_run": {"prior_postmortem": prior},
    }
