"""The orchestrator.

Walks the CRISP-DM state machine: asks the PM for the next move, dispatches each
substep to its owning agent, and enforces hard caps so a run can't blow the token
budget. Loops are wired but not exercised until Phase 3.

Loop machinery (_fire_loop, _can_fire_loop, loop_back handling) is intentionally
retained for P0 CRISP-DM back-edges; use test_path_coverage loop scenarios to
verify before removing.
"""
from __future__ import annotations

import os
from pathlib import Path

from maads.agents import (
    DataEngineerAgent,
    DataScientistAgent,
    DeveloperAgent,
    DomainExpertAgent,
    Plan,
    ProjectManagerAgent,
)
from maads.shutdown import INTERRUPT_HALT_REASON, shutdown_requested
from maads.state import SUBSTEPS, SUBSTEP_OWNER, CrispDMState, Phase
from maads.validators import validate_phase_3_artifacts, validate_phase_4_models


# Hard caps. Tighten before the demo; loosen during development.
MAX_PHASE_TRANSITIONS = 12
MAX_VISITS_PER_PHASE = 3
MAX_INNER_LOOP_ITERATIONS = 3  # the 3 <-> 4 loop specifically


class Orchestrator:
    def __init__(
        self,
        state: CrispDMState,
        artifact_dir: Path,
    ) -> None:
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
        """Hub-and-spoke: PM plans each turn; orchestrator dispatches and enforces caps."""
        while not self.state.halted:
            if shutdown_requested():
                self._force_halt(INTERRUPT_HALT_REASON)
                break
            if self._caps_exceeded():
                self._force_halt("hard cap exceeded")
                break
            if self._over_token_budget():
                self._force_halt("token budget exceeded")
                break

            plan = self.pm.plan(self.state)
            self.state.append_log(
                "pm",
                f"plan -> {plan.action} {plan.target_substep or ''}: {plan.reason}",
            )

            if plan.action == "halt":
                if self._deployment_review_pending():
                    self.state.append_log(
                        "orchestrator",
                        "ignored PM halt: substep 6.4 (experience_documentation) "
                        "not complete",
                        level="warn",
                    )
                else:
                    self._force_halt(plan.reason or "PM halt")
                    break

            if plan.action == "loop_back":
                if plan.loop_to_phase and self._can_fire_loop(plan):
                    self._fire_loop(
                        plan.loop_to_phase, plan.reason, plan.loop_label or "?",
                    )
                    if plan.target_substep:
                        target_phase = Phase(plan.loop_to_phase)
                        allowed = SUBSTEPS[target_phase]
                        if plan.target_substep in allowed:
                            self.state.substep = plan.target_substep
                        else:
                            self.state.append_log(
                                "orchestrator",
                                f"ignored PM target_substep {plan.target_substep} "
                                f"for phase {plan.loop_to_phase}",
                                level="warn",
                            )
                else:
                    self.state.append_log(
                        "orchestrator", "loop blocked by guard", level="warn",
                    )
                continue

            # On advance, always run the *current* substep; the orchestrator advances
            # mechanically after dispatch. target_substep is only for loop_back.
            substep = self.state.substep
            if (
                plan.action == "advance"
                and plan.target_substep
                and plan.target_substep != self.state.substep
            ):
                self.state.append_log(
                    "orchestrator",
                    f"ignored PM target_substep {plan.target_substep}; "
                    f"running current {self.state.substep}",
                    level="warn",
                )

            try:
                self._dispatch(substep)
            except Exception as exc:
                self._force_halt(f"dispatch failed at {substep}: {exc}")
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
        target_phase = int(target_phase)  # defend against a stringy LLM value
        self.state.record_loop(label, int(self.state.phase), target_phase, reason)
        if label == "B":
            self._inner_loop_count += 1
        self.state.phase = Phase(target_phase)
        self.state.substep = SUBSTEPS[Phase(target_phase)][0]
        self._phase_visits[target_phase] = self._phase_visits.get(target_phase, 0) + 1
        # The loop addresses the findings; clear them so they don't re-fire next turn.
        self.state.validator_findings = []
        self.state.append_log("orchestrator", f"loop {label} -> phase {target_phase}: {reason}", level="warn")

    def _validate_on_transition(self, leaving_phase: Phase) -> None:
        """Run the state-artifact validator when leaving a phase that produces them.

        Findings land in `state.validator_findings`; the PM reads them on the next
        turn and may fire a Loop B instead of advancing on a lie.
        """
        if leaving_phase == Phase.DATA_PREPARATION:
            findings = validate_phase_3_artifacts(self.state)
        elif leaving_phase == Phase.MODELING:
            findings = validate_phase_4_models(self.state)
        else:
            return
        self.state.validator_findings = findings
        if findings:
            self.state.append_log(
                "orchestrator",
                f"validator found {len(findings)} deficit(s) leaving phase "
                f"{int(leaving_phase)}: {'; '.join(findings)}",
                level="warn",
            )

    def _advance_substep(self) -> bool:
        """Advance to the next substep / phase. Return True when the run is done."""
        self._sync_phase_substep()
        phase = self.state.phase
        subs = SUBSTEPS[phase]
        i = subs.index(self.state.substep)
        if i + 1 < len(subs):
            self.state.substep = subs[i + 1]
            return False
        # end of this phase -> validate artifacts, then advance to next phase
        self._validate_on_transition(phase)
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

    def _can_fire_loop(self, plan: Plan) -> bool:
        if self._caps_exceeded():
            return False
        if plan.loop_label == "B" and self._inner_loop_count >= MAX_INNER_LOOP_ITERATIONS:
            return False
        target = plan.loop_to_phase
        if target is None:
            return False
        if self._phase_visits.get(target, 0) >= MAX_VISITS_PER_PHASE:
            return False
        return True

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

    def _sync_phase_substep(self) -> None:
        """Recover when PM loop_back leaves substep and phase inconsistent."""
        phase = self.state.phase
        subs = SUBSTEPS[phase]
        if self.state.substep in subs:
            return
        try:
            derived = int(self.state.substep.split(".", 1)[0])
        except (ValueError, AttributeError):
            derived = int(phase)
        target = Phase(derived)
        if target != phase and self.state.substep in SUBSTEPS.get(target, []):
            self.state.append_log(
                "orchestrator",
                f"substep {self.state.substep} out of sync with phase {int(phase)}; "
                f"syncing phase to {derived}",
                level="warn",
            )
            self.state.phase = target
            return
        self.state.append_log(
            "orchestrator",
            f"substep {self.state.substep} invalid for phase {int(phase)}; "
            f"resetting to {subs[0]}",
            level="warn",
        )
        self.state.substep = subs[0]

    def _deployment_review_pending(self) -> bool:
        """True while Phase 6 still owes substep 6.4 (experience documentation)."""
        return (
            self.state.phase == Phase.DEPLOYMENT
            and not self.state.dep.experience_documentation
        )

    def _force_halt(self, reason: str) -> None:
        self.state.halted = True
        self.state.halt_reason = reason
        self.state.append_log("orchestrator", reason, level="warn")
