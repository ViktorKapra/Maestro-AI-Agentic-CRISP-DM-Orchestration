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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from maads.crew import CrewKickoffError, run_json_task
from maads.prompts import PM_DECISION_INSTRUCTION
from maads.prompts.identities.data_engineer import format_data_engineer_task
from maads.prompts.identities.data_scientist import format_data_scientist_task
from maads.prompts.identities.domain import format_domain_understanding_task
from maads.state import CrispDMState, ModelRun, next_substep
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


# ── Shared helpers (composition, not inheritance) ───────────────────────────

def _tools(artifact_dir: Path) -> tuple[FileIO, PythonExec]:
    return FileIO(artifact_dir), PythonExec(workdir=artifact_dir / "sandbox")


from maads.paths import resolve_path


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


# ── Fixed baseline snippets (Phase 1) ───────────────────────────────────────

_PIPE_HELPER = '''
def build_pipeline(X):
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    from sklearn.ensemble import GradientBoostingClassifier
    num = X.select_dtypes(include="number").columns.tolist()
    cat = [c for c in X.select_dtypes(exclude="number").columns if X[c].nunique() <= 20]
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")), ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat),
    ])
    pipe = Pipeline([("pre", pre), ("gb", GradientBoostingClassifier(random_state=0))])
    return pipe, num + cat
'''

_COLLECT_SRC = '''
import pandas as pd, json
tr = pd.read_csv(r"__TRAIN__"); te = pd.read_csv(r"__TEST__")
print(json.dumps({"train_rows": int(len(tr)), "test_rows": int(len(te)), "columns": list(tr.columns)}))
'''

_DESCRIBE_SRC = '''
import pandas as pd, json
df = pd.read_csv(r"__TRAIN__")
print(json.dumps({
    "n_rows": int(len(df)), "n_cols": int(df.shape[1]),
    "columns": list(df.columns),
    "dtypes": {c: str(t) for c, t in df.dtypes.items()},
    "missing": {c: int(df[c].isna().sum()) for c in df.columns},
    "n_unique": {c: int(df[c].nunique()) for c in df.columns},
}))
'''

_EXPLORE_SRC = '''
import pandas as pd, json
df = pd.read_csv(r"__TRAIN__")
target = "__TARGET__"
out = {"n_rows": int(len(df)), "target": target}
if target in df.columns:
    out["target_distribution"] = {str(k): int(v) for k, v in df[target].value_counts().items()}
    out["target_missing"] = int(df[target].isna().sum())
print(json.dumps(out))
'''

_PREP_SRC = '''
import pandas as pd, json, os
train = pd.read_csv(r"__TRAIN__"); test = pd.read_csv(r"__TEST__")
os.makedirs(r"__OUTDIR__", exist_ok=True)
tp = os.path.join(r"__OUTDIR__", "train.parquet")
sp = os.path.join(r"__OUTDIR__", "test.parquet")
train.to_parquet(tp); test.to_parquet(sp)
print(json.dumps({"train": tp, "test": sp, "n_train": int(len(train)), "n_test": int(len(test))}))
'''

_TRAIN_SRC = _PIPE_HELPER + '''
import pandas as pd, json
from sklearn.model_selection import cross_val_score, StratifiedKFold
train = pd.read_parquet(r"__TRAIN__")
target = "__TARGET__"; idc = "__ID__"
y = train[target]
X = train.drop(columns=[c for c in (target, idc) if c in train.columns])
pipe, feats = build_pipeline(X)
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
scores = cross_val_score(pipe, X[feats], y, cv=cv, scoring="accuracy")
print(json.dumps({"technique": "gradient_boosting", "cv_score": float(scores.mean()),
                  "cv_std": float(scores.std()), "n_features": int(len(feats))}))
'''

