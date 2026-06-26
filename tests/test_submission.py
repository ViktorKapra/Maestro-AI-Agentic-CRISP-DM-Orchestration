"""Tests for Developer agent-authored submission at 6.1."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from maads.capabilities.developer import build_submission
from maads.config import load_case_config
from maads.paths import resolve_path
from maads.state import CrispDMState, ModelRun
from maads.tools import PythonExec


@pytest.fixture
def house_prices_state(tmp_path: Path) -> CrispDMState:
    train_csv = Path("data/house_prices/train.csv")
    test_csv = Path("data/house_prices/test.csv")
    if not train_csv.exists():
        pytest.skip("house_prices data not present")
    cfg = load_case_config(resolve_path("configs/house_prices.yaml"))
    state = CrispDMState.from_config(cfg)
    train = pd.read_csv(train_csv).head(120)
    test = pd.read_csv(test_csv).head(120)
    train_p = tmp_path / "train.parquet"
    test_p = tmp_path / "test.parquet"
    sample_p = tmp_path / "sample_submission.csv"
    train.to_parquet(train_p, index=False)
    test.to_parquet(test_p, index=False)
    pd.DataFrame({"Id": test["Id"], "SalePrice": 0.0}).to_csv(sample_p, index=False)
    state.dp.dataset = {"train": str(train_p), "test": str(test_p)}
    state.md.chosen_model = ModelRun(
        technique="gradient_boosting",
        cv_score=0.14,
        description="test model",
    )
    state.config.data.sample_submission_csv = str(sample_p)
    return state


_REGRESSION_SUBMIT = '''```python
import json
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import GradientBoostingRegressor
train = pd.read_parquet(TRAIN_PARQUET)
test = pd.read_parquet(TEST_PARQUET)
target = TARGET
idc = ID_COL
y = np.log1p(train[target]) if "log" in EVAL_METRIC.lower() else train[target]
X = train.drop(columns=[c for c in (target, idc) if c in train.columns])
num = X.select_dtypes(include="number").columns.tolist()
cat = X.select_dtypes(include="object").columns.tolist()
pre = ColumnTransformer([
    ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num),
    ("cat", Pipeline([("imp", SimpleImputer(strategy="constant", fill_value="missing")), ("oh", OneHotEncoder(handle_unknown="ignore"))]), cat),
])
pipe = Pipeline([("pre", pre), ("gb", GradientBoostingRegressor(random_state=0))])
feats = num + cat
pipe.fit(X[feats], y)
preds = pipe.predict(test.reindex(columns=feats, fill_value=0))
if "log" in EVAL_METRIC.lower():
    preds = np.expm1(preds)
sub = pd.DataFrame({idc: test[idc], target: preds.astype(float)})
sub.to_csv(OUTPUT_PATH, index=False)
print(json.dumps({"submission_path": OUTPUT_PATH, "rows": int(len(sub))}))
```'''


@patch("maads.crew.run_text_task", return_value=_REGRESSION_SUBMIT)
def test_build_submission_uses_developer_authored_code(
    _mock_llm,
    house_prices_state: CrispDMState,
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "run"
    artifact_dir.mkdir()
    delta = build_submission(PythonExec(workdir=artifact_dir), house_prices_state, artifact_dir)
    assert "dep.submission_path" in delta.fields_written
    assert house_prices_state.dep.submission_path
    sub = pd.read_csv(house_prices_state.dep.submission_path)
    assert list(sub.columns) == ["Id", "SalePrice"]
    assert len(sub) == 120
