"""The five agents — CrewAI-backed wrappers over the kept scaffold spine.

The deprecated `Agent` ABC is gone. Each agent is an independent class (no
inheritance) exposing the two methods the orchestrator calls:

    plan(state) -> Plan          # only the PM plans in the hub-and-spoke design
    act(state)  -> StateDelta    # does the work for the CURRENT state.substep

Phase 1 split:
    - PM and Domain Expert call the LLM (via maads.crew.run_json_task).
    - Data Engineer and Data Scientist call the LLM with execution evidence from baseline snippets.
    - Developer runs a FIXED pandas+sklearn baseline through PythonExec for deployment.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maads.baselines import (
    _COLLECT_SRC,
    _DESCRIBE_SRC,
    _EXPLORE_SRC,
    _PREP_SRC,
    _QUALITY_SRC,
    _SUBMIT_SRC,
    _TRAIN_SRC,
)
from maads.codegen import run_authored_code
from maads.crew import CrewKickoffError, run_json_task
from maads.paths import resolve_path
from maads.prompts import PM_DECISION_INSTRUCTION
from maads.prompts.identities.data_engineer import format_data_engineer_task
from maads.prompts.identities.data_scientist import format_data_scientist_task
from maads.prompts.identities.domain import format_domain_understanding_task
from maads.state import CrispDMState, ModelRun
from maads.tools import FileIO, PythonExec


# ── Decisions / deltas ──────────────────────────────────────────────────────

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


def _coerce_phase(value: Any) -> int | None:
    """Coerce an LLM-supplied loop target to an int phase (1-6), or None.

    Models routinely return the phase as a string ("1") or a label
    ("Phase 1"); `Phase` is an IntEnum, so `Phase("1")` would raise. Normalise
    here so the orchestrator can build `Phase(int)` safely.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1 <= value <= 6 else None
    m = re.search(r"[1-6]", str(value))
    return int(m.group()) if m else None


# ── Shared helpers (composition, not inheritance) ───────────────────────────

def _tools(artifact_dir: Path) -> tuple[FileIO, PythonExec]:
    return FileIO(artifact_dir), PythonExec(workdir=artifact_dir / "sandbox")


def _abspath(rel: str) -> str:
    """Resolve a config-relative data path to an absolute string for snippets."""
    return str(resolve_path(rel))


def _run_snippet(pyexec: PythonExec, src: str, **subs: str) -> dict:
    """Run a fixed snippet (sentinels replaced), return the JSON it prints.

    Fails loudly: a non-zero exit raises with the captured stderr.
    """
    code = src
    for token, value in subs.items():
        code = code.replace(token, value)
    res = pyexec.run(code)
    if not res.ok:
        raise RuntimeError(f"baseline snippet failed:\n{res.stderr.strip()}")
    return json.loads(res.stdout.strip().splitlines()[-1])


# ── 1. Project Manager ──────────────────────────────────────────────────────

class ProjectManagerAgent:
    name = "pm"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)

    def plan(self, state: CrispDMState) -> Plan:
        """Real LLM decision; halt on kickoff failure, fallback only on unparseable JSON."""
        try:
            data = run_json_task(self.name, PM_DECISION_INSTRUCTION, state)
        except (CrewKickoffError, RuntimeError) as exc:
            return Plan(action="halt", reason=f"PM LLM call failed: {exc}")
        action = (data or {}).get("action")
        if action not in {"advance", "loop_back", "halt"}:
            return Plan(action="halt", reason="PM returned unusable JSON directive")
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

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s == "1.4":
            state.bu.project_plan = [
                "Understand the problem and data", "Prepare data",
                "Build and evaluate a model", "Produce a Kaggle submission",
            ]
            state.bu.initial_assessment_of_tools_and_techniques = {
                "framework": "CrewAI", "modeling": "scikit-learn baseline",
            }
            return StateDelta(["bu.project_plan", "bu.initial_assessment_of_tools_and_techniques"])
        if s == "5.2":
            state.ev.review_of_process = "Linear CRISP-DM pass; baseline pipeline; no loops fired."
            return StateDelta(["ev.review_of_process"])
        if s == "5.3":
            state.ev.list_of_possible_actions = ["deploy", "tune features", "try another model"]
            state.ev.decision = "deploy"
            return StateDelta(["ev.list_of_possible_actions", "ev.decision"])
        return StateDelta(notes=f"PM no-op for {s}")


