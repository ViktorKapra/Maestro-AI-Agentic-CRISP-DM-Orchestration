"""Fixed baseline Python snippets for DE/DS/Developer fallback execution.

Each snippet is a self-contained script that prints a single JSON line to stdout.
Token placeholders (``__TRAIN__``, ``__TARGET__``, etc.) are substituted at runtime
by ``agents._run_snippet``.
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
def read_table(path):
    return pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path)
train = read_table(r"__TRAIN__"); test = read_table(r"__TEST__")
os.makedirs(r"__OUTDIR__", exist_ok=True)
tp = os.path.join(r"__OUTDIR__", "train.parquet")
sp = os.path.join(r"__OUTDIR__", "test.parquet")
train.to_parquet(tp); test.to_parquet(sp)
print(json.dumps({"train": tp, "test": sp, "n_train": int(len(train)), "n_test": int(len(test)),
                  "derived": [], "dropped": []}))
'''

_IO_UTILS = '''
def read_table(path):
    import pandas as pd
    return pd.read_parquet(path) if str(path).endswith(".parquet") else pd.read_csv(path)
'''

_CLEAN_SRC = _IO_UTILS + '''
import pandas as pd, json, os
os.makedirs(r"__OUTDIR__", exist_ok=True)
tr = read_table(r"__TRAIN_IN__"); te = read_table(r"__TEST_IN__")
target = "__TARGET__"
missing_before = {c: int(tr[c].isna().sum()) for c in tr.columns}
if "Age" in tr.columns:
    med = float(tr["Age"].median())
    tr["Age"] = tr["Age"].fillna(med); te["Age"] = te["Age"].fillna(med)
if "Fare" in tr.columns:
    med = float(tr["Fare"].median())
    tr["Fare"] = tr["Fare"].fillna(med); te["Fare"] = te["Fare"].fillna(med)
if "Embarked" in tr.columns:
    mode = tr["Embarked"].mode()
    fill = str(mode.iloc[0]) if len(mode) else "S"
    tr["Embarked"] = tr["Embarked"].fillna(fill); te["Embarked"] = te["Embarked"].fillna(fill)
missing_after = {c: int(tr[c].isna().sum()) for c in tr.columns}
tp = os.path.join(r"__OUTDIR__", "train_clean.parquet")
sp = os.path.join(r"__OUTDIR__", "test_clean.parquet")
tr.to_parquet(tp); te.to_parquet(sp)
print(json.dumps({"train_out": tp, "test_out": sp, "missing_before": missing_before,
                  "missing_after": missing_after, "operations": ["median/mode imputation"]}))
'''

_CONSTRUCT_SRC = _IO_UTILS + '''
import pandas as pd, json, os
os.makedirs(r"__OUTDIR__", exist_ok=True)
tr = read_table(r"__TRAIN_IN__"); te = read_table(r"__TEST_IN__")
derived = []
if "SibSp" in tr.columns and "Parch" in tr.columns:
    for df in (tr, te):
        df["FamilySize"] = df["SibSp"].fillna(0) + df["Parch"].fillna(0) + 1
        df["IsAlone"] = (df["FamilySize"] == 1).astype(int)
    derived = ["FamilySize", "IsAlone"]
tp = os.path.join(r"__OUTDIR__", "train_constructed.parquet")
sp = os.path.join(r"__OUTDIR__", "test_constructed.parquet")
tr.to_parquet(tp); te.to_parquet(sp)
print(json.dumps({"train_out": tp, "test_out": sp, "derived": derived}))
'''

_INTEGRATE_SRC = _IO_UTILS + '''
import pandas as pd, json, os
os.makedirs(r"__OUTDIR__", exist_ok=True)
tr = read_table(r"__TRAIN_IN__"); te = read_table(r"__TEST_IN__")
tp = os.path.join(r"__OUTDIR__", "train_integrated.parquet")
sp = os.path.join(r"__OUTDIR__", "test_integrated.parquet")
tr.to_parquet(tp); te.to_parquet(sp)
print(json.dumps({"train_out": tp, "test_out": sp,
                  "train_rows": int(len(tr)), "test_rows": int(len(te)),
                  "columns_train": list(tr.columns), "columns_test": list(te.columns)}))
'''

_FORMAT_SRC = _IO_UTILS + '''
import pandas as pd, json, os
tr = read_table(r"__TRAIN_IN__"); te = read_table(r"__TEST_IN__")
target = "__TARGET__"; idc = "__ID__"
dropped = []
for col in ("Name", "Ticket", "Cabin"):
    if col in tr.columns:
        dropped.append(col)
        tr = tr.drop(columns=[col])
        te = te.drop(columns=[col], errors="ignore")
os.makedirs(r"__OUTDIR__", exist_ok=True)
tp = os.path.join(r"__OUTDIR__", "train.parquet")
sp = os.path.join(r"__OUTDIR__", "test.parquet")
tr.to_parquet(tp); te.to_parquet(sp)
derived = [c for c in tr.columns if c not in read_table(r"__SOURCE_TRAIN__").columns and c not in (target, idc)]
print(json.dumps({"train": tp, "test": sp, "n_train": int(len(tr)), "n_test": int(len(te)),
                  "derived": derived, "dropped": dropped}))
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

_NLP_TRAIN_SRC = '''
import pandas as pd, json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, StratifiedKFold
train = pd.read_parquet(r"__TRAIN__")
target = "__TARGET__"
text_col = "__TEXT_COL__"
y = train[target]
X = train[text_col].fillna("").astype(str)
pipe = Pipeline([
    ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
    ("clf", LogisticRegression(max_iter=1000, random_state=0)),
])
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
scores = cross_val_score(pipe, X, y, cv=cv, scoring="__METRIC__")
print(json.dumps({"technique": "tfidf_logreg", "cv_score": float(scores.mean()),
                  "cv_std": float(scores.std()), "n_features": 5000}))
'''

_NLP_SUBMIT_SRC = '''
import pandas as pd, json
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
train = pd.read_parquet(r"__TRAIN__"); test = pd.read_parquet(r"__TEST__")
target = "__TARGET__"; idc = "__ID__"; text_col = "__TEXT_COL__"
y = train[target]
Xtr = train[text_col].fillna("").astype(str)
Xte = test[text_col].fillna("").astype(str)
pipe = Pipeline([
    ("tfidf", TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
    ("clf", LogisticRegression(max_iter=1000, random_state=0)),
])
pipe.fit(Xtr, y)
preds = pipe.predict(Xte)
sub = pd.DataFrame({idc: test[idc], target: preds.astype(int)})
sample = pd.read_csv(r"__SAMPLE__")
assert list(sub.columns) == list(sample.columns)
assert len(sub) == len(sample)
sub.to_csv(r"__OUT__", index=False)
print(json.dumps({"submission_path": r"__OUT__", "rows": int(len(sub))}))
'''


def primary_text_column(feature_hints: dict) -> str | None:
    """Return the main free-text column from config feature_hints, if any."""
    for key in ("text_free", "text"):
        cols = feature_hints.get(key)
        if isinstance(cols, list) and cols:
            return str(cols[0])
    return None


def is_nlp_case(feature_hints: dict) -> bool:
    """True when the competition is NLP-primary (e.g. disaster tweets), not tabular-with-text."""
    text = primary_text_column(feature_hints)
    if not text:
        return False
    tabular_keys = ("numeric_with_missing", "categorical", "ordinal", "high_missing")
    return not any(feature_hints.get(k) for k in tabular_keys)
