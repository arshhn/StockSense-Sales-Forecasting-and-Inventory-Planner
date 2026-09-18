"""Causal, weekly features shared by training and recursive prediction.

A row dated Monday predicts the units sold during that Monday–Sunday week.
Every sales-derived feature is shifted first, so that row cannot see its target.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = (1, 2, 4, 8)
NUMERIC_FEATURES = [
    "lag_1", "lag_2", "lag_4", "lag_8", "rolling_mean_4",
    "rolling_std_4", "rolling_mean_8", "week_sin", "week_cos", "month", "year",
]
FEATURE_COLUMNS = ["stock_code", *NUMERIC_FEATURES]


def validate_weekly(weekly: pd.DataFrame) -> pd.DataFrame:
    """Return a sorted copy, rejecting ambiguous or incomplete weekly panels.

    Missing calendar weeks must be filled deliberately by data preparation; a
    lag of one row is only a lag of one week when that invariant holds.
    """
    required = {"stock_code", "week", "sales"}
    missing = required.difference(weekly.columns)
    if missing:
        raise ValueError(f"Weekly data is missing columns: {sorted(missing)}")
    if weekly.empty:
        raise ValueError("Weekly history must contain at least one product.")
    frame = weekly.loc[:, ["stock_code", "week", "sales"]].copy()
    if frame["stock_code"].isna().any() or not frame["stock_code"].map(lambda x: isinstance(x, str)).all():
        raise ValueError("stock_code must contain nonmissing strings; identifiers are not numbers.")
    frame["week"] = pd.to_datetime(frame["week"], errors="raise")
    if frame["week"].isna().any() or (frame["week"].dt.dayofweek != 0).any():
        raise ValueError("Every week must be a nonmissing Monday.")
    if (frame["week"] != frame["week"].dt.normalize()).any():
        raise ValueError("Week dates must be normalized to midnight.")
    frame["sales"] = pd.to_numeric(frame["sales"], errors="raise").astype(float)
    if not np.isfinite(frame["sales"]).all() or (frame["sales"] < 0).any():
        raise ValueError("Weekly sales must be finite, nonnegative numbers.")
    if frame.duplicated(["stock_code", "week"]).any():
        raise ValueError("Each product/week must appear exactly once.")
    frame = frame.sort_values(["stock_code", "week"]).reset_index(drop=True)
    expected = pd.date_range(frame["week"].min(), frame["week"].max(), freq="W-MON")
    for code, group in frame.groupby("stock_code", sort=False):
        if not pd.DatetimeIndex(group["week"]).equals(expected):
            raise ValueError(f"Product {code!r} is missing weeks; provide a rectangular complete-week panel.")
    return frame


def build_features(weekly: pd.DataFrame) -> pd.DataFrame:
    """Keep targets and identifiers alongside strictly past-looking features.

    The first eight rows of each product have incomplete lag history. They stay
    in this frame for inspection and are excluded from model fitting.
    """
    frame = validate_weekly(weekly)
    grouped = frame.groupby("stock_code", sort=False)["sales"]
    for lag in LAGS:
        frame[f"lag_{lag}"] = grouped.shift(lag)
    frame["rolling_mean_4"] = grouped.transform(lambda s: s.shift(1).rolling(4, min_periods=4).mean())
    frame["rolling_std_4"] = grouped.transform(lambda s: s.shift(1).rolling(4, min_periods=4).std(ddof=0))
    frame["rolling_mean_8"] = grouped.transform(lambda s: s.shift(1).rolling(8, min_periods=8).mean())
    week_number = frame["week"].dt.isocalendar().week.astype(float)
    frame["week_sin"] = np.sin(2 * np.pi * week_number / 52.1775)
    frame["week_cos"] = np.cos(2 * np.pi * week_number / 52.1775)
    frame["month"] = frame["week"].dt.month
    frame["year"] = frame["week"].dt.year
    return frame