# ── 2. Domain Knowledge Expert ──────────────────────────────────────────────

def _format_success_criterion(sc: dict, cfg) -> str:
    metric = sc.get("metric") or cfg.evaluation_metric
    target = sc.get("target_value")
    direction = sc.get("direction") or "maximize"
    if target is not None and str(target).lower() not in {"null", "none"}:
        return f"{metric} {direction} {target}"
    threshold = cfg.success_criterion.threshold
    return f"{metric} {direction} (threshold {threshold})"


def _apply_domain_understanding(data: dict, state: CrispDMState) -> StateDelta:
    """Map domain_understanding_task JSON into BusinessUnderstanding fields."""
    cfg = state.config
    sit = data.get("situation_assessment") or {}
    sc = data.get("success_criterion") or {}

    state.bu.background = cfg.problem_statement
    state.bu.business_objectives = (
        data.get("business_objectives")
        or f"Predict {cfg.target_column} as accurately as possible."
    )
    state.bu.business_success_criteria = _format_success_criterion(sc, cfg)

    state.bu.inventory_of_resources = {
        "resources": sit.get("resources", []),
        "data": cfg.data.model_dump(),
        "domain_artifacts": {
            "data_description_notes": data.get("data_description_notes", []),
            "feature_hints": data.get("feature_hints", []),
            "domain_data_quality_flags": data.get("domain_data_quality_flags", []),
            "loop_a_recommendation": data.get("loop_a_recommendation"),
        },
    }
    state.bu.requirements_assumptions_constraints = {
        "requirements": sit.get("requirements", []),
        "assumptions": sit.get("assumptions", []) + data.get("assumptions", []),
        "constraints": sit.get("constraints", []),
        "open_questions": data.get("open_questions", []),
        "metric": cfg.evaluation_metric,
        "problem_type": cfg.problem_type,
    }
    state.bu.risks_and_contingencies = sit.get("risks", [])
    state.bu.terminology = {
        t["term"]: t["meaning"]
        for t in sit.get("terminology", [])
        if isinstance(t, dict) and t.get("term")
    }
    state.bu.costs_and_benefits = {
        "costs_or_tradeoffs": sit.get("costs_or_tradeoffs", []),
        "expected_benefits": sit.get("expected_benefits", []),
    }

    state.bu.data_mining_goals = (
        data.get("data_mining_goal")
        or f"Train a {cfg.problem_type} model for {cfg.target_column}."
    )
    state.bu.data_mining_success_criteria = _format_success_criterion(sc, cfg)

    return StateDelta([
        "bu.background",
        "bu.business_objectives",
        "bu.business_success_criteria",
        "bu.inventory_of_resources",
        "bu.requirements_assumptions_constraints",
        "bu.risks_and_contingencies",
        "bu.terminology",
        "bu.costs_and_benefits",
        "bu.data_mining_goals",
        "bu.data_mining_success_criteria",
    ])


class DomainExpertAgent:
    name = "domain"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)

    def _run_domain_understanding(self, state: CrispDMState) -> StateDelta:
        instruction, schema_hint = format_domain_understanding_task(state)
        data = run_json_task(self.name, instruction, state, schema_hint=schema_hint) or {}
        return _apply_domain_understanding(data, state)

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s == "1.1":
            return self._run_domain_understanding(state)
        if s == "1.2":
            return StateDelta(notes="1.2 covered by domain understanding at 1.1")
        if s == "1.3":
            if state.du.data_quality_report:
                return self._run_domain_understanding(state)
            return StateDelta(notes="1.3 covered by domain understanding at 1.1")
        return StateDelta(notes=f"Domain no-op for {s}")


# ── Shared act() for the execution-evidence agents (DE, DS) ─────────────────

