"""Two transparent baselines and a pooled random forest for weekly sales."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from stocksense.features import FEATURE_COLUMNS, NUMERIC_FEATURES, build_features, validate_weekly

RANDOM_SEED = 42
BASELINES = ("previous_week", "trailing_4_week")
CANDIDATES = {
    "forest_small": {"n_estimators": 80, "max_depth": 8, "min_samples_leaf": 4},
    "forest_flexible": {"n_estimators": 120, "max_depth": 12, "min_samples_leaf": 2},
}


@dataclass
class ForecastModel:
    """Serializable fitted estimator plus provenance used to prevent leakage."""

    pipeline: Any
    candidate: str
    trained_through: pd.Timestamp
    products: tuple[str, ...]


def fit_model(history: pd.DataFrame, candidate: str = "forest_small") -> ForecastModel:
    """Fit only the supplied history; callers are responsible for its cutoff."""
    if candidate not in CANDIDATES:
        raise ValueError(f"Unknown candidate {candidate!r}; choose {tuple(CANDIDATES)}.")
    features = build_features(history)
    train = features.dropna(subset=NUMERIC_FEATURES)
    if train.empty:
        raise ValueError("Tree fitting needs at least nine complete weeks per product (eight lags plus one target).")
    transform = ColumnTransformer([
        ("product", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["stock_code"]),
        ("numeric", "passthrough", NUMERIC_FEATURES),
    ])
    pipeline = Pipeline([
        ("features", transform),
        ("regressor", RandomForestRegressor(**CANDIDATES[candidate], random_state=RANDOM_SEED, n_jobs=-1)),
    ])
    pipeline.fit(train[FEATURE_COLUMNS], train["sales"])
    return ForecastModel(
        pipeline=pipeline,
        candidate=candidate,
        trained_through=features["week"].max(),
        products=tuple(sorted(features["stock_code"].unique())),
    )


def forecast(
    history: pd.DataFrame,
    horizon: int = 4,
    method: str = "previous_week",
    model: ForecastModel | None = None,
) -> pd.DataFrame:
    """Predict the next 1–4 weeks recursively without any future actual sales.

    After each prediction, that predicted sales value is appended to working
    history. Thus week 2 can use week 1's prediction, never week 1's actual.
    This same policy is used in backtesting and in the application.
    """
    if isinstance(horizon, bool) or not isinstance(horizon, (int, np.integer)) or not 1 <= horizon <= 4:
        raise ValueError("horizon must be an integer from 1 to 4 weeks.")
    if method not in (*BASELINES, "tree"):
        raise ValueError(f"Unknown method {method!r}.")
    working = validate_weekly(history)
    products = tuple(sorted(working["stock_code"].unique()))
    if method == "trailing_4_week" and working["week"].nunique() < 4:
        raise ValueError("The trailing-four-week baseline needs four complete weeks.")
    if method == "tree":
        if model is None:
            raise ValueError("A fitted model is required for the tree method.")
        if model.trained_through > working["week"].max():
            raise ValueError("Model was trained after the forecast origin; that would leak future data.")
        if products != model.products:
            raise ValueError("Forecast products must match the fitted model's frozen product set.")
        if working["week"].nunique() < 8:
            raise ValueError("Tree prediction needs eight complete weeks of history.")
    outputs = []
    for step in range(1, horizon + 1):
        next_week = working["week"].max() + pd.Timedelta(weeks=1)
        next_rows = pd.DataFrame({"stock_code": products, "week": next_week, "sales": 0.0})
        if method == "previous_week":
            values = working.groupby("stock_code", sort=True)["sales"].last().to_numpy()
        elif method == "trailing_4_week":
            values = working.groupby("stock_code", sort=True)["sales"].apply(lambda s: s.tail(4).mean()).to_numpy()
        else:
            # The placeholder target is never read: every sales feature shifts.
            candidate_history = pd.concat([working, next_rows], ignore_index=True)
            features = build_features(candidate_history)
            target_features = features.loc[features["week"].eq(next_week), FEATURE_COLUMNS]
            values = model.pipeline.predict(target_features)
        values = np.clip(np.asarray(values, dtype=float), 0, None)
        if not np.isfinite(values).all():
            raise ValueError("Forecasts must be finite.")
        next_rows["sales"] = values
        outputs.append(next_rows.rename(columns={"sales": "prediction"}).assign(horizon=step))
        working = pd.concat([working, next_rows], ignore_index=True).sort_values(["stock_code", "week"])
    return pd.concat(outputs, ignore_index=True)[["stock_code", "week", "horizon", "prediction"]]
