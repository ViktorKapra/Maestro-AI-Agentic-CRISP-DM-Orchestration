"""The five agents.

The `Agent` base class defines the contract every concrete agent implements.
The five concrete agents below are stubs — read the docstrings carefully,
then fill in the `act()` methods. Do NOT change the base-class contract
without reading docs/ARCHITECTURE.md first.

Read docs/TOKEN_BUDGET.md before writing your first prompt — that's where
the cost discipline lives.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from maads.llm import LLM, llm_for
from maads.state import CrispDMState
from maads.tools import FileIO, PythonExec, RAGRetriever


# ── Decisions an agent's plan() can return ─────────────────────────────────

@dataclass
class Plan:
    """What an agent intends to do next, returned by plan() for the PM to read."""
    action: Literal["act", "skip", "request_loop_back"]
    target_substep: str | None = None
    loop_to_phase: int | None = None     # required iff action == request_loop_back
    reason: str = ""


@dataclass
class StateDelta:
    """A description of what an agent changed in state, for logging."""
    fields_written: list[str] = field(default_factory=list)
    notes: str = ""


# ── Base class ─────────────────────────────────────────────────────────────

class Agent(ABC):
    name: str

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.llm: LLM = llm_for(self.name)
        self.fileio = FileIO(artifact_dir)
        self.pyexec = PythonExec(workdir=artifact_dir / "sandbox")

    # The two methods the orchestrator calls.

    @abstractmethod
    def plan(self, state: CrispDMState) -> Plan: ...

    @abstractmethod
    def act(self, state: CrispDMState) -> StateDelta: ...

    # Helper for charging tokens to the right account.
    def _charge(self, state: CrispDMState, n_tokens: int) -> None:
        state.add_tokens(self.name, n_tokens)


# ── 1. Project Manager ────────────────────────────────────────────────────

class ProjectManagerAgent(Agent):
    """Owns phase transitions and the four loop contours (A, B, C, D).

    Implementation notes:
        - plan() should read state and decide one of:
            * advance to the next substep (the normal case)
            * fire one of the four loops:
                Loop A — 2 → 1 (data contradicts business goal)
                Loop B — 4 → 3 (modeling reveals preparation deficit)
                Loop C — 5 → 1 (business success criterion not met)
                Loop D — 6 → 1 (optional outer cycle; stretch goal)
            * halt (success: phase 6 done with a submission, or cap reached)
        - The decision schema: return Plan(action=..., target_substep=...,
          loop_to_phase=..., reason=...).
        - Hard caps you MUST enforce (or the run will burn the token budget):
            * total phase transitions <= 12
            * visits to any single phase <= 3
            * inner loop (Loop B, 4 → 3) iterations <= 3
        - The PM directly writes:
            * 1.4 Produce Project Plan -> state.bu.project_plan
              + state.bu.initial_assessment_of_tools_and_techniques
            * 5.2 Review Process -> state.ev.review_of_process
            * 5.3 Determine Next Steps -> state.ev.list_of_possible_actions
              + state.ev.decision

    Suggested prompt structure (read docs/TOKEN_BUDGET.md first):
        SYSTEM: stable, identical across calls (cache-friendly).
                "You are the Project Manager for a CRISP-DM run. You walk
                 the cycle and fire back-edges when warranted. Output
                 strict JSON."
        USER:   state.view_for("pm") + the question "What is the next action?"
        Response in JSON: {action, target_substep, loop_to_phase, reason}.

    The PM is called most often, so its prompt design dominates cost.
    """
    name = "pm"

    def plan(self, state: CrispDMState) -> Plan:
        # TODO: call self.llm.chat(...) with the PM prompt and parse JSON.
        raise NotImplementedError

    def act(self, state: CrispDMState) -> StateDelta:
        # The PM does not perform substeps directly; the dispatcher routes
        # the current substep to the owning agent. The PM does write 1.4
        # (the project plan) and 5.2/5.3 (review and next steps).
        raise NotImplementedError


# ── 2. Domain Knowledge Expert ─────────────────────────────────────────────

class DomainExpertAgent(Agent):
    """Owns Business Understanding (1.1–1.3) and contributes to Data Understanding.

    Implementation notes:
        - In Phase 1, reads `state.config.problem_statement` and any RAG
          corpus you've built, then writes to `state.bu`: background,
          business_objectives, business_success_criteria, the Phase-1.2
          situation fields, and data_mining_goals +
          data_mining_success_criteria.
        - In Phase 2 (2.1, 2.2 partial), contributes domain context: which
          fields are ordinal-but-look-nominal, which "NA" values mean
          "absence" vs "missing", etc. The hints in `config.feature_hints`
          are a starting point — extend them from RAG, don't just copy them.
        - Use `state.view_for("domain")` to fetch the slice this agent needs
          rather than reading the full state object.
    """
    name = "domain"

    def __init__(self, *, artifact_dir: Path, corpus_dir: Path | None = None) -> None:
        super().__init__(artifact_dir=artifact_dir)
        self.rag = RAGRetriever(corpus_dir or artifact_dir / "rag_corpus")

    def plan(self, state: CrispDMState) -> Plan:
        raise NotImplementedError

    def act(self, state: CrispDMState) -> StateDelta:
        raise NotImplementedError


# ── 3. Data Engineer ───────────────────────────────────────────────────────

class DataEngineerAgent(Agent):
    """Owns Data Understanding (2.1, 2.2, 2.4) and Data Preparation (3.1–3.5).

    Implementation notes:
        - 2.1 Collect Initial Data: load the train/test CSVs declared in
          config.data; write `state.du.initial_data_collection_report`.
        - 2.2 Describe Data: write `state.du.data_description_report` with
          shapes, dtypes, missingness per column, cardinality per column,
          basic statistics. The Domain Expert reads this for later 1.x
          substeps (a back-edge of useful information, not a CRISP-DM loop).
        - 2.4 Verify Data Quality: write `state.du.data_quality_report` with
          {"blockers": [...], "tolerable": [...]}. Non-empty blockers trigger
          Loop A (2 → 1) when the PM reads them.
        - 3.x: every transformation goes through PythonExec. The phase-level
          output of Phase 3 lives at `state.dp.dataset` (a dict mapping role
          to file path: {"train": ".../train.parquet", "test": ".../test.parquet"}).
        - Use sklearn Pipeline objects so the same fit/transform runs in
          training and inference. This prevents leakage.
    """
    name = "data_engineer"

    def plan(self, state: CrispDMState) -> Plan:
        raise NotImplementedError

    def act(self, state: CrispDMState) -> StateDelta:
        raise NotImplementedError


# ── 4. Data Scientist ──────────────────────────────────────────────────────

class DataScientistAgent(Agent):
    """Owns Modeling (4.1–4.4), contributes to Data Understanding (2.3).

    Implementation notes:
        - 2.3 Explore Data: append modelling-lens findings to
          `state.du.data_exploration_report` (target distribution, class
          balance, candidate-feature univariate strength). The Data Engineer
          will have already done schema-level description in 2.2.
        - 4.1 Select Modeling Technique: pick ONE technique from a constrained
          menu and record why in `state.md.modeling_technique` and
          `state.md.modeling_assumptions`. A reasonable starting menu for
          binary_classification:
            ["logistic_regression", "random_forest", "gradient_boosting"]
          For regression:
            ["ridge", "random_forest", "gradient_boosting"]
          For text problems, add the representation choice
          ("tfidf" vs "openai_embeddings") to the prompt.
        - 4.2 Generate Test Design: write `state.md.test_design`. Default:
          stratified 5-fold for classification, plain 5-fold for regression.
        - 4.3 Build Model / 4.4 Assess Model: append a `ModelRun` to
          `state.md.models` for each trial. Fill technique, parameter_settings,
          description, cv_score, assessment.
        - On poor performance, the agent should NOT silently keep trying more
          models. It should write a diagnostic into the last model's
          `assessment` and let the PM fire Loop B (4 → 3) with a concrete
          preparation request (e.g. "need stronger text representation" for
          Disaster Tweets).
    """
    name = "data_scientist"

    def plan(self, state: CrispDMState) -> Plan:
        raise NotImplementedError

    def act(self, state: CrispDMState) -> StateDelta:
        raise NotImplementedError


# ── 5. Developer ───────────────────────────────────────────────────────────

class DeveloperAgent(Agent):
    """Cross-cutting tool development, debugging on-call, and Deployment (6.1-6.4).

    The Developer plays two distinct roles:

    (A) DEVELOPMENT (during Phases 2-5)
        Writes helper Python that other agents need (custom encoders, feature
        builders, integration glue, the production pipeline scaffolding).
        Called by the PM whenever another agent's task requires a piece of
        code beyond a straightforward sklearn-style snippet.

    (B) DEBUGGING (whenever any agent's PythonExec call fails)
        This is the on-call responsibility. Every other agent's failed code
        execution surfaces here. Implement at least:

        1. classify_error(exec_result) -> ErrorClass
           Categorise the failure. Examples of categories and detection:
             - schema_error          stderr contains "KeyError" referencing
                                     a column name; or "no column"
             - shape_mismatch        sklearn's "shape" / "n_features" complaints
             - type_error            "could not convert", "object" coercion
             - leakage_signal        train/test contamination detected
             - lib_version           "module has no attribute" on a known API
             - oom                   "MemoryError"
             - timeout               ExecResult.timed_out is True
             - syntax_error          SyntaxError or IndentationError
             - json_parse            occurred upstream — agent JSON failed validation
             - other                 the catch-all

        2. propose_fix(error_class, code, schema, recent_state) -> str
           Return a corrected version of the offending code. For schema
           errors, consult state.du.data_description_report; for type
           errors, the same plus dtype hints. Keep the fix as small as
           possible — single-purpose, not a rewrite.

        3. re_execute(code, max_attempts=3) -> ExecResult
           Run the proposed fix through PythonExec; on still-failing,
           propose another fix; on three failures, surface as a stuck
           diagnostic so the PM can decide whether to fire Loop B or halt.

        4. repair_json(text, schema_hint) -> dict | None
           When another agent's structured output fails to parse, try a
           single repair pass (strip Markdown fencing, balance braces,
           escape control chars). If that fails, request a re-emission
           with a stricter prompt rather than swallowing the error.

        5. schema_check(code, schema) -> list[str]
           Static pass over a code snippet, returning any column names
           referenced that are NOT in the actual data schema. Run this
           BEFORE re-executing, not after.

    DEPLOYMENT (Phase 6) - in order:

        6.1 Plan Deployment: write `state.dep.deployment_plan` (short text)
            AND produce the actual `submission.csv` from
            `state.md.chosen_model`'s predictions. Validate the schema
            against the competition's `sample_submission.csv` BEFORE
            writing. Fail loudly on mismatch. Store the file path in
            `state.dep.submission_path`.

        6.2 Plan Monitoring and Maintenance: write
            `state.dep.monitoring_and_maintenance_plan` (short text).

        6.3 Produce Final Report: assemble `final_report.md` from the log
            and key state fields; store its path in
            `state.dep.final_report_path`. This is the input to the paper.

        6.4 Review Project: a project review (what worked, what didn't)
            stored in `state.dep.experience_documentation`. If the
            cross-dataset stretch goal is implemented, this feeds the next
            run's RAG corpus (Loop D).

    The Developer is the agent that prevents "five agents each fail in
    their own way" from turning into ten interacting failure modes.
    Without it, every other agent must handle its own errors, and they
    will not handle them as well.
    """
    name = "developer"

    def plan(self, state: CrispDMState) -> Plan:
        raise NotImplementedError

    def act(self, state: CrispDMState) -> StateDelta:
        raise NotImplementedError

    # ── Debugging-toolkit methods. These are part of the Developer's API
    #    and called by other agents (or the orchestrator) when an error
    #    occurs. Stubs follow; implement them as you build the system. ──

    def classify_error(self, exec_result) -> str:
        """Return one of: schema_error, shape_mismatch, type_error,
        leakage_signal, lib_version, oom, timeout, syntax_error,
        json_parse, other.
        """
        raise NotImplementedError

    def propose_fix(self, error_class: str, code: str,
                    schema: dict | None) -> str:
        """Return a corrected version of the failing code."""
        raise NotImplementedError

    def re_execute(self, code: str, max_attempts: int = 3):
        """Re-run, with up to max_attempts proposed fixes. Returns the
        final ExecResult, plus a list of attempts made (for the log)."""
        raise NotImplementedError

    def repair_json(self, text: str, schema_hint: dict | None = None):
        """Try to parse `text` as JSON; if it fails, attempt one repair
        pass; if that fails, return None."""
        raise NotImplementedError

    def schema_check(self, code: str, schema: dict) -> list[str]:
        """Return a list of column names referenced in `code` that are
        not present in `schema`. Used before re_execute."""
        raise NotImplementedError


# ── Optional sixth: Validator ──────────────────────────────────────────────

class ValidatorAgent(Agent):
    """Optional adversarial validator (owns 4.4 and 5.1 if used).

    Mandate: look for a reason to REJECT the modeller's work. Check for:
        - column hallucination (referenced columns not in schema)
        - leakage (target appears in features, scaler fit on test, etc.)
        - submission format issues
        - over-fit signals (huge train-CV gap, suspicious leaderboard delta)

    Only ships if it cannot find a problem.
    """
    name = "validator"

    def plan(self, state: CrispDMState) -> Plan:
        raise NotImplementedError

    def act(self, state: CrispDMState) -> StateDelta:
        raise NotImplementedError
