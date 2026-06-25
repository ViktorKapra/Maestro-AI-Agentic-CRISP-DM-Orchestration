"""Agent plan/delta types shared by orchestrator and capabilities."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Plan:
    """What the PM decides to do next."""
    action: str  # "advance" | "loop_back" | "halt"
    target_substep: str | None = None
    loop_label: str | None = None
    loop_to_phase: int | None = None
    reason: str = ""


@dataclass
class StateDelta:
    """What an agent changed, for logging."""
    fields_written: list[str] = field(default_factory=list)
    notes: str = ""
    failed: bool = False
