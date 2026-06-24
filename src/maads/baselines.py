"""Fixed baseline code snippets — the last-resort fallbacks for DE/DS/developer.

These run through ``PythonExec`` (see ``maads.agents._run_snippet``) only when an
agent's authored code fails repeatedly; ``__TOKEN__`` sentinels are replaced with
concrete paths/columns at call time. They are deliberately fixed (see docs/plan.md)
and kept out of agents.py so the agent control flow reads cleanly.
"""
from __future__ import annotations

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

_QUALITY_SRC = '''
import pandas as pd, json
df = pd.read_csv(r"__TRAIN__")
target = "__TARGET__"
blockers = []; tolerable = []
for c in df.columns:
    miss = float(df[c].isna().mean())
    if miss > 0.4:
        blockers.append(c + ": %.0f%% missing" % (miss * 100))
    elif miss > 0:
        tolerable.append(c + ": %.0f%% missing (imputable)" % (miss * 100))
    if int(df[c].nunique(dropna=True)) <= 1:
        blockers.append(c + ": constant column")
if bool(df.duplicated().any()):
    tolerable.append(str(int(df.duplicated().sum())) + " duplicate rows")
if target in df.columns and bool(df[target].isna().any()):
    blockers.append(target + ": target has missing values")
print(json.dumps({"blockers": blockers, "tolerable": tolerable}))
'''

_PREP_SRC = '''
import pandas as pd, json, os
train = pd.read_csv(r"__TRAIN__"); test = pd.read_csv(r"__TEST__")
os.makedirs(r"__OUTDIR__", exist_ok=True)
tp = os.path.join(r"__OUTDIR__", "train.parquet")
sp = os.path.join(r"__OUTDIR__", "test.parquet")
train.to_parquet(tp); test.to_parquet(sp)
print(json.dumps({"train": tp, "test": sp, "n_train": int(len(train)), "n_test": int(len(test)),
                  "derived": [], "dropped": []}))
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
