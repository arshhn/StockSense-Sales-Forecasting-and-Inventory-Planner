"""Small, deliberately constructed fixtures test correctness, not real scores."""

import numpy as np
import pandas as pd
import pytest

from stocksense.evaluation import error_metrics, evaluate
from stocksense.features import FEATURE_COLUMNS, build_features
from stocksense.forecasting import ForecastModel, fit_model, forecast


def weekly_fixture(n_weeks=40):
    weeks = pd.date_range("2022-01-03", periods=n_weeks, freq="W-MON")
    return pd.concat([
        pd.DataFrame({"stock_code": code, "week": weeks, "sales": np.arange(n_weeks, dtype=float) + offset})
        for code, offset in (("00123", 1), ("A12B", 101))
    ], ignore_index=True)


def test_current_and_future_sales_cannot_change_features():
    original = weekly_fixture()
    cutoff = original["week"].sort_values().unique()[20]
    changed = original.copy()
    changed.loc[changed["week"] >= cutoff, "sales"] = 99999
    first = build_features(original)
    second = build_features(changed)
    pd.testing.assert_frame_equal(
        first.loc[first["week"] <= cutoff, FEATURE_COLUMNS],
        second.loc[second["week"] <= cutoff, FEATURE_COLUMNS],
    )
    # Separate product histories: the first lag for A12B is 101, not 40.
    assert first.loc[(first["stock_code"] == "A12B") & (first["week"] == pd.Timestamp("2022-01-10")), "lag_1"].item() == 101


def test_missing_calendar_week_is_rejected_instead_of_shortening_lags():
    weekly = weekly_fixture()
    with pytest.raises(ValueError, match="missing weeks"):
        build_features(weekly.drop(index=5))


def test_baselines_are_recursive_for_all_four_weeks():
    weekly = pd.DataFrame({"stock_code": "00123", "week": pd.date_range("2022-01-03", periods=4, freq="W-MON"), "sales": [0, 0, 0, 16]})
    assert forecast(weekly, 4, "previous_week")["prediction"].tolist() == [16, 16, 16, 16]
    assert forecast(weekly, 4, "trailing_4_week")["prediction"].tolist() == [4, 5, 6.25, 7.8125]


class IncrementPredictor:
    def predict(self, frame):
        return frame["lag_1"].to_numpy() + 1


def test_tree_recursion_uses_predictions_in_subsequent_features():
    weekly = weekly_fixture(12)
    model = ForecastModel(IncrementPredictor(), "test_double", weekly["week"].max(), ("00123", "A12B"))
    result = forecast(weekly, 4, "tree", model)
    assert result.loc[result["stock_code"] == "00123", "prediction"].tolist() == [13, 14, 15, 16]
    assert result.loc[result["stock_code"] == "A12B", "prediction"].tolist() == [113, 114, 115, 116]
    assert result["week"].min() > weekly["week"].max()


def test_model_fit_after_origin_is_rejected():
    weekly = weekly_fixture(12)
    model = ForecastModel(IncrementPredictor(), "test_double", weekly["week"].max() + pd.Timedelta(weeks=1), ("00123", "A12B"))
    with pytest.raises(ValueError, match="leak"):
        forecast(weekly, 1, "tree", model)


def test_wape_uses_total_volume_and_handles_zero_explicitly():
    scores = error_metrics([0, 10], [5, 5])
    assert scores["mae"] == 5
    assert scores["wape"] == 1
    assert scores["n_predictions"] == 2
    assert np.isnan(error_metrics([0, 0], [0, 0])["wape"])
    assert np.isnan(error_metrics([0, 0], [3, 1])["wape"])
    assert error_metrics([0, 0], [3, 1])["mae"] == 2


def test_rolling_split_and_selection_are_untouched_by_final_test(monkeypatch):
    fitted_cutoffs = []

    def fake_fit(history, candidate="forest_small"):
        fitted_cutoffs.append(history["week"].max())
        return ForecastModel(IncrementPredictor(), candidate, history["week"].max(), ("00123", "A12B"))

    monkeypatch.setattr("stocksense.evaluation.fit_model", fake_fit)
    weekly = weekly_fixture(40)
    evaluation = evaluate(weekly)
    assert len(evaluation["summary"]["validation_origins"]) == 3
    assert len(evaluation["summary"]["test_origins"]) == 2
    assert evaluation["config"]["initial_training_weeks"] == 20
    for phase in ("validation", "test"):
        predictions = evaluation[f"{phase}_predictions"]
        assert (predictions["train_end"] < predictions["origin"]).all()
        assert (predictions["week"] >= predictions["origin"]).all()
        assert not predictions.duplicated(["model", "stock_code", "week"]).any()
    validation_predictions = evaluation["validation_predictions"]
    test_predictions = evaluation["test_predictions"]
    assert validation_predictions["week"].max() < test_predictions["week"].min()
    # Fits: two candidates at three validation origins, one chosen tree at two
    # test origins, then the explicitly separate deployment fit.
    expected = [pd.Timestamp(origin) - pd.Timedelta(weeks=1) for origin in evaluation["summary"]["validation_origins"] for _ in range(2)]
    expected += [pd.Timestamp(origin) - pd.Timedelta(weeks=1) for origin in evaluation["summary"]["test_origins"]]
    expected += [weekly["week"].max()]
    assert fitted_cutoffs == expected
    changed = weekly.copy()
    changed.loc[changed["week"] >= pd.Timestamp(evaluation["summary"]["test_start"]), "sales"] *= 100
    alternative = evaluate(changed)
    assert evaluation["summary"]["selected_model"] == alternative["summary"]["selected_model"]
    pd.testing.assert_frame_equal(evaluation["validation_metrics"], alternative["validation_metrics"])
    first_origin = test_predictions["origin"].min()
    pd.testing.assert_series_equal(
        test_predictions.loc[test_predictions["origin"] == first_origin, "prediction"],
        alternative["test_predictions"].loc[alternative["test_predictions"]["origin"] == first_origin, "prediction"],
    )


def test_real_estimator_fits_string_ids_and_returns_finite_predictions():
    weekly = weekly_fixture(20)
    model = fit_model(weekly)
    predictions = forecast(weekly, 4, "tree", model)
    assert len(predictions) == 8
    assert model.trained_through == weekly["week"].max()
    assert set(predictions["stock_code"]) == {"00123", "A12B"}
    assert np.isfinite(predictions["prediction"]).all()
    assert (predictions["prediction"] >= 0).all()


def test_selection_can_prefer_baseline_when_holdout_volume_is_zero(monkeypatch):
    def fake_fit(history, candidate="forest_small"):
        return ForecastModel(IncrementPredictor(), candidate, history["week"].max(), ("00123", "A12B"))

    monkeypatch.setattr("stocksense.evaluation.fit_model", fake_fit)
    weekly = weekly_fixture(40)
    weekly["sales"] = 0.0
    result = evaluate(weekly)
    assert result["summary"]["selected_method"] == "previous_week"
    assert result["validation_metrics"]["wape"].isna().all()
    assert result["test_metrics"]["wape"].isna().all()
    assert not result["failure_cases"].empty


@pytest.mark.parametrize("horizon", [0, 5, 1.5, True])
def test_invalid_forecast_horizon_is_rejected(horizon):
    with pytest.raises(ValueError, match="horizon"):
        forecast(weekly_fixture(), horizon)
