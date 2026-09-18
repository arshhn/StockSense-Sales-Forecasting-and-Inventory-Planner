"""AppTest catches missing-data failures and exercises real local artifacts."""

from pathlib import Path
from contextlib import closing
import sqlite3

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_app_explains_setup_when_data_is_missing(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("STOCKSENSE_HOME", str(tmp_path))
    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
    assert not app.exception
    assert any("Prepare the UCI data" in warning.value for warning in app.warning)
    assert "python -m stocksense prepare" in app.code[0].value


def test_app_rejects_artifacts_from_different_prepared_data(tmp_path, monkeypatch):
    """An empty test-only schema is enough: stale artifacts must stop before forecasting."""
    from streamlit.testing.v1 import AppTest

    (tmp_path / "data/processed").mkdir(parents=True)
    (tmp_path / "reports").mkdir()
    (tmp_path / "artifacts").mkdir()
    with closing(sqlite3.connect(tmp_path / "data/processed/stocksense.sqlite")) as connection, connection:
        connection.executescript(
            "CREATE TABLE weekly_sales(stock_code TEXT, week TEXT, sales REAL);"
            "CREATE TABLE products(stock_code TEXT, description TEXT, training_units REAL);"
            "CREATE TABLE daily_sales(date TEXT, sales REAL, rows INTEGER);"
            "CREATE TABLE quality_counts(reason TEXT, count INTEGER);"
        )
    (tmp_path / "reports/data_quality.json").write_text('{"weekly_sha256": "new"}', encoding="utf-8")
    (tmp_path / "artifacts/evaluation_summary.json").write_text('{"weekly_sha256": "old"}', encoding="utf-8")
    monkeypatch.setenv("STOCKSENSE_HOME", str(tmp_path))
    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=30)
    assert not app.exception
    assert any("Prepared data has changed" in error.value for error in app.error)
    assert "python -m stocksense train" in app.code[0].value


@pytest.mark.skipif(
    not (ROOT / "data/processed/stocksense.sqlite").exists()
    or not (ROOT / "artifacts/deployment_model.joblib").exists(),
    reason="Run prepare and train on the real dataset before the artifact-dependent smoke test.",
)
def test_app_runs_and_inventory_controls_update(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("STOCKSENSE_HOME", str(ROOT))
    app = AppTest.from_file(str(ROOT / "app.py")).run(timeout=60)
    assert not app.exception
    assert len(app.selectbox) == 2
    assert any("Suggested replenishment" == metric.label for metric in app.metric)
    # Exercise deserialization and prediction even when validation chose a baseline.
    # AppTest 1.45 select_index feeds the formatted label into format_func;
    # select the actual option value when a selectbox uses formatted labels.
    for method in ("previous_week", "trailing_4_week", "tree"):
        app.selectbox[1].select(method).run(timeout=60)
        assert not app.exception
    with closing(sqlite3.connect(ROOT / "data/processed/stocksense.sqlite")) as connection:
        other_product = connection.execute("SELECT stock_code FROM products ORDER BY training_units DESC LIMIT 1 OFFSET 1").fetchone()[0]
    app.selectbox[0].select(other_product)
    app.slider[0].set_value(1)
    app.number_input[0].set_value(1_000_000_000.0)
    app.number_input[1].set_value(25.0)
    app.number_input[2].set_value(4)
    app.number_input[3].set_value(50.0)
    app.run(timeout=60)
    assert not app.exception
    replenishment = next(metric for metric in app.metric if metric.label == "Suggested replenishment")
    assert replenishment.value == "0 units"
    assert any("planner uses 4 forecast weeks" in caption.value for caption in app.caption)
