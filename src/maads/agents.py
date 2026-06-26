"""Agent adapters — CrewAI-backed layer over capability modules."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from maads.crews.developer_crew.developer_crew import DeveloperCrew
from maads.crews.data_engineer_crew.data_engineer_crew import DataEngineerCrew
from maads.crews.data_scientist_crew.data_scientist_crew import DataScientistCrew
from maads.crews.domain_crew.domain_crew import DomainCrew
from maads.crews.pm_crew.pm_crew import PMCrew
from maads.crews.storyteller_crew.storyteller_crew import StorytellerCrew
from maads.crew import CrewKickoffError, run_json_task, run_text_task  # test patch targets
from maads.deltas import Plan, StateDelta
from maads.state import CrispDMState
from maads.tools import FileIO, PythonExec

from maads.capabilities.data_engineer import apply_response as _apply_data_engineer_response
from maads.capabilities.data_engineer import execution_evidence as _de_execution_evidence
from maads.capabilities.data_scientist import apply_response as _apply_data_scientist_response
from maads.capabilities.data_scientist import execution_evidence as _ds_execution_evidence
from maads.capabilities.shared import execution_authoritative
from maads.capabilities.developer import (
    build_submission,
    experience_review,
)
from maads.capabilities.storyteller import (
    apply_response as _apply_storyteller_response,
    render_final_report_step,
)
from maads.capabilities.domain import (
    apply_refine_goals,
    apply_situation,
    apply_understanding,
)


def _coerce_phase(value: Any) -> int | None:
    """Coerce an LLM-supplied loop target to an int phase (1-6), or None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 6 else None
    m = re.search(r"[1-6]", str(value))
    return int(m.group()) if m else None


def _tools(artifact_dir: Path) -> tuple[FileIO, PythonExec]:
    return FileIO(artifact_dir), PythonExec(workdir=artifact_dir / "sandbox")


class ProjectManagerAgent:
    name = "pm"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)
        self._crew = PMCrew()

    def plan(self, state: CrispDMState) -> Plan:
        try:
            data = self._crew.kickoff_decision(state, self.artifact_dir)
        except (CrewKickoffError, RuntimeError) as exc:
            return Plan(action="halt", reason=f"PM LLM call failed: {exc}")
        if data:
            action = data.get("action")
            if action in {"advance", "loop_back", "halt"}:
                loop_label = data.get("loop_label")
                if loop_label in ("null", "None", ""):
                    loop_label = None
                return Plan(
                    action=action,
                    target_substep=data.get("target_substep") or None,
                    loop_label=loop_label,
                    loop_to_phase=_coerce_phase(data.get("loop_to_phase")),
                    reason=str(data.get("reason", "")),
                )
        return Plan(action="halt", reason="PM returned unusable JSON directive")

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s == "1.4":
            state.bu.project_plan = [
                "Understand the problem and data",
                "Prepare data",
                "Build and evaluate a model",
                "Produce a Kaggle submission",
            ]
            state.bu.initial_assessment_of_tools_and_techniques = {
                "framework": "CrewAI",
                "modeling": "scikit-learn baseline",
            }
            return StateDelta(["bu.project_plan", "bu.initial_assessment_of_tools_and_techniques"])
        if s == "5.2":
            data = self._crew.kickoff_substep(s, state, self.artifact_dir) or {}
            review = data.get("review_of_process")
            if review:
                state.ev.review_of_process = str(review)
            else:
                loops = len(state.loop_history)
                deg = len(state.degraded_flags)
                state.ev.review_of_process = (
                    f"Completed CRISP-DM run with {loops} loop(s) and {deg} degraded step(s)."
                )
            return StateDelta(["ev.review_of_process"])
        if s == "5.3":
            data = self._crew.kickoff_substep(s, state, self.artifact_dir) or {}
            actions = data.get("list_of_possible_actions")
            if isinstance(actions, list):
                state.ev.list_of_possible_actions = [str(a) for a in actions]
            decision = data.get("decision")
            if decision:
                state.ev.decision = str(decision)
            elif not state.ev.decision:
                state.ev.decision = "deploy"
            return StateDelta(["ev.list_of_possible_actions", "ev.decision"])
        return StateDelta(notes=f"PM no-op for {s}")


class DomainExpertAgent:
    name = "domain"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)
        self._crew = DomainCrew()

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s == "1.1":
            data = self._crew.kickoff_substep(s, state, self.artifact_dir) or {}
            return apply_understanding(data, state)
        if s == "1.2":
            data = self._crew.kickoff_substep(s, state, self.artifact_dir) or {}
            return apply_situation(data, state)
        if s == "1.3":
            data = self._crew.kickoff_substep(s, state, self.artifact_dir) or {}
            return apply_refine_goals(data, state)
        return StateDelta(notes=f"Domain no-op for {s}")


