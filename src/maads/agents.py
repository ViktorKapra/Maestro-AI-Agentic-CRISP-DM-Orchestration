"""The five agents — CrewAI-backed wrappers over the kept scaffold spine.

The deprecated `Agent` ABC is gone. Each agent is an independent class (no
inheritance) exposing the two methods the orchestrator calls:

    plan(state) -> Plan          # only the PM plans in the hub-and-spoke design
    act(state)  -> StateDelta    # does the work for the CURRENT state.substep

Phase 1 split:
    - PM and Domain Expert call the LLM (via maads.crew.run_json_task).
    - Data Engineer / Data Scientist / Developer run a FIXED pandas+sklearn
      baseline through PythonExec (agent-generated code is Phase 2).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from maads.crew import run_json_task
from maads.prompts import PM_DECISION_INSTRUCTION
from maads.state import CrispDMState, ModelRun
from maads.tools import FileIO, PythonExec


# ── Decisions / deltas ──────────────────────────────────────────────────────

@dataclass
class Plan:
    """What the PM decides to do next."""
    action: str  # "act" | "skip" | "request_loop_back"
    target_substep: str | None = None
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


def _abspath(rel: str) -> str:
    """Resolve a config-relative data path to an absolute string for snippets."""
    return str(Path(rel).resolve())


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
        """Real LLM decision; deterministic fallback only on unparseable output."""
        data = run_json_task(
            self.name, PM_DECISION_INSTRUCTION, state,
            schema_hint='{"action":"act|skip|request_loop_back","target_substep":str|null,'
                        '"loop_to_phase":int|null,"reason":str}',
        )
        if data and data.get("action") in {"act", "skip", "request_loop_back"}:
            return Plan(
                action=data["action"],
                target_substep=data.get("target_substep") or state.substep,
                loop_to_phase=data.get("loop_to_phase"),
                reason=str(data.get("reason", "")),
            )
        # Output unusable -> proceed with the current substep (resilience, not a
        # design bypass; the LLM was still consulted).
        return Plan(action="act", target_substep=state.substep, reason="fallback: act current")

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

class DomainExpertAgent:
    name = "domain"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        cfg = state.config
        if s == "1.1":
            data = run_json_task(
                self.name,
                "State the project background, the business objective, and a measurable "
                "business success criterion for this problem.",
                state,
                schema_hint='{"background":str,"business_objectives":str,"business_success_criteria":str}',
            ) or {}
            state.bu.background = data.get("background") or cfg.problem_statement
            state.bu.business_objectives = (
                data.get("business_objectives")
                or f"Predict {cfg.target_column} as accurately as possible."
            )
            state.bu.business_success_criteria = (
                data.get("business_success_criteria")
                or f"{cfg.success_criterion.metric} >= {cfg.success_criterion.threshold}"
            )
            return StateDelta(["bu.background", "bu.business_objectives", "bu.business_success_criteria"])
        if s == "1.2":
            state.bu.inventory_of_resources = {"data": cfg.data.model_dump()}
            state.bu.requirements_assumptions_constraints = {
                "metric": cfg.evaluation_metric, "problem_type": cfg.problem_type,
            }
            return StateDelta(["bu.inventory_of_resources", "bu.requirements_assumptions_constraints"])
        if s == "1.3":
            data = run_json_task(
                self.name,
                "Translate the business objective into a concrete data-mining goal and a "
                "measurable data-mining success criterion.",
                state,
                schema_hint='{"data_mining_goals":str,"data_mining_success_criteria":str}',
            ) or {}
            state.bu.data_mining_goals = (
                data.get("data_mining_goals")
                or f"Train a {cfg.problem_type} model for {cfg.target_column}."
            )
            state.bu.data_mining_success_criteria = (
                data.get("data_mining_success_criteria")
                or f"cross-validated {cfg.evaluation_metric} >= {cfg.success_criterion.threshold}"
            )
            return StateDelta(["bu.data_mining_goals", "bu.data_mining_success_criteria"])
        return StateDelta(notes=f"Domain no-op for {s}")


# ── 3. Data Engineer ────────────────────────────────────────────────────────

class DataEngineerAgent:
    name = "data_engineer"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        train = _abspath(state.config.data.train_csv)
        test = _abspath(state.config.data.test_csv)
        if s == "2.1":
            state.du.initial_data_collection_report = _run_snippet(
                self.pyexec, _COLLECT_SRC, __TRAIN__=train, __TEST__=test)
            return StateDelta(["du.initial_data_collection_report"])
        if s == "2.2":
            state.du.data_description_report = _run_snippet(
                self.pyexec, _DESCRIBE_SRC, __TRAIN__=train)
            return StateDelta(["du.data_description_report"])
        if s == "2.4":
            state.du.data_quality_report = {"blockers": [], "tolerable": ["missing values imputed in prep"]}
            return StateDelta(["du.data_quality_report"])
        if s == "3.5":
            info = _run_snippet(
                self.pyexec, _PREP_SRC,
                __TRAIN__=train, __TEST__=test, __OUTDIR__=str(self.artifact_dir.resolve()))
            state.dp.dataset = {"train": info["train"], "test": info["test"]}
            state.dp.dataset_description = f"{info['n_train']} train / {info['n_test']} test rows (parquet)."
            return StateDelta(["dp.dataset", "dp.dataset_description"])
        if s in {"3.1", "3.2", "3.3", "3.4"}:
            state.dp.data_cleaning_report = {"strategy": "median/most-frequent impute, one-hot encode (in pipeline)"}
            return StateDelta(["dp.data_cleaning_report"], notes=f"DE light step {s}")
        return StateDelta(notes=f"DE no-op for {s}")


# ── 4. Data Scientist ───────────────────────────────────────────────────────

class DataScientistAgent:
    name = "data_scientist"

    def __init__(self, *, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir
        self.fileio, self.pyexec = _tools(artifact_dir)

    def act(self, state: CrispDMState) -> StateDelta:
        s = state.substep
        if s == "2.3":
            desc = state.du.data_description_report or {}
            state.du.data_exploration_report = {
                "n_rows": desc.get("n_rows"), "target": state.config.target_column,
            }
            return StateDelta(["du.data_exploration_report"])
        if s == "4.1":
            state.md.modeling_technique = "gradient_boosting"
            state.md.modeling_assumptions = ["tabular features", "no leakage (pipeline fit on train only)"]
            return StateDelta(["md.modeling_technique", "md.modeling_assumptions"])
        if s == "4.2":
            state.md.test_design = {"cv": "stratified_5fold", "metric": state.config.evaluation_metric}
            return StateDelta(["md.test_design"])
        if s == "4.3":
            res = _run_snippet(
                self.pyexec, _TRAIN_SRC,
                __TRAIN__=state.dp.dataset["train"],
                __TARGET__=state.config.target_column, __ID__=state.config.id_column)
            state.md.models.append(ModelRun(
                technique=res["technique"], cv_score=res["cv_score"],
                description=f"{res['n_features']} features, 5-fold CV"))
            return StateDelta(["md.models"])
        if s == "4.4":
            if state.md.models:
                best = max(state.md.models, key=lambda m: m.cv_score or 0.0)
                best.assessment = "selected: best CV score"
                state.md.chosen_model = best
            return StateDelta(["md.chosen_model"])
        if s == "5.1":
            cv = state.md.chosen_model.cv_score if state.md.chosen_model else None
            thr = state.config.success_criterion.threshold
            state.ev.assessment_of_dm_results = {
                "cv_score": cv, "threshold": thr, "meets": bool(cv is not None and cv >= thr),
            }
            if state.md.chosen_model:
                state.ev.approved_models = [state.md.chosen_model]
            return StateDelta(["ev.assessment_of_dm_results", "ev.approved_models"])
        return StateDelta(notes=f"DS no-op for {s}")


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
