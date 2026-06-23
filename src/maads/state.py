"""The shared CRISP-DM state.

The state is organised as one nested model per phase, with one field per
output named in the CRISP-DM 1.0 Reference Model "Generic Tasks and Outputs"
diagram. The naming mirrors the spec so an agent's prompt can reference an
output by its canonical name and the team's mental model stays consistent
with the literature.

Two design rules:
    1. Append-only logs. `log`, `loop_history`, and `md.models` only grow.
    2. No agent reads another agent's prompts — they only read state. This
       keeps agents loosely coupled and individually swappable.

When reading or writing state inside an agent prompt, use the
`view_for(agent_name)` helper at the bottom of this file. Sending the
entire state to every LLM call burns the token budget — see
docs/TOKEN_BUDGET.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field

from maads.config import CaseConfig


class Phase(IntEnum):
    BUSINESS_UNDERSTANDING = 1
    DATA_UNDERSTANDING = 2
    DATA_PREPARATION = 3
    MODELING = 4
    EVALUATION = 5
    DEPLOYMENT = 6


# The 24 generic tasks of CRISP-DM 1.0, in canonical order.
SUBSTEPS: dict[Phase, list[str]] = {
    Phase.BUSINESS_UNDERSTANDING: ["1.1", "1.2", "1.3", "1.4"],
    Phase.DATA_UNDERSTANDING:     ["2.1", "2.2", "2.3", "2.4"],
    Phase.DATA_PREPARATION:       ["3.1", "3.2", "3.3", "3.4", "3.5"],
    Phase.MODELING:               ["4.1", "4.2", "4.3", "4.4"],
    Phase.EVALUATION:             ["5.1", "5.2", "5.3"],
    Phase.DEPLOYMENT:             ["6.1", "6.2", "6.3", "6.4"],
}


SUBSTEP_NAMES: dict[str, str] = {
    "1.1": "Determine Business Objectives",
    "1.2": "Assess Situation",
    "1.3": "Determine Data Mining Goals",
    "1.4": "Produce Project Plan",
    "2.1": "Collect Initial Data",
    "2.2": "Describe Data",
    "2.3": "Explore Data",
    "2.4": "Verify Data Quality",
    "3.1": "Select Data",
    "3.2": "Clean Data",
    "3.3": "Construct Data",
    "3.4": "Integrate Data",
    "3.5": "Format Data",
    "4.1": "Select Modeling Technique",
    "4.2": "Generate Test Design",
    "4.3": "Build Model",
    "4.4": "Assess Model",
    "5.1": "Evaluate Results",
    "5.2": "Review Process",
    "5.3": "Determine Next Steps",
    "6.1": "Plan Deployment",
    "6.2": "Plan Monitoring and Maintenance",
    "6.3": "Produce Final Report",
    "6.4": "Review Project",
}


SUBSTEP_OWNER: dict[str, str] = {
    # Phase 1 — Business Understanding
    "1.1": "domain", "1.2": "domain", "1.3": "domain", "1.4": "pm",
    # Phase 2 — Data Understanding
    "2.1": "data_engineer", "2.2": "data_engineer",
    "2.3": "data_scientist",  # data_engineer also contributes
    "2.4": "data_engineer",
    # Phase 3 — Data Preparation
    "3.1": "data_engineer", "3.2": "data_engineer",
    "3.3": "data_engineer", "3.4": "data_engineer", "3.5": "data_engineer",
    # Phase 4 — Modeling
    "4.1": "data_scientist", "4.2": "data_scientist",
    "4.3": "data_scientist", "4.4": "data_scientist",
    # Phase 5 — Evaluation
    "5.1": "data_scientist", "5.2": "pm", "5.3": "pm",
    # Phase 6 — Deployment
    "6.1": "developer", "6.2": "developer",
    "6.3": "developer", "6.4": "developer",
}


# ── Cross-cutting log + loop types ──────────────────────────────────────────

class LogEntry(BaseModel):
    t: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agent: str
    level: str = "info"  # "info" | "warn" | "error"
    message: str
    data: dict[str, Any] | None = None


class LoopEvent(BaseModel):
    t: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    from_phase: int
    to_phase: int
    label: str   # "A" | "B" | "C" | "D" — matching the four loops in the README
    reason: str


class ModelRun(BaseModel):
    technique: str
    parameter_settings: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    cv_score: float | None = None
    holdout_score: float | None = None
    assessment: str | None = None
    revised_parameter_settings: dict[str, Any] | None = None


# ── Phase 1 — Business Understanding ───────────────────────────────────────

class BusinessUnderstanding(BaseModel):
    # 1.1 Determine Business Objectives
    background: str | None = None
    business_objectives: str | None = None
    business_success_criteria: str | None = None
    # 1.2 Assess Situation
    inventory_of_resources: dict[str, Any] | None = None
    requirements_assumptions_constraints: dict[str, Any] | None = None
    risks_and_contingencies: list[str] = Field(default_factory=list)
    terminology: dict[str, str] = Field(default_factory=dict)
    costs_and_benefits: dict[str, Any] | None = None
    # 1.3 Determine Data Mining Goals
    data_mining_goals: str | None = None
    data_mining_success_criteria: str | None = None
    # 1.4 Produce Project Plan
    project_plan: list[str] = Field(default_factory=list)
    initial_assessment_of_tools_and_techniques: dict[str, Any] | None = None


# ── Phase 2 — Data Understanding ───────────────────────────────────────────

class DataUnderstanding(BaseModel):
    initial_data_collection_report: dict[str, Any] | None = None  # 2.1
    data_description_report: dict[str, Any] | None = None         # 2.2
    data_exploration_report: dict[str, Any] | None = None         # 2.3
    data_quality_report: dict[str, Any] | None = None             # 2.4


# ── Phase 3 — Data Preparation ─────────────────────────────────────────────

class DataPreparation(BaseModel):
    rationale_for_inclusion_exclusion: dict[str, Any] | None = None  # 3.1
    data_cleaning_report: dict[str, Any] | None = None               # 3.2
    derived_attributes: dict[str, Any] | None = None                   # 3.3
    generated_records: dict[str, Any] | None = None                  # 3.3
    merged_data: dict[str, Any] | None = None                        # 3.4
    reformatted_data: dict[str, Any] | None = None                   # 3.5
    # Phase-level outputs
    dataset: dict[str, str] = Field(default_factory=dict)   # role -> path
    dataset_description: str | None = None


# ── Phase 4 — Modeling ─────────────────────────────────────────────────────

class Modeling(BaseModel):
    modeling_technique: str | None = None                       # 4.1
    modeling_assumptions: list[str] = Field(default_factory=list)  # 4.1
    test_design: dict[str, Any] | None = None                   # 4.2
    # 4.3 & 4.4 captured per-run.
    models: list[ModelRun] = Field(default_factory=list)
    chosen_model: ModelRun | None = None


# ── Phase 5 — Evaluation ───────────────────────────────────────────────────

class Evaluation(BaseModel):
    assessment_of_dm_results: dict[str, Any] | None = None      # 5.1
    approved_models: list[ModelRun] = Field(default_factory=list)
    review_of_process: str | None = None                        # 5.2
    list_of_possible_actions: list[str] = Field(default_factory=list)  # 5.3
    decision: str | None = None


# ── Phase 6 — Deployment ───────────────────────────────────────────────────

class Deployment(BaseModel):
    deployment_plan: str | None = None                          # 6.1
    monitoring_and_maintenance_plan: str | None = None          # 6.2
    final_report_path: str | None = None                        # 6.3
    final_presentation_path: str | None = None                  # 6.3
    experience_documentation: str | None = None                 # 6.4
    submission_path: str | None = None


# ── Top-level state ────────────────────────────────────────────────────────

class CrispDMState(BaseModel):
    case_id: str
    config: CaseConfig

    phase: Phase = Phase.BUSINESS_UNDERSTANDING
    substep: str = "1.1"
    loop_history: list[LoopEvent] = Field(default_factory=list)
    halted: bool = False
    halt_reason: str | None = None

    bu: BusinessUnderstanding = Field(default_factory=BusinessUnderstanding)
    du: DataUnderstanding = Field(default_factory=DataUnderstanding)
    dp: DataPreparation = Field(default_factory=DataPreparation)
    md: Modeling = Field(default_factory=Modeling)
    ev: Evaluation = Field(default_factory=Evaluation)
    dep: Deployment = Field(default_factory=Deployment)

    log: list[LogEntry] = Field(default_factory=list)
    token_spend: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_config(cls, config: CaseConfig) -> "CrispDMState":
        return cls(case_id=config.case_id, config=config)

    # ── Mutators agents should use ────────────────────────────────────────

    def append_log(self, agent: str, message: str,
                   level: str = "info", data: dict | None = None) -> None:
        self.log.append(LogEntry(agent=agent, level=level,
                                 message=message, data=data))

    def record_loop(self, label: str, from_phase: int,
                    to_phase: int, reason: str) -> None:
        self.loop_history.append(LoopEvent(
            label=label, from_phase=from_phase, to_phase=to_phase, reason=reason
        ))

    def add_tokens(self, agent: str, n_tokens: int) -> None:
        self.token_spend[agent] = self.token_spend.get(agent, 0) + n_tokens

    # ── Prerequisite checks the orchestrator uses ─────────────────────────

    def substep_prereqs_satisfied(self, substep: str) -> bool:
        """Return True iff the prerequisites for `substep` are filled.

        This is the anti-phase-jumping rule. Extend it as agents produce
        more outputs.
        """
        if substep == "1.3" and self.bu.business_objectives is None:
            return False
        if substep == "1.4" and self.bu.data_mining_goals is None:
            return False
        if substep == "2.3" and self.du.data_description_report is None:
            return False
        if substep == "3.1" and self.du.data_quality_report is None:
            return False
        if substep == "4.1" and not self.dp.dataset:
            return False
        if substep == "4.4" and not self.md.models:
            return False
        if substep == "5.1" and not self.md.models:
            return False
        if substep == "6.1" and self.md.chosen_model is None:
            return False
        if substep == "6.3" and self.dep.submission_path is None:
            return False
        return True

    # ── Token-economy views (see docs/TOKEN_BUDGET.md) ────────────────────

    def view_for(self, agent_name: str) -> dict[str, Any]:
        """Minimal slice of state to send to an agent's prompt.

        DO NOT serialise the whole state object into a prompt. Always
        send the smallest view that lets the agent do its substep.
        """
        base = {
            "case_id": self.case_id,
            "phase": int(self.phase),
            "substep": self.substep,
            "substep_name": SUBSTEP_NAMES.get(self.substep, "?"),
            "config": {
                "problem_statement": self.config.problem_statement,
                "problem_type": self.config.problem_type,
                "target_column": self.config.target_column,
                "evaluation_metric": self.config.evaluation_metric,
            },
        }
        if agent_name == "pm":
            base["loop_history"] = [le.model_dump() for le in self.loop_history]
            base["recent_log"] = _trim_log(self.log, n=8)
            base["latest_quality_blockers"] = _quality_blockers(self.du.data_quality_report)
            base["latest_model_assessment"] = _latest_model_assessment(self.md)
            base["outputs_status"] = _pm_outputs_status(self)
            assessment = self.ev.assessment_of_dm_results or {}
            base["business_goal_met"] = bool(assessment.get("meets"))
        elif agent_name == "domain":
            base["bu"] = self.bu.model_dump(exclude_none=True)
            base["du_so_far"] = self.du.model_dump(exclude_none=True)
            base["feature_hints"] = self.config.feature_hints
        elif agent_name == "data_engineer":
            base["raw_data_paths"] = self.config.data.model_dump()
            base["data_mining_goals"] = self.bu.data_mining_goals
            base["du_so_far"] = self.du.model_dump(exclude_none=True)
            base["dp_so_far"] = self.dp.model_dump(exclude_none=True)
        elif agent_name == "data_scientist":
            base["data_mining_goals"] = self.bu.data_mining_goals
            base["dataset"] = self.dp.dataset
            base["data_description_report"] = self.du.data_description_report
            base["recent_models"] = [m.model_dump() for m in self.md.models[-3:]]
            base["test_design"] = self.md.test_design
        elif agent_name == "developer":
            base["chosen_model"] = (
                self.md.chosen_model.model_dump() if self.md.chosen_model else None
            )
            base["dataset"] = self.dp.dataset
            base["sample_submission_csv"] = self.config.data.sample_submission_csv
            base["data_description_report"] = self.du.data_description_report
        return base


def next_substep(state: "CrispDMState") -> str | None:
    """Return the substep after `state.substep`, or None past 6.4."""
    phase = state.phase
    subs = SUBSTEPS[phase]
    i = subs.index(state.substep)
    if i + 1 < len(subs):
        return subs[i + 1]
    next_phase = int(phase) + 1
    if next_phase > int(Phase.DEPLOYMENT):
        return None
    return SUBSTEPS[Phase(next_phase)][0]


def _pm_outputs_status(state: "CrispDMState") -> dict[str, bool]:
    bu, du, dp, md, ev, dep = state.bu, state.du, state.dp, state.md, state.ev, state.dep
    phase_4_model_ok = any(
        m.cv_score is not None and m.assessment for m in md.models
    )
    return {
        "phase_1_ready": bool(
            bu.business_objectives
            and bu.business_success_criteria
            and bu.data_mining_goals
            and bu.project_plan
        ),
        "phase_2_ready": bool(
            du.data_description_report
            and du.data_exploration_report
            and du.data_quality_report
        ),
        "phase_3_ready": bool(dp.dataset),
        "phase_4_ready": bool(phase_4_model_ok and md.chosen_model),
        "phase_5_ready": bool(
            ev.assessment_of_dm_results and ev.review_of_process and ev.decision
        ),
        "phase_6_ready": bool(
            dep.submission_path
            and dep.final_report_path
            and dep.experience_documentation
        ),
    }


# ── Helpers used by view_for ───────────────────────────────────────────────

def _trim_log(log: list[LogEntry], n: int = 8) -> list[dict]:
    """Return the last n log entries with messages truncated."""
    out = []
    for e in log[-n:]:
        out.append({
            "agent": e.agent,
            "level": e.level,
            "message": e.message[:200],
        })
    return out


def _quality_blockers(report: dict | None) -> list[str]:
    if not report:
        return []
    return list(report.get("blockers", []))


def _latest_model_assessment(md: Modeling) -> dict | None:
    if not md.models:
        return None
    last = md.models[-1]
    return {
        "technique": last.technique,
        "cv_score": last.cv_score,
        "assessment": last.assessment,
    }
