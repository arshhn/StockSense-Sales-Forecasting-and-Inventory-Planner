import sqlite3
from contextlib import closing
import pandas as pd
import pytest
from stocksense.data import clean_transactions, aggregate_weekly, complete_week_bounds, select_products, save_database, load_weekly


def rows(*overrides):
    base = {"Invoice": "100001", "StockCode": "00123A", "Description": "Real product", "Quantity": 2, "InvoiceDate": "2011-01-03", "Price": 1.5, "Customer ID": None, "Country": "United Kingdom"}
    return pd.DataFrame([{**base, **x} for x in overrides])


def test_cleaning_audits_overlaps_keeps_identifiers_and_anonymous_sales():
    raw = rows({}, {}, {"Invoice": "C100002", "Quantity": -2}, {"Quantity": -1}, {"Price": 0}, {"StockCode": "POST"}, {"StockCode": "DCGS0058"}, {"StockCode": "gift_0001_20"}, {"StockCode": None}, {"InvoiceDate": "bad"}, {"Quantity": float("inf")}, {"Invoice": "100003", "Description": None})
    clean, q = clean_transactions(raw)
    assert clean.stock_code.tolist() == ["00123A", "DCGS0058", "00123A"]
    assert clean.customer_id.isna().all()
    assert clean.description.iloc[-1] == "Unknown description"
    assert q["flags"]["negative_quantity"] == 2
    assert q["excluded"]["negative_quantity"] == 1  # cancellation counted first
    assert q["clean_rows"] + sum(q["excluded"].values()) == len(raw)


def test_partial_weeks_and_zero_filling_are_explicit():
    first, last = complete_week_bounds("2011-01-04", "2011-02-04")
    assert first == pd.Timestamp("2011-01-10")
    assert last == pd.Timestamp("2011-01-24")
    clean, _ = clean_transactions(rows({"InvoiceDate": "2011-01-09"}, {"InvoiceDate": "2011-01-10", "Quantity": 3}, {"InvoiceDate": "2011-01-16", "Quantity": 4}, {"InvoiceDate": "2011-01-24", "Quantity": 5}, {"InvoiceDate": "2011-01-31"}))
    weekly = aggregate_weekly(clean, ["00123A", "99999"], first, last)
    assert weekly.loc[weekly.stock_code.eq("00123A"), "sales"].tolist() == [7, 0, 5]
    assert weekly.loc[weekly.stock_code.eq("99999"), "sales"].tolist() == [0, 0, 0]
    with pytest.raises(ValueError, match="no complete"):
        complete_week_bounds("2011-01-04", "2011-01-06")


def test_nullable_missing_numeric_values_are_excluded():
    raw = rows({}, {"Invoice": "100002"}, {"Invoice": "100003"})
    raw["Quantity"] = pd.Series([2, pd.NA, 2], dtype="Int64")
    raw["Price"] = pd.Series([1.5, 1.5, pd.NA], dtype="Float64")
    clean, quality = clean_transactions(raw)
    assert len(clean) == 1
    assert quality["excluded"]["zero_or_invalid_quantity"] == 1
    assert quality["excluded"]["nonpositive_or_invalid_price"] == 1


def test_product_selection_ignores_future_sales_and_labels():
    clean, _ = clean_transactions(rows({"StockCode": "00123", "Quantity": 10}, {"StockCode": "99999", "Quantity": 1}, {"StockCode": "99999", "Quantity": 100000, "InvoiceDate": "2011-02-01", "Description": "Future label"}))
    selected = select_products(clean, "2011-01-03", "2011-01-03", n=1, min_active_weeks=1)
    assert selected.stock_code.tolist() == ["00123"]
    changed = clean.copy()
    changed.loc[changed.invoice_date.gt("2011-01-09"), "quantity"] = 1e9
    pd.testing.assert_frame_equal(selected, select_products(changed, "2011-01-03", "2011-01-03", n=1, min_active_weeks=1))


def test_sqlite_roundtrip_keeps_leading_zero_code(tmp_path):
    clean, quality = clean_transactions(rows({"StockCode": "00123"}))
    selected = select_products(clean, "2011-01-03", "2011-01-03", n=1, min_active_weeks=1)
    weekly = aggregate_weekly(clean, ["00123"], "2011-01-03", "2011-01-10")
    path = tmp_path / "test.sqlite"
    save_database(path, clean, weekly, selected, quality)
    assert load_weekly(path).stock_code.tolist() == ["00123", "00123"]
    with closing(sqlite3.connect(path)) as con:
        assert con.execute("SELECT typeof(stock_code) FROM transactions").fetchone()[0] == "text"
