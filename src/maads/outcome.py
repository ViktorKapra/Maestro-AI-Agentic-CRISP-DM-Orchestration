"""ML outcome helpers — distinguish workflow completion from ML success."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maads.state import CrispDMState


def ml_outcome_deficits(state: "CrispDMState") -> list[str]:
    """Return human-readable deficits when core ML deliverables are missing."""
    deficits: list[str] = []
    if state.md.chosen_model is None:
        deficits.append("no chosen_model")
    if not state.dep.submission_path:
        deficits.append("no submission_path")
    assessment = state.ev.assessment_of_dm_results or {}
    if not assessment.get("meets"):
        deficits.append("business success criteria not met")
    return deficits


def ml_run_succeeded(state: "CrispDMState") -> bool:
    return not ml_outcome_deficits(state)


def workflow_complete(state: "CrispDMState") -> bool:
    """True when the CRISP-DM workflow reached the end of phase 6."""
    from maads.state import Phase

    return (
        state.halted
        and int(state.phase) == int(Phase.DEPLOYMENT)
        and state.substep == "6.4"
    )


def completion_halt_reason(state: "CrispDMState") -> str:
    """Halt reason when the workflow finishes phase 6."""
    deficits = ml_outcome_deficits(state)
    if not deficits:
        return "completed phase 6"
    return f"completed phase 6 without ML success: {'; '.join(deficits)}"