_DE_OWNED_SUBSTEPS = {"2.1", "2.2", "2.4", "3.1", "3.2", "3.3", "3.4", "3.5"}
_DE_EXECUTION_SUBSTEPS = {"2.1", "2.2", "2.4", "3.2", "3.3", "3.4", "3.5"}


class DataEngineerAgent:
    name = "data_engineer"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)
        self._crew = DataEngineerCrew()

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s not in _DE_OWNED_SUBSTEPS:
            return StateDelta(notes=f"DE no-op for {s}")

        execution: dict[str, Any] = {}
        try:
            execution = _de_execution_evidence(
                self.pyexec, state, s, self.artifact_dir,
            )
        except RuntimeError as exc:
            return StateDelta(notes=f"DE {s} execution failed: {exc}", failed=True)

        if s in _DE_EXECUTION_SUBSTEPS and not execution:
            return StateDelta(notes=f"DE {s}: no execution evidence produced", failed=True)

        if s in _DE_EXECUTION_SUBSTEPS and execution_authoritative(
            execution, s, "data_engineer",
        ):
            return _apply_data_engineer_response({}, state, s, execution)

        try:
            data = self._crew.kickoff_substep(
                s, state, self.artifact_dir, execution_evidence=execution or None,
            ) or {}
        except CrewKickoffError as exc:
            return StateDelta(notes=f"DE {s} LLM failed: {exc}", failed=True)
        except RuntimeError as exc:
            return StateDelta(notes=f"DE {s} runtime error: {exc}", failed=True)
        return _apply_data_engineer_response(data, state, s, execution)


_DS_OWNED_SUBSTEPS = {"2.3", "4.1", "4.2", "4.3", "4.4", "5.1"}
_DS_EXECUTION_SUBSTEPS = {"2.3", "4.3", "4.4"}


class DataScientistAgent:
    name = "data_scientist"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)
        self._crew = DataScientistCrew()

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s not in _DS_OWNED_SUBSTEPS:
            return StateDelta(notes=f"DS no-op for {s}")

        execution: dict[str, Any] = {}
        try:
            execution = _ds_execution_evidence(
                self.pyexec, state, s, self.artifact_dir,
            )
        except RuntimeError as exc:
            return StateDelta(notes=f"DS {s} execution failed: {exc}", failed=True)

        if s in _DS_EXECUTION_SUBSTEPS and not execution:
            return StateDelta(notes=f"DS {s}: no execution evidence produced", failed=True)

        if s in _DS_EXECUTION_SUBSTEPS and execution_authoritative(
            execution, s, "data_scientist",
        ):
            return _apply_data_scientist_response({}, state, s, execution)

        try:
            data = self._crew.kickoff_substep(
                s, state, self.artifact_dir, execution_evidence=execution or None,
            ) or {}
        except CrewKickoffError as exc:
            return StateDelta(notes=f"DS {s} LLM failed: {exc}", failed=True)
        except RuntimeError as exc:
            return StateDelta(notes=f"DS {s} runtime error: {exc}", failed=True)
        return _apply_data_scientist_response(data, state, s, execution)


class DeveloperAgent:
    name = "developer"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)
        self._crew = DeveloperCrew()

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s == "6.1":
            try:
                return build_submission(self.pyexec, state, self.artifact_dir)
            except (RuntimeError, CrewKickoffError) as exc:
                return StateDelta(notes=f"Developer 6.1 submission failed: {exc}", failed=True)
        if s == "6.4":
            return experience_review(state)
        return StateDelta(notes=f"Developer no-op for {s}")


_STORYTELLER_OWNED_SUBSTEPS = {"6.2", "6.3"}


class StorytellerAgent:
    name = "storyteller"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)
        self._crew = StorytellerCrew()

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s not in _STORYTELLER_OWNED_SUBSTEPS:
            return StateDelta(notes=f"Storyteller no-op for {s}")
        if s == "6.3":
            return render_final_report_step(state, self.artifact_dir)
        try:
            data = self._crew.kickoff_substep(s, state, self.artifact_dir) or {}
        except CrewKickoffError as exc:
            return StateDelta(notes=f"Storyteller {s} LLM failed: {exc}", failed=True)
        except RuntimeError as exc:
            return StateDelta(notes=f"Storyteller {s} runtime error: {exc}", failed=True)
        return _apply_storyteller_response(data, state, s, self.artifact_dir)
