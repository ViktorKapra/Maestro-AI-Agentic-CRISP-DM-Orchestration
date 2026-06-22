"""The orchestrator.

Walks the CRISP-DM state machine. Asks the PM for the next move, dispatches
to the owning agent, fires loop contours when the PM says so. Enforces hard
caps so the system can't burn through the token budget.

This file is INTENTIONALLY INCOMPLETE. You implement `run()`. The skeleton
below gives you the shape; the TODO comments tell you what to fill in.
"""
from __future__ import annotations

from pathlib import Path

from maads.agents import (
    Agent,
    DataEngineerAgent,
    DataScientistAgent,
    DeveloperAgent,
    DomainExpertAgent,
    Plan,
    ProjectManagerAgent,
)
from maads.state import CrispDMState, SUBSTEP_OWNER


# Hard caps. Tighten these before the demo; loosen during development.
MAX_PHASE_TRANSITIONS = 12
MAX_VISITS_PER_PHASE = 3
MAX_INNER_LOOP_ITERATIONS = 3  # the 3 ↔ 4 loop specifically


class Orchestrator:
    def __init__(self, state: CrispDMState, artifact_dir: Path) -> None:
        self.state = state
        self.artifact_dir = artifact_dir
        self.pm = ProjectManagerAgent(artifact_dir=artifact_dir)
        self.agents: dict[str, Agent] = {
            "pm": self.pm,
            "domain":         DomainExpertAgent(artifact_dir=artifact_dir),
            "data_engineer":  DataEngineerAgent(artifact_dir=artifact_dir),
            "data_scientist": DataScientistAgent(artifact_dir=artifact_dir),
            "developer":      DeveloperAgent(artifact_dir=artifact_dir),
        }

        # Bookkeeping for the hard caps.
        self._n_transitions = 0
        self._phase_visits: dict[int, int] = {}
        self._inner_loop_count = 0

    def run(self) -> CrispDMState:
        """Walk the state machine until phase 6 completes or a cap is hit.

        TODO: implement the control loop. Suggested shape:

            while not self.state.halted:
                if self._caps_exceeded():
                    self._force_halt("hard cap exceeded")
                    break

                plan: Plan = self.pm.plan(self.state)
                if plan.action == "act":
                    self._dispatch(plan.target_substep)
                elif plan.action == "request_loop_back":
                    self._fire_loop(plan.loop_to_phase, plan.reason)
                elif plan.action == "skip":
                    self._advance_substep()

            return self.state

        Things to get right:
            - Refuse to dispatch a substep whose prereqs aren't satisfied
              (use state.substep_prereqs_satisfied). Log a warning and let
              the PM re-plan instead.
            - Count phase visits and reject loop_back requests that would
              exceed MAX_VISITS_PER_PHASE.
            - Count 3<->4 transitions specifically; cap with MAX_INNER_LOOP_ITERATIONS.
            - Every dispatch and every loop fired should append a LogEntry.
        """
        # TODO: replace this with the real loop.
        self.state.append_log(
            agent="orchestrator",
            message="run() not implemented yet",
            level="warn",
        )
        self.state.halted = True
        self.state.halt_reason = "orchestrator.run() not implemented"
        return self.state

    # ── Helpers you may want; left as TODO stubs ──────────────────────────

    def _dispatch(self, substep: str) -> None:
        """Route a substep to its owning agent, after prereq check."""
        # TODO: look up SUBSTEP_OWNER[substep], call agent.act(self.state),
        # log the StateDelta returned. Refuse + log if prereqs not satisfied.
        raise NotImplementedError

    def _fire_loop(self, target_phase: int, reason: str, label: str = "?") -> None:
        """Record a back-edge to target_phase. `label` is one of A, B, C, D."""
        # TODO: append a LoopEvent via state.record_loop(label, ..., ...),
        # set state.phase, set state.substep to the first substep of
        # target_phase. Increment _inner_loop_count if label == "B" (4 -> 3).
        raise NotImplementedError

    def _advance_substep(self) -> None:
        """Move to the next substep within the current phase, or the next phase."""
        # TODO: find the current substep in SUBSTEPS[phase]; pick the next one.
        # If at end of phase, increment phase and start at its first substep.
        # Increment _n_transitions; track _phase_visits.
        raise NotImplementedError

    def _caps_exceeded(self) -> bool:
        if self._n_transitions >= MAX_PHASE_TRANSITIONS:
            return True
        if any(v > MAX_VISITS_PER_PHASE for v in self._phase_visits.values()):
            return True
        if self._inner_loop_count > MAX_INNER_LOOP_ITERATIONS:
            return True
        return False

    def _force_halt(self, reason: str) -> None:
        self.state.halted = True
        self.state.halt_reason = reason
        self.state.append_log(agent="orchestrator", message=reason, level="warn")
