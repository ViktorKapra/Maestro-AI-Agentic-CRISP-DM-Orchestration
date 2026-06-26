"""Reference assess snippet for evaluation_bundle contract tests (not a runtime fallback)."""
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

ASSESS_SRC = _PIPE_HELPER + '''
import json, os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, precision_recall_fscore_support,
    confusion_matrix, classification_report,
)
train = pd.read_parquet(r"__TRAIN__")
target = "__TARGET__"; idc = "__ID__"
problem_type = "__PROBLEM_TYPE__"
figures_dir = r"__FIGURES_DIR__"
os.makedirs(figures_dir, exist_ok=True)
class_labels = json.loads(r"""__CLASS_LABELS__""")
y = train[target]
X = train.drop(columns=[c for c in (target, idc) if c in train.columns])
pipe, feats = build_pipeline(X)
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
oof_pred = np.zeros(len(y), dtype=int)
cv_scores = []
for tr_idx, va_idx in cv.split(X[feats], y):
    pipe.fit(X[feats].iloc[tr_idx], y.iloc[tr_idx])
    preds = pipe.predict(X[feats].iloc[va_idx])
    oof_pred[va_idx] = preds
    cv_scores.append(float(accuracy_score(y.iloc[va_idx], preds)))
cm = confusion_matrix(y, oof_pred).tolist()
prec, rec, f1, support = precision_recall_fscore_support(y, oof_pred, average=None, zero_division=0)
labels_sorted = sorted(y.unique())
metrics = {
    "accuracy": float(accuracy_score(y, oof_pred)),
    "balanced_accuracy": float(balanced_accuracy_score(y, oof_pred)),
}
for i, lbl in enumerate(labels_sorted):
    key = str(int(lbl))
    name = class_labels.get(key, key)
    metrics[f"precision_{name}"] = float(prec[i])
    metrics[f"recall_{name}"] = float(rec[i])
    metrics[f"f1_{name}"] = float(f1[i])
    metrics[f"support_{name}"] = float(support[i])
warnings = []
vc = y.value_counts(normalize=True)
if len(vc) == 2 and min(vc) < 0.4:
    warnings.append("moderate class imbalance detected")
fig_paths = []
fig, ax = plt.subplots(figsize=(5, 4))
counts = y.value_counts().sort_index()
names = [class_labels.get(str(int(k)), str(k)) for k in counts.index]
ax.bar(names, counts.values)
ax.set_title("Class distribution")
ax.set_ylabel("Count")
p1 = os.path.join(figures_dir, "class_distribution.png")
fig.tight_layout(); fig.savefig(p1); plt.close(fig)
fig_paths.append("figures/class_distribution.png")
fig, ax = plt.subplots(figsize=(5, 4))
im = ax.imshow(cm, cmap="Blues")
ax.set_xticks(range(len(labels_sorted)))
ax.set_yticks(range(len(labels_sorted)))
tick_names = [class_labels.get(str(int(l)), str(int(l))) for l in labels_sorted]
ax.set_xticklabels(tick_names)
ax.set_yticklabels(tick_names)
ax.set_xlabel("Predicted"); ax.set_ylabel("True")
ax.set_title("Confusion matrix (OOF)")
for i in range(len(cm)):
    for j in range(len(cm[i])):
        ax.text(j, i, str(cm[i][j]), ha="center", va="center")
p2 = os.path.join(figures_dir, "confusion_matrix.png")
fig.tight_layout(); fig.savefig(p2); plt.close(fig)
fig_paths.append("figures/confusion_matrix.png")
bundle = {
    "problem_type": problem_type,
    "metrics": metrics,
    "confusion_matrix": cm,
    "class_labels": class_labels,
    "cv": {"mean": float(np.mean(cv_scores)), "std": float(np.std(cv_scores)), "n_folds": 5},
    "figures": fig_paths,
    "warnings": warnings,
}
print(json.dumps({"evaluation_bundle": bundle, "assessment": "OOF evaluation with full classification metrics"}))
'''
