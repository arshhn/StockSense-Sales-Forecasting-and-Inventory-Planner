"""Chronological model selection, then a frozen-policy final test.

Validation and test use nonoverlapping four-week forecast blocks. Model
parameters are refitted at each origin using only information known then;
the candidate and winning method are chosen before any test score is used.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from stocksense.features import validate_weekly
from stocksense.forecasting import BASELINES, CANDIDATES, RANDOM_SEED, fit_model, forecast


def error_metrics(actual, prediction) -> dict:
    """MAE in units and WAPE as a fraction; WAPE is undefined at zero volume."""
    actual = np.asarray(actual, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    if actual.shape != prediction.shape or actual.size == 0:
        raise ValueError("Metrics require nonempty, equally shaped actual and prediction arrays.")
    if not np.isfinite(actual).all() or not np.isfinite(prediction).all() or (actual < 0).any():
        raise ValueError("Metrics require finite values and nonnegative actual sales.")
    absolute_errors = np.abs(actual - prediction)
    volume = float(actual.sum())
    return {
        "mae": float(absolute_errors.mean()),
        "wape": float(absolute_errors.sum() / volume) if volume > 0 else np.nan,
        "n_predictions": int(actual.size),
        "actual_total": volume,
    }


def summarize_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    """Report overall, product, horizon, and product-by-horizon errors."""
    rows = []
    for scope, dimensions in (
        ("overall", []), ("product", ["stock_code"]),
        ("horizon", ["horizon"]), ("product_horizon", ["stock_code", "horizon"]),
    ):
        columns = ["model", *dimensions]
        for key, group in predictions.groupby(columns, sort=True):
            key = key if isinstance(key, tuple) else (key,)
            row = {"scope": scope, "stock_code": None, "horizon": None, **dict(zip(columns, key))}
            rows.append({**row, **error_metrics(group["actual"], group["prediction"])})
    return pd.DataFrame(rows)[[
        "model", "scope", "stock_code", "horizon", "mae", "wape", "n_predictions", "actual_total",
    ]]


def _backtest(weekly, origins, horizon, model_names):
    predictions = []
    for origin in origins:
        history = weekly.loc[weekly["week"] < origin]
        for name in model_names:
            model = fit_model(history, candidate=name) if name in CANDIDATES else None
            result = forecast(history, horizon=horizon, method="tree" if model is not None else name, model=model)
            result = result.merge(
                weekly.rename(columns={"sales": "actual"}), on=["stock_code", "week"], how="left", validate="one_to_one",
            )
            if result["actual"].isna().any():
                raise ValueError("A backtest forecast extends beyond the available complete weeks.")
            result["model"] = name
            result["origin"] = origin
            result["train_end"] = history["week"].max()
            predictions.append(result)
    return pd.concat(predictions, ignore_index=True)


def _rank_models(metrics):
    # All candidates face exactly the same actuals, so WAPE rankings equal
    # MAE rankings. Explicit fallback also handles an all-zero holdout.
    overall = metrics.loc[metrics["scope"].eq("overall")].copy()
    overall["selection_score"] = overall["wape"].where(overall["wape"].notna(), overall["mae"])
    # A tied baseline is preferred to a more complicated model.
    priority = {name: i for i, name in enumerate((*BASELINES, *CANDIDATES))}
    overall["tie_priority"] = overall["model"].map(priority)
    return overall.sort_values(["selection_score", "tie_priority"])


def _failure_cases(test_metrics, tree_name):
    product = test_metrics.loc[test_metrics["scope"].eq("product")]
    tree = product.loc[product["model"].eq(tree_name), ["stock_code", "mae", "wape"]]
    comparisons = []
    for baseline in BASELINES:
        base = product.loc[product["model"].eq(baseline), ["stock_code", "mae", "wape"]]
        merged = tree.merge(base, on="stock_code", suffixes=("_tree", "_baseline"))
        merged["baseline"] = baseline
        merged["tree_model"] = tree_name
        merged["mae_gap"] = merged["mae_tree"] - merged["mae_baseline"]
        comparisons.append(merged.loc[merged["mae_gap"] > 0])
    return pd.concat(comparisons, ignore_index=True).sort_values("mae_gap", ascending=False).reset_index(drop=True)


def evaluate(weekly: pd.DataFrame, validation_weeks: int = 12, test_weeks: int = 8, horizon: int = 4) -> dict:
    """Select on validation, audit on test, and create a separate deployment fit.

    The final test is prequential: after one four-week block has actually
    elapsed, its observations may train the next block. Test results never
    change the chosen hyperparameters or winner. The deployment estimator is
    refitted after evaluation and is never used to produce reported test scores.
    """
    weekly = validate_weekly(weekly)
    if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 4:
        raise ValueError("horizon must be an integer from 1 to 4.")
    for name, length in (("validation_weeks", validation_weeks), ("test_weeks", test_weeks)):
        if isinstance(length, bool) or not isinstance(length, int) or length <= 0 or length % horizon:
            raise ValueError(f"{name} must be a positive multiple of horizon.")
    weeks = pd.DatetimeIndex(sorted(weekly["week"].unique()))
    initial_count = len(weeks) - validation_weeks - test_weeks
    if initial_count < 16:
        raise ValueError("Need at least 16 training weeks before validation and test.")
    validation_origins = list(weeks[initial_count:len(weeks) - test_weeks:horizon])
    test_origins = list(weeks[len(weeks) - test_weeks::horizon])
    validation_predictions = _backtest(weekly, validation_origins, horizon, [*BASELINES, *CANDIDATES])
    validation_metrics = summarize_metrics(validation_predictions)
    ranking = _rank_models(validation_metrics)
    selected_model = ranking.iloc[0]["model"]
    tree_name = ranking.loc[ranking["model"].isin(CANDIDATES)].iloc[0]["model"]
    test_predictions = _backtest(weekly, test_origins, horizon, [*BASELINES, tree_name])
    test_metrics = summarize_metrics(test_predictions)
    failure_cases = _failure_cases(test_metrics, tree_name)
    config = {
        "random_seed": RANDOM_SEED, "horizon": horizon, "validation_weeks": validation_weeks,
        "test_weeks": test_weeks, "initial_training_weeks": initial_count,
        "candidates": CANDIDATES, "selection_metric": "WAPE; MAE when actual sum is zero",
        "recursive_forecasts": True, "test_protocol": "nonoverlapping rolling-origin blocks with expanding-history refits",
    }
    summary = {
        "selected_model": selected_model,
        "selected_method": "tree" if selected_model in CANDIDATES else selected_model,
        "selected_tree_candidate": tree_name,
        "training_start": weeks[0].date().isoformat(),
        "initial_training_end": weeks[initial_count - 1].date().isoformat(),
        "validation_start": validation_origins[0].date().isoformat(),
        "validation_end": weeks[len(weeks) - test_weeks - 1].date().isoformat(),
        "test_start": test_origins[0].date().isoformat(),
        "test_end": weeks[-1].date().isoformat(),
        "validation_origins": [week.date().isoformat() for week in validation_origins],
        "test_origins": [week.date().isoformat() for week in test_origins],
        "n_products": int(weekly["stock_code"].nunique()),
        "n_weeks": len(weeks),
        "products_tree_worse_than_any_baseline": int(failure_cases["stock_code"].nunique()),
        "wape_units": "fraction; multiply by 100 for percent; undefined if actual total is zero",
    }
    return {
        "config": config, "summary": summary,
        "validation_predictions": validation_predictions, "validation_metrics": validation_metrics,
        "test_predictions": test_predictions, "test_metrics": test_metrics,
        "failure_cases": failure_cases,
        "deployment_model": fit_model(weekly, candidate=tree_name),
    }
