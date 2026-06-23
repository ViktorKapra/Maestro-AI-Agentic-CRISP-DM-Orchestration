"""The orchestrator.

Walks the CRISP-DM state machine: asks the PM for the next move, dispatches each
substep to its owning agent, and enforces hard caps so a run can't blow the token
budget. Loops are wired but not exercised until Phase 3.
"""
from __future__ import annotations

import os
from pathlib import Path

from maads.agents import (
    DataEngineerAgent,
    DataScientistAgent,
    DeveloperAgent,
    DomainExpertAgent,
    ProjectManagerAgent,
)
from maads.state import SUBSTEPS, SUBSTEP_OWNER, CrispDMState, Phase


# Hard caps. Tighten before the demo; loosen during development.
MAX_PHASE_TRANSITIONS = 12
MAX_VISITS_PER_PHASE = 3
MAX_INNER_LOOP_ITERATIONS = 3  # the 3 <-> 4 loop specifically


class Orchestrator:
    def __init__(self, state: CrispDMState, artifact_dir: Path) -> None:
        self.state = state
        self.artifact_dir = artifact_dir
        self.pm = ProjectManagerAgent(artifact_dir=artifact_dir)
        self.agents = {
            "pm": self.pm,
            "domain":         DomainExpertAgent(artifact_dir=artifact_dir),
            "data_engineer":  DataEngineerAgent(artifact_dir=artifact_dir),
            "data_scientist": DataScientistAgent(artifact_dir=artifact_dir),
            "developer":      DeveloperAgent(artifact_dir=artifact_dir),
        }
        self._n_transitions = 0
        self._phase_visits: dict[int, int] = {int(state.phase): 1}
        self._inner_loop_count = 0

    # ── Main loop ─────────────────────────────────────────────────────────

    def run(self) -> CrispDMState:
        """Walk the cycle, running every substep, until phase 6 completes.

        Phase 1 is a linear pass: there are no loop contours yet (those arrive in
        Phase 3), so there is no flow decision for the PM to make — the
        orchestrator dispatches each substep to its owner and advances. The PM is
        still an active agent (it owns substeps 1.4 / 5.2 / 5.3) and becomes the
        decision-maker via `pm.plan()` + `_fire_loop()` once loops exist.
        """
        while not self.state.halted:
            if self._caps_exceeded():
                self._force_halt("hard cap exceeded")
                break
            if self._over_token_budget():
                self._force_halt("token budget exceeded")
                break

            try:
                self._dispatch(self.state.substep)
            except Exception as exc:  # fail loudly, halt the run
                self._force_halt(f"dispatch failed at {self.state.substep}: {exc}")
                break

            if self._advance_substep():
                break

        return self.state

    # ── Helpers ───────────────────────────────────────────────────────────

    def _dispatch(self, substep: str) -> None:
        if not self.state.substep_prereqs_satisfied(substep):
            self.state.append_log(
                "orchestrator", f"prereqs not satisfied for {substep}; skipping", level="warn")
            return
        owner = SUBSTEP_OWNER[substep]
        delta = self.agents[owner].act(self.state)
        detail = ", ".join(delta.fields_written) or delta.notes
        self.state.append_log(owner, f"ran {substep} -> {detail}")

    def _fire_loop(self, target_phase: int, reason: str, label: str = "?") -> None:
        self.state.record_loop(label, int(self.state.phase), target_phase, reason)
        if label == "B":
            self._inner_loop_count += 1
        self.state.phase = Phase(target_phase)
        self.state.substep = SUBSTEPS[Phase(target_phase)][0]
        self._phase_visits[target_phase] = self._phase_visits.get(target_phase, 0) + 1
        self.state.append_log("orchestrator", f"loop {label} -> phase {target_phase}: {reason}", level="warn")

    def _advance_substep(self) -> bool:
        """Advance to the next substep / phase. Return True when the run is done."""
        phase = self.state.phase
        subs = SUBSTEPS[phase]
        i = subs.index(self.state.substep)
        if i + 1 < len(subs):
            self.state.substep = subs[i + 1]
            return False
        # end of this phase -> next phase
        self._n_transitions += 1
        next_phase = int(phase) + 1
        if next_phase > int(Phase.DEPLOYMENT):
            self.state.halted = True
            self.state.halt_reason = "completed phase 6"
            self.state.append_log("orchestrator", "run complete: phase 6 finished")
            return True
        self.state.phase = Phase(next_phase)
        self.state.substep = SUBSTEPS[Phase(next_phase)][0]
        self._phase_visits[next_phase] = self._phase_visits.get(next_phase, 0) + 1
        return False

    def _caps_exceeded(self) -> bool:
        if self._n_transitions >= MAX_PHASE_TRANSITIONS:
            return True
        if any(v > MAX_VISITS_PER_PHASE for v in self._phase_visits.values()):
            return True
        if self._inner_loop_count > MAX_INNER_LOOP_ITERATIONS:
            return True
        return False

    def _over_token_budget(self) -> bool:
        cap = os.getenv("MAX_TOKENS_PER_RUN")
        if not cap:
            return False
        try:
            return sum(self.state.token_spend.values()) >= int(cap)
        except (ValueError, TypeError):
            return False

    def _force_halt(self, reason: str) -> None:
        self.state.halted = True
        self.state.halt_reason = reason
        self.state.append_log("orchestrator", reason, level="warn")
