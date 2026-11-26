"""The 15 approved inputs and train-only scikit-learn preprocessing."""

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from response_ml.features import FEATURE_COLUMNS

NUMERIC = (
    "threat_confidence", "triggered_rule_present", "abnormal_feature_count",
    "replay_detected", "risk_score", "evidence_conflict",
)
CATEGORICAL = tuple(key for key in FEATURE_COLUMNS if key not in NUMERIC)


def feature_matrix(rows) -> np.ndarray:
    # Use the allowlist directly. Metadata never enters the returned matrix.
    return np.array([
        [np.nan if getattr(row, name) is None else getattr(row, name) for name in FEATURE_COLUMNS]
        for row in rows
    ], dtype=object)


def make_preprocessor() -> ColumnTransformer:
    categories = Pipeline([
        ("missing", SimpleImputer(strategy="constant", fill_value="__MISSING__", keep_empty_features=True)),
        ("one_hot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])
    numbers = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
    return ColumnTransformer([
        ("numeric", numbers, [FEATURE_COLUMNS.index(name) for name in NUMERIC]),
        ("categorical", categories, [FEATURE_COLUMNS.index(name) for name in CATEGORICAL]),
    ], remainder="drop")


def feature_importance(model: Pipeline) -> dict[str, float]:
    """Sum impurity importances over encoded columns from the same input."""
    preprocessor = model.named_steps["preprocessing"]
    numbers = preprocessor.named_transformers_["numeric"]
    encoder = preprocessor.named_transformers_["categorical"].named_steps["one_hot"]
    names = [
        *NUMERIC,
        *(NUMERIC[index] for index in numbers.indicator_.features_),
        *(field for field, levels in zip(CATEGORICAL, encoder.categories_) for _ in levels),
    ]
    importances = dict.fromkeys(FEATURE_COLUMNS, 0.0)
    for name, value in zip(names, model.named_steps["classifier"].feature_importances_, strict=True):
        importances[name] += float(value)
    return dict(sorted(importances.items(), key=lambda item: (-item[1], item[0])))