_SUBMIT_SRC = _PIPE_HELPER + '''
import pandas as pd, json
train = pd.read_parquet(r"__TRAIN__"); test = pd.read_parquet(r"__TEST__")
target = "__TARGET__"; idc = "__ID__"
y = train[target]
X = train.drop(columns=[c for c in (target, idc) if c in train.columns])
pipe, feats = build_pipeline(X)
pipe.fit(X[feats], y)
Xt = test.reindex(columns=feats, fill_value=0)
preds = pipe.predict(Xt)
sub = pd.DataFrame({idc: test[idc], target: preds.astype(int)})
sample = pd.read_csv(r"__SAMPLE__")
assert list(sub.columns) == list(sample.columns), "columns %s != %s" % (list(sub.columns), list(sample.columns))
assert len(sub) == len(sample), "rows %d != %d" % (len(sub), len(sample))
sub.to_csv(r"__OUT__", index=False)
print(json.dumps({"submission_path": r"__OUT__", "rows": int(len(sub))}))
'''


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
                    loop_to_phase=data.get("loop_to_phase"),
                    reason=str(data.get("reason", "")),
                )
        return Plan(
            action="halt",
            reason="PM returned unusable JSON directive",
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

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s == "1.1":
            instruction, schema_hint = format_domain_understanding_task(state)
            data = run_json_task(self.name, instruction, state, schema_hint=schema_hint) or {}
            return _apply_domain_understanding(data, state)
        if s == "1.2":
            return StateDelta(notes="1.2 covered by domain understanding at 1.1")
        if s == "1.3":
            if state.du.data_quality_report:
                instruction, schema_hint = format_domain_understanding_task(state)
                data = run_json_task(self.name, instruction, state, schema_hint=schema_hint) or {}
                return _apply_domain_understanding(data, state)
            return StateDelta(notes="1.3 covered by domain understanding at 1.1")
        return StateDelta(notes=f"Domain no-op for {s}")


# ── 3. Data Engineer ────────────────────────────────────────────────────────

_DE_OWNED_SUBSTEPS = {"2.1", "2.2", "2.4", "3.1", "3.2", "3.3", "3.4", "3.5"}


def _de_execution_evidence(
    pyexec: PythonExec,
    state: CrispDMState,
    substep: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Run baseline snippets and return evidence for the LLM contract."""
    train = _abspath(state.config.data.train_csv)
    test = _abspath(state.config.data.test_csv)
    if substep == "2.1":
        return {
            "initial_data_collection_report": _run_snippet(
                pyexec, _COLLECT_SRC, __TRAIN__=train, __TEST__=test,
            ),
        }
    if substep == "2.2":
        return {
            "data_description_report": _run_snippet(
                pyexec, _DESCRIBE_SRC, __TRAIN__=train,
            ),
        }
    if substep == "3.5":
        info = _run_snippet(
            pyexec, _PREP_SRC,
            __TRAIN__=train, __TEST__=test, __OUTDIR__=str(artifact_dir.resolve()),
        )
        return {
            "dataset": {"train": info["train"], "test": info["test"]},
            "dataset_description": (
                f"{info['n_train']} train / {info['n_test']} test rows (parquet)."
            ),
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
        report = du.get("data_quality_report") or execution.get("data_quality_report")
        state.du.data_quality_report = report or {
            "blockers": [],
            "tolerable": ["missing values imputed in prep"],
        }
        fields.append("du.data_quality_report")
    elif substep == "3.1":
        rationale = dp.get("rationale_for_inclusion_exclusion") or execution.get(
            "rationale_for_inclusion_exclusion",
        )
        if rationale:
            state.dp.rationale_for_inclusion_exclusion = rationale
            fields.append("dp.rationale_for_inclusion_exclusion")
    elif substep == "3.2":
        report = dp.get("data_cleaning_report") or execution.get("data_cleaning_report")
        state.dp.data_cleaning_report = report or {
            "strategy": "median/most-frequent impute, one-hot encode (in pipeline)",
        }
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
        dataset = dp.get("dataset") or execution.get("dataset")
        description = dp.get("dataset_description") or execution.get("dataset_description")
        if dataset:
            state.dp.dataset = dataset
            fields.append("dp.dataset")
        if description:
            state.dp.dataset_description = description
            fields.append("dp.dataset_description")

    summary = (data or {}).get("summary", "")
    return StateDelta(fields, notes=summary or f"DE completed {substep}")


class DataEngineerAgent:
    name = "data_engineer"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s not in _DE_OWNED_SUBSTEPS:
            return StateDelta(notes=f"DE no-op for {s}")

        execution: dict[str, Any] = {}
        try:
            execution = _de_execution_evidence(
                self.pyexec, state, s, self.artifact_dir,
            )
        except RuntimeError:
            pass

        instruction, schema_hint = format_data_engineer_task(
            state, self.artifact_dir, execution_evidence=execution or None,
        )
        try:
            data = run_json_task(self.name, instruction, state, schema_hint=schema_hint) or {}
        except (CrewKickoffError, RuntimeError):
            data = {}
        return _apply_data_engineer_response(data, state, s, execution)


# ── 4. Data Scientist ───────────────────────────────────────────────────────

_DS_OWNED_SUBSTEPS = {"2.3", "4.1", "4.2", "4.3", "4.4", "5.1"}


def _ds_execution_evidence(
    pyexec: PythonExec,
    state: CrispDMState,
    substep: str,
) -> dict[str, Any]:
    """Run baseline snippets and return evidence for the LLM contract."""
    train = _abspath(state.config.data.train_csv)
    target = state.config.target_column
    if substep == "2.3":
        return {
            "data_exploration_report": _run_snippet(
                pyexec, _EXPLORE_SRC, __TRAIN__=train, __TARGET__=target,
            ),
        }
    if substep == "4.3":
        dataset_train = state.dp.dataset.get("train")
        if not dataset_train:
            return {}
        res = _run_snippet(
            pyexec, _TRAIN_SRC,
            __TRAIN__=dataset_train,
            __TARGET__=target,
            __ID__=state.config.id_column,
        )
        return {
            "model_run": {
                "technique": res["technique"],
                "cv_score": res["cv_score"],
                "cv_std": res.get("cv_std"),
                "description": f"{res['n_features']} features, 5-fold CV",
                "parameter_settings": {},
            },
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
        state.md.modeling_technique = (
            md.get("modeling_technique") or "gradient_boosting"
        )
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
        run = dict(execution.get("model_run") or {})
        llm_run = md.get("model_run") or {}
        if llm_run.get("description"):
            run["description"] = llm_run["description"]
        if not run:
            run = llm_run
        state.md.models.append(ModelRun(
            technique=run.get("technique") or "gradient_boosting",
            cv_score=run.get("cv_score"),
            description=run.get("description") or "baseline model run",
            parameter_settings=run.get("parameter_settings") or {},
        ))
        fields.append("md.models")
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
        s = state.substep
        if s not in _DS_OWNED_SUBSTEPS:
            return StateDelta(notes=f"DS no-op for {s}")

        execution: dict[str, Any] = {}
        try:
            execution = _ds_execution_evidence(self.pyexec, state, s)
        except RuntimeError:
            pass

        instruction, schema_hint = format_data_scientist_task(
            state, self.artifact_dir, execution_evidence=execution or None,
        )
        try:
            data = run_json_task(self.name, instruction, state, schema_hint=schema_hint) or {}
        except (CrewKickoffError, RuntimeError):
            data = {}
        return _apply_data_scientist_response(data, state, s, execution)


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