def _evidence_backed_act(
    agent: Any,
    state: CrispDMState,
    owned: set[str],
    evidence_fn: Any,
    format_fn: Any,
    apply_fn: Any,
) -> StateDelta:
    """The common cycle DE and DS share for an owned substep.

    Author and run the substep's code for measured evidence (self-debug +
    fallback live in `run_authored_code`), ask the LLM to narrate/enrich it, then
    map the merged result into state. "Measured execution wins" is enforced
    inside each `apply_fn`. Agents that don't own the substep no-op.
    """
    s = state.substep
    if s not in owned:
        return StateDelta(notes=f"{agent.name} no-op for {s}")

    execution: dict[str, Any] = {}
    try:
        execution = evidence_fn(agent.pyexec, state, s, agent.artifact_dir)
    except RuntimeError:
        pass

    instruction, schema_hint = format_fn(
        state, agent.artifact_dir, execution_evidence=execution or None,
    )
    try:
        data = run_json_task(agent.name, instruction, state, schema_hint=schema_hint) or {}
    except (CrewKickoffError, RuntimeError):
        data = {}
    return apply_fn(data, state, s, execution)


# ── 3. Data Engineer ────────────────────────────────────────────────────────

_DE_OWNED_SUBSTEPS = {"2.1", "2.2", "2.4", "3.1", "3.2", "3.3", "3.4", "3.5"}


def _has_keys(payload: dict, *keys: str) -> list[str]:
    """Contract helper: report any missing keys."""
    return [f"missing key '{k}'" for k in keys if k not in payload]


