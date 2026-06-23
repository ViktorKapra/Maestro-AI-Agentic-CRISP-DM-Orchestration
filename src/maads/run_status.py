"""File-based live run status (works without a TTY and during long LLM calls)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from maads.state import SUBSTEP_NAMES, SUBSTEPS, Phase

if TYPE_CHECKING:
    from maads.state import CrispDMState

TOTAL_SUBSTEPS = sum(len(v) for v in SUBSTEPS.values())

PHASE_NAMES: dict[int, str] = {
    int(Phase.BUSINESS_UNDERSTANDING): "Business Understanding",
    int(Phase.DATA_UNDERSTANDING): "Data Understanding",
    int(Phase.DATA_PREPARATION): "Data Preparation",
    int(Phase.MODELING): "Modeling",
    int(Phase.EVALUATION): "Evaluation",
    int(Phase.DEPLOYMENT): "Deployment",
}

_bound_dir: Path | None = None
_bound_state: CrispDMState | None = None
_activity: str = "starting"
_completed_substeps: int = 0


def bind_run(artifact_dir: Path, state: CrispDMState) -> None:
    """Attach the active run; writes an initial ``status.json`` immediately."""
    global _bound_dir, _bound_state, _completed_substeps, _activity
    _bound_dir = artifact_dir
    _bound_state = state
    _completed_substeps = 0
    _activity = "starting"
    flush_status()


def set_activity(message: str) -> None:
    global _activity
    _activity = message
    flush_status()


def record_substep_done(substep: str) -> None:
    global _completed_substeps, _activity
    _completed_substeps += 1
    _activity = f"finished {substep}"
    flush_status()


def flush_status() -> None:
    """Rewrite ``status.json`` and ``status.md`` under the artifact directory."""
    if _bound_dir is None or _bound_state is None:
        return
    state = _bound_state
    artifact_dir = _bound_dir.resolve()
    trace_dir = artifact_dir / "trace"
    payload: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "case_id": state.case_id,
        "phase": int(state.phase),
        "phase_name": PHASE_NAMES.get(int(state.phase), ""),
        "substep": state.substep,
        "substep_name": SUBSTEP_NAMES.get(state.substep, ""),
        "activity": _activity,
        "completed_substeps": _completed_substeps,
        "total_substeps": TOTAL_SUBSTEPS,
        "token_spend": dict(state.token_spend),
        "halted": state.halted,
        "halt_reason": state.halt_reason,
        "artifact_dir": str(artifact_dir),
        "trace_dir": str(trace_dir),
        "status_file": str(artifact_dir / "status.json"),
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "status.json").write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )
    (artifact_dir / "status.md").write_text(_format_md(payload), encoding="utf-8")


def _format_md(payload: dict[str, Any]) -> str:
    tokens = payload.get("token_spend") or {}
    total_tokens = sum(tokens.values()) if tokens else 0
    lines = [
        f"# Run status — {payload.get('case_id', '?')}",
        "",
        f"- **Updated:** {payload.get('updated_at', '?')}",
        f"- **Phase:** {payload.get('phase')} — {payload.get('phase_name', '')}",
        f"- **Substep:** {payload.get('substep')} — {payload.get('substep_name', '')}",
        f"- **Activity:** {payload.get('activity', '')}",
        (
            f"- **Progress:** {payload.get('completed_substeps', 0)}"
            f"/{payload.get('total_substeps', TOTAL_SUBSTEPS)} substeps"
        ),
        f"- **Tokens:** {total_tokens} {dict(tokens) if tokens else ''}",
        f"- **Artifacts:** `{payload.get('artifact_dir', '')}`",
        f"- **Trace:** `{payload.get('trace_dir', '')}`",
    ]
    if payload.get("halted"):
        lines.append(f"- **Halted:** {payload.get('halt_reason', '')}")
    return "\n".join(lines) + "\n"