def _de_execution_evidence(
    pyexec: PythonExec,
    state: CrispDMState,
    substep: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Have the Data Engineer author and run the code for its owned substep.

    Returns measured evidence in the shape `_apply_data_engineer_response`
    expects. Each authored attempt self-debugs (codegen.run_authored_code) and
    falls back to the fixed baseline snippet only when all attempts fail.
    """
    train = _abspath(state.config.data.train_csv)
    test = _abspath(state.config.data.test_csv)
    target = state.config.target_column
    idc = state.config.id_column

    if substep == "2.1":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 2.1 Collect Initial Data: load the train and test "
                        "CSVs and report a brief collection summary.",
            header_vars={"TRAIN_CSV": train, "TEST_CSV": test},
            contract=lambda p: _has_keys(p, "train_rows", "test_rows", "columns"),
            contract_hint="Required keys: train_rows (int), test_rows (int), columns (list).",
            fallback=lambda: _run_snippet(pyexec, _COLLECT_SRC, __TRAIN__=train, __TEST__=test),
            fallback_code=_COLLECT_SRC,
        )
        return {"initial_data_collection_report": res.payload}

    if substep == "2.2":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 2.2 Describe Data: profile the training data — "
                        "row/column counts, dtypes, missing counts, cardinality.",
            header_vars={"TRAIN_CSV": train},
            contract=lambda p: _has_keys(p, "n_rows", "n_cols", "columns", "dtypes", "missing"),
            contract_hint="Required keys: n_rows, n_cols, columns, dtypes, missing (per-column).",
            fallback=lambda: _run_snippet(pyexec, _DESCRIBE_SRC, __TRAIN__=train),
            fallback_code=_DESCRIBE_SRC,
        )
        return {"data_description_report": res.payload}

    if substep == "2.4":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM 2.4 Verify Data Quality: inspect the training data "
                        "and list genuine quality BLOCKERS (e.g. >40% missing, constant "
                        "columns, missing target) vs tolerable issues. Compute from the data.",
            header_vars={"TRAIN_CSV": train, "TARGET": target},
            contract=lambda p: _has_keys(p, "blockers", "tolerable"),
            contract_hint="Required keys: blockers (list of strings), tolerable (list of strings).",
            fallback=lambda: _run_snippet(pyexec, _QUALITY_SRC, __TRAIN__=train, __TARGET__=target),
            fallback_code=_QUALITY_SRC,
        )
        return {"data_quality_report": res.payload}

    if substep == "3.5":
        outdir = str(artifact_dir.resolve())
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_engineer", state=state,
            instruction="CRISP-DM Data Preparation (3.1-3.5): produce a model-ready "
                        "dataset. Clean (impute missing), construct useful derived "
                        "features, drop leakage/identifier columns, and write "
                        "train.parquet and test.parquet into OUTDIR. Keep TARGET in train "
                        "and ID_COL in test. Apply identical transforms to train and test.",
            header_vars={
                "TRAIN_CSV": train, "TEST_CSV": test, "OUTDIR": outdir,
                "TARGET": target, "ID_COL": idc,
            },
            contract=lambda p: (
                _has_keys(p, "train", "test", "n_train", "n_test")
                or ([] if int(p.get("n_train", 0)) > 0 else ["n_train must be > 0"])
            ),
            contract_hint="Required keys: train (parquet path), test (parquet path), "
                          "n_train (int>0), n_test (int), derived (list), dropped (list).",
            fallback=lambda: _run_snippet(
                pyexec, _PREP_SRC, __TRAIN__=train, __TEST__=test, __OUTDIR__=outdir,
            ),
            fallback_code=_PREP_SRC,
        )
        info = res.payload
        n_derived = len(info.get("derived") or [])
        return {
            "dataset": {"train": info["train"], "test": info["test"]},
            "dataset_description": (
                f"{info.get('n_train')} train / {info.get('n_test')} test rows (parquet); "
                f"{n_derived} derived feature(s)"
                + (" [degraded: baseline fallback]" if res.degraded else "")
            ),
            "derived": info.get("derived") or [],
            "dropped": info.get("dropped") or [],
            "degraded": res.degraded,
        }
    return {}


def _apply_data_engineer_response(
    data: dict,
    state: CrispDMState,
    substep: str,
    execution: dict[str, Any],
) -> StateDelta:
    """Map data-engineer JSON (or execution fallback) into shared state."""
    su = (data or {}).get("state_updates") or {}
    du = su.get("du") or {}
    dp = su.get("dp") or {}
    fields: list[str] = []

    if substep == "2.1":
        report = du.get("initial_data_collection_report") or execution.get(
            "initial_data_collection_report",
        )
        if report:
            state.du.initial_data_collection_report = report
            fields.append("du.initial_data_collection_report")
    elif substep == "2.2":
        report = du.get("data_description_report") or execution.get("data_description_report")
        if report:
            state.du.data_description_report = report
            fields.append("du.data_description_report")
    elif substep == "2.4":
        # Measured execution wins: real blockers must not be masked by an empty fallback.
        report = execution.get("data_quality_report") or du.get("data_quality_report")
        if report:
            state.du.data_quality_report = report
            fields.append("du.data_quality_report")
    elif substep == "3.1":
        rationale = dp.get("rationale_for_inclusion_exclusion") or execution.get(
            "rationale_for_inclusion_exclusion",
        )
        if rationale:
            state.dp.rationale_for_inclusion_exclusion = rationale
            fields.append("dp.rationale_for_inclusion_exclusion")
    elif substep == "3.2":
        # The actual cleaning runs in the authored prep code at 3.5; here record the
        # DE's described strategy without fabricating a specific one if absent.
        report = dp.get("data_cleaning_report") or execution.get("data_cleaning_report")
        if report:
            state.dp.data_cleaning_report = report
            fields.append("dp.data_cleaning_report")
    elif substep == "3.3":
        derived = dp.get("derived_attributes") or execution.get("derived_attributes")
        if derived is not None:
            if isinstance(derived, list):
                derived = derived[0] if len(derived) == 1 else {"items": derived}
            state.dp.derived_attributes = derived
            fields.append("dp.derived_attributes")
        generated = dp.get("generated_records") or execution.get("generated_records")
        if generated is not None:
            state.dp.generated_records = generated
            fields.append("dp.generated_records")
    elif substep == "3.4":
        merged = dp.get("merged_data") or execution.get("merged_data")
        if merged is not None:
            state.dp.merged_data = merged
            fields.append("dp.merged_data")
    elif substep == "3.5":
        # Measured execution wins: dataset paths and derived features come from the
        # code that actually ran, not from LLM prose.
        dataset = execution.get("dataset") or dp.get("dataset")
        description = execution.get("dataset_description") or dp.get("dataset_description")
        if dataset:
            state.dp.dataset = dataset
            fields.append("dp.dataset")
        if description:
            state.dp.dataset_description = description
            fields.append("dp.dataset_description")
        derived = execution.get("derived")
        if derived:
            state.dp.derived_attributes = {"items": derived}
            fields.append("dp.derived_attributes")
        if execution.get("degraded"):
            state.dp.reformatted_data = {"degraded": True, "reason": "DE prep fell back to baseline"}
            fields.append("dp.reformatted_data")

    summary = (data or {}).get("summary", "")
    return StateDelta(fields, notes=summary or f"DE completed {substep}")


class DataEngineerAgent:
    name = "data_engineer"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)

    def act(self, state: CrispDMState) -> StateDelta:
        return _evidence_backed_act(
            self, state, _DE_OWNED_SUBSTEPS,
            _de_execution_evidence, format_data_engineer_task,
            _apply_data_engineer_response,
        )


# ── 4. Data Scientist ───────────────────────────────────────────────────────

_DS_OWNED_SUBSTEPS = {"2.3", "4.1", "4.2", "4.3", "4.4", "5.1"}


def _ds_execution_evidence(
    pyexec: PythonExec,
    state: CrispDMState,
    substep: str,
    artifact_dir: Path | None = None,  # unused; kept for a uniform evidence_fn signature
) -> dict[str, Any]:
    """Have the Data Scientist author and run the code for its owned substep."""
    train = _abspath(state.config.data.train_csv)
    target = state.config.target_column

    if substep == "2.3":
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_scientist", state=state,
            instruction="CRISP-DM 2.3 Explore Data: probe the training data to inform "
                        "modeling — target balance, feature/target relationships, "
                        "notable distributions. Compute from the data, do not guess.",
            header_vars={"TRAIN_CSV": train, "TARGET": target},
            contract=lambda p: _has_keys(p, "n_rows", "target"),
            contract_hint="Required keys: n_rows (int), target (str); add any findings "
                          "(e.g. target_distribution, correlations).",
            fallback=lambda: _run_snippet(pyexec, _EXPLORE_SRC, __TRAIN__=train, __TARGET__=target),
            fallback_code=_EXPLORE_SRC,
        )
        return {"data_exploration_report": res.payload}

    if substep == "4.3":
        dataset_train = state.dp.dataset.get("train")
        if not dataset_train:
            return {}
        idc = state.config.id_column
        res = run_authored_code(
            pyexec=pyexec, agent_name="data_scientist", state=state,
            instruction="CRISP-DM 4.3 Build Model: read the prepared parquet at "
                        "TRAIN_PARQUET, choose a suitable scikit-learn classifier and "
                        "feature set yourself, and evaluate it with stratified k-fold "
                        "cross-validation on the configured metric. Drop TARGET and "
                        "ID_COL from the features.",
            header_vars={"TRAIN_PARQUET": dataset_train, "TARGET": target, "ID_COL": idc},
            contract=lambda p: (
                _has_keys(p, "technique", "cv_score")
                or ([] if isinstance(p.get("cv_score"), (int, float)) else ["cv_score must be numeric"])
            ),
            contract_hint="Required keys: technique (str), cv_score (float), n_features (int).",
            fallback=lambda: _run_snippet(
                pyexec, _TRAIN_SRC, __TRAIN__=dataset_train, __TARGET__=target, __ID__=idc,
            ),
            fallback_code=_TRAIN_SRC,
        )
        p = res.payload
        return {
            "model_run": {
                "technique": p.get("technique") or "unspecified",
                "cv_score": p.get("cv_score"),
                "cv_std": p.get("cv_std"),
                "description": f"{p.get('n_features', '?')} features, CV"
                               + (" [degraded: baseline fallback]" if res.degraded else ""),
                "parameter_settings": p.get("parameter_settings") or {},
            },
            "degraded": res.degraded,
        }
    return {}


def _apply_data_scientist_response(
    data: dict,
    state: CrispDMState,
    substep: str,
    execution: dict[str, Any],
) -> StateDelta:
    """Map data-scientist JSON (or execution fallback) into shared state."""
    su = (data or {}).get("state_updates") or {}
    du = su.get("du") or {}
    md = su.get("md") or {}
    ev = su.get("ev") or {}
    fields: list[str] = []

    if substep == "2.3":
        report = (
            du.get("data_exploration_report")
            or execution.get("data_exploration_report")
        )
        if not report:
            desc = state.du.data_description_report or {}
            report = {"n_rows": desc.get("n_rows"), "target": state.config.target_column}
        state.du.data_exploration_report = report
        fields.append("du.data_exploration_report")
    elif substep == "4.1":
        # The DS's stated intent; the authoritative technique is whatever its 4.3
        # code actually trains (recorded on the ModelRun below).
        state.md.modeling_technique = md.get("modeling_technique") or "to be chosen at 4.3"
        state.md.modeling_assumptions = md.get("modeling_assumptions") or [
            "tabular features", "no leakage (pipeline fit on train only)",
        ]
        fields.extend(["md.modeling_technique", "md.modeling_assumptions"])
    elif substep == "4.2":
        state.md.test_design = md.get("test_design") or {
            "cv": "stratified_5fold",
            "metric": state.config.evaluation_metric,
        }
        fields.append("md.test_design")
    elif substep == "4.3":
        # Measured execution wins: technique and cv_score come from the code the DS
        # actually ran, not from LLM prose (which may only enrich the description).
        run = dict(execution.get("model_run") or {})
        llm_run = md.get("model_run") or {}
        if llm_run.get("description"):
            run["description"] = llm_run["description"]
        if not run:
            run = llm_run
        technique = run.get("technique") or "unspecified"
        state.md.models.append(ModelRun(
            technique=technique,
            cv_score=run.get("cv_score"),
            description=run.get("description") or "model run",
            parameter_settings=run.get("parameter_settings") or {},
        ))
        # Reflect the actually-trained technique back onto the phase-level field.
        state.md.modeling_technique = technique
        fields.extend(["md.models", "md.modeling_technique"])
    elif substep == "4.4":
        if state.md.models:
            best = max(state.md.models, key=lambda m: m.cv_score or 0.0)
            chosen = md.get("chosen_model_technique")
            if chosen:
                for m in state.md.models:
                    if m.technique == chosen:
                        best = m
                        break
            best.assessment = md.get("assessment") or "selected: best CV score"
            state.md.chosen_model = best
            fields.append("md.chosen_model")
    elif substep == "5.1":
        cv = state.md.chosen_model.cv_score if state.md.chosen_model else None
        thr = state.config.success_criterion.threshold
        state.ev.assessment_of_dm_results = ev.get("assessment_of_dm_results") or {
            "cv_score": cv,
            "threshold": thr,
            "meets": bool(cv is not None and cv >= thr),
        }
        fields.append("ev.assessment_of_dm_results")
        if state.md.chosen_model:
            state.ev.approved_models = [state.md.chosen_model]
            fields.append("ev.approved_models")

    summary = (data or {}).get("summary", "")
    return StateDelta(fields, notes=summary or f"DS completed {substep}")


class DataScientistAgent:
    name = "data_scientist"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)

    def act(self, state: CrispDMState) -> StateDelta:
        return _evidence_backed_act(
            self, state, _DS_OWNED_SUBSTEPS,
            _ds_execution_evidence, format_data_scientist_task,
            _apply_data_scientist_response,
        )


# ── 5. Developer ────────────────────────────────────────────────────────────

class DeveloperAgent:
    name = "developer"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s == "6.1":
            out = str((self.artifact_dir / "submission.csv").resolve())
            info = _run_snippet(
                self.pyexec, _SUBMIT_SRC,
                __TRAIN__=state.dp.dataset["train"], __TEST__=state.dp.dataset["test"],
                __TARGET__=state.config.target_column, __ID__=state.config.id_column,
                __SAMPLE__=_abspath(state.config.data.sample_submission_csv), __OUT__=out)
            state.dep.submission_path = info["submission_path"]
            state.dep.deployment_plan = "Refit on full train, predict test, write submission.csv."
            return StateDelta(["dep.submission_path", "dep.deployment_plan"])
        if s == "6.2":
            state.dep.monitoring_and_maintenance_plan = "Re-run on data refresh; watch CV vs leaderboard gap."
            return StateDelta(["dep.monitoring_and_maintenance_plan"])
        if s == "6.3":
            lines = [
                f"# Final report — {state.case_id}",
                f"- Technique: {state.md.modeling_technique}",
                f"- CV score: {state.md.chosen_model.cv_score if state.md.chosen_model else 'n/a'}",
                f"- Submission: {state.dep.submission_path}",
            ]
            path = self.fileio.write_text("final_report.md", "\n".join(lines))
            state.dep.final_report_path = str(path)
            return StateDelta(["dep.final_report_path"])
        if s == "6.4":
            state.dep.experience_documentation = "Phase 1 vertical slice: fixed baseline, no loops."
            return StateDelta(["dep.experience_documentation"])
        return StateDelta(notes=f"Developer no-op for {s}")
