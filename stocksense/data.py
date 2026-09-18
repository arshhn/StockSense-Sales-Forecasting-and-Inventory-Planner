"""Auditable cleaning, training-only product selection, and SQLite storage."""
from pathlib import Path
from contextlib import closing
import json
import sqlite3
import numpy as np
import pandas as pd

RAW_COLUMNS = ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"]
RENAME = dict(zip(RAW_COLUMNS, ["invoice", "stock_code", "description", "quantity", "invoice_date", "price", "customer_id", "country"]))
# Inspected in the actual workbook. Do NOT require numeric-only product codes:
# PADS, DCGS*, SP1002, and alphabetic suffixes can represent physical products.
NON_PRODUCT_CODES = {"POST", "DOT", "M", "C2", "C3", "D", "S", "BANK CHARGES", "ADJUST", "ADJUST2", "AMAZONFEE", "CRUK", "B", "GIFT"}


def read_workbook(path: Path) -> tuple[pd.DataFrame, list[dict]]:
    sheets, frames = [], []
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        for name in workbook.sheet_names:
            print(f"Reading {name} ...", flush=True)
            frame = pd.read_excel(workbook, sheet_name=name, dtype={"Invoice": "string", "StockCode": "string", "Customer ID": "string"})
            if set(frame.columns) != set(RAW_COLUMNS):
                raise ValueError(f"Unexpected schema in {name}: {frame.columns.tolist()}")
            sheets.append({"sheet": name, "rows": len(frame), "date_min": str(frame.InvoiceDate.min()), "date_max": str(frame.InvoiceDate.max())})
            frames.append(frame[RAW_COLUMNS])
    return pd.concat(frames, ignore_index=True), sheets


def inspect_source(raw: pd.DataFrame, sheets: list[dict]) -> dict:
    """Describe the actual workbook without applying cleaning decisions."""
    codes = raw.StockCode.astype("string").str.strip()
    unusual = ~codes.str.fullmatch(r"\d{5}[A-Za-z]{0,2}", na=False)
    return {
        "sheets": [s["sheet"] for s in sheets], "sheet_details": sheets,
        "shape": list(raw.shape), "columns": raw.columns.tolist(),
        "dtypes": {k: str(v) for k, v in raw.dtypes.items()},
        "missing": {k: int(v) for k, v in raw.isna().sum().items()},
        "exact_duplicates": int(raw.duplicated().sum()),
        "min_date": str(raw.InvoiceDate.min()), "max_date": str(raw.InvoiceDate.max()),
        "cancellations": int(raw.Invoice.str.upper().str.startswith("C", na=False).sum()),
        "negative_quantity": int(raw.Quantity.lt(0).sum()),
        "zero_quantity": int(raw.Quantity.eq(0).sum()),
        "nonpositive_price": int(raw.Price.le(0).sum()),
        "nonstandard_codes": {k: int(v) for k, v in codes[unusual].value_counts().items()},
        "nonstandard_descriptions": raw.loc[unusual, ["StockCode", "Description"]].drop_duplicates().fillna("").to_dict("records"),
        "top_quantities": [float(v) for v in raw.Quantity.nlargest(10)],
    }


def clean_transactions(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Forecast gross positive sales; returns are audited, not subtracted.

    Flags overlap; excluded counts assign each row its first exclusion reason.
    Exact duplicate removal is a disclosed assumption, since no line ID exists.
    """
    missing = set(RAW_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing source columns: {sorted(missing)}")
    d = raw[RAW_COLUMNS].rename(columns=RENAME).copy()
    exact_duplicates = d.duplicated(keep="first")
    for name in ["invoice", "stock_code", "description", "customer_id", "country"]:
        d[name] = d[name].astype("string").str.strip().replace("", pd.NA)
    d["invoice_date"] = pd.to_datetime(d.invoice_date, errors="coerce")
    d["quantity"] = pd.to_numeric(d.quantity, errors="coerce")
    d["price"] = pd.to_numeric(d.price, errors="coerce")
    code_upper = d.stock_code.str.upper()
    flags = {
        "exact_duplicate": exact_duplicates,
        "missing_invoice": d.invoice.isna(),
        "missing_product_code": d.stock_code.isna(),
        "invalid_date": d.invoice_date.isna(),
        "cancellation": d.invoice.str.upper().str.startswith("C", na=False),
        "negative_quantity": d.quantity.lt(0),
        "zero_or_invalid_quantity": d.quantity.isna() | ~np.isfinite(d.quantity) | d.quantity.eq(0),
        "nonpositive_or_invalid_price": d.price.isna() | ~np.isfinite(d.price) | d.price.le(0),
        "non_product": code_upper.isin(NON_PRODUCT_CODES) | code_upper.str.startswith(("GIFT_", "TEST"), na=False),
    }
    remaining = pd.Series(True, index=d.index)
    excluded = {}
    for reason, mask in flags.items():
        mask = mask.fillna(False)
        excluded[reason] = int((remaining & mask).sum())
        remaining &= ~mask
    dates = d.invoice_date.dropna()
    if dates.empty:
        raise ValueError("No valid dates in workbook.")
    quality = {
        "raw_rows": len(raw),
        "clean_rows": int(remaining.sum()),
        "flags": {reason: int(mask.sum()) for reason, mask in flags.items()},
        "excluded": excluded,
        "missing_values": {name: int(d[name].isna().sum()) for name in d.columns},
        "raw_date_min": str(dates.min()), "raw_date_max": str(dates.max()),
    }
    clean = d.loc[remaining].copy()
    # Labels only: never impute quantity, price, date, or product identifier.
    clean["description"] = clean.description.fillna("Unknown description")
    quality["retained_missing_customer_id"] = int(clean.customer_id.isna().sum())
    quality["retained_missing_description"] = int(d.loc[remaining, "description"].isna().sum())
    quality["clean_products"] = int(clean.stock_code.nunique())
    quality["max_retained_quantity"] = float(clean.quantity.max()) if len(clean) else None
    return clean.reset_index(drop=True), quality


def complete_week_bounds(min_date, max_date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return first/last complete Monday labels, using observed file boundaries.

    A calendar date at either edge is assumed fully recorded. Interior missing
    transactions are zero observed sales, not proof of zero latent demand.
    """
    start, end = pd.Timestamp(min_date).normalize(), pd.Timestamp(max_date).normalize()
    first = start + pd.Timedelta(days=(-start.dayofweek) % 7)
    last = end - pd.Timedelta(days=end.dayofweek)
    if end.dayofweek != 6:
        last -= pd.Timedelta(weeks=1)
    if last < first:
        raise ValueError("Source contains no complete calendar week.")
    return first, last


def select_products(clean: pd.DataFrame, start, training_end, n=30, min_active_weeks=26) -> pd.DataFrame:
    """Rank units using initial training only; deterministic ties by string code."""
    end_exclusive = pd.Timestamp(training_end) + pd.Timedelta(weeks=1)
    history = clean.loc[clean.invoice_date.ge(start) & clean.invoice_date.lt(end_exclusive)].copy()
    history["week"] = history.invoice_date.dt.to_period("W-SUN").dt.start_time
    stats = history.groupby("stock_code").agg(training_units=("quantity", "sum"), active_weeks=("week", "nunique"))
    stats = stats.loc[stats.active_weeks.ge(min_active_weeks)].reset_index()
    stats = stats.sort_values(["training_units", "stock_code"], ascending=[False, True]).head(n)
    if len(stats) < n:
        raise ValueError(f"Only {len(stats)} eligible products; requested {n}. Reduce n/min_active_weeks for a different dataset.")
    labels = history.sort_values("invoice_date", kind="stable").groupby("stock_code").description.last()
    stats["description"] = stats.stock_code.map(labels)
    return stats.reset_index(drop=True)


def aggregate_weekly(clean: pd.DataFrame, codes: list[str], start, end) -> pd.DataFrame:
    """Sum Monday–Sunday units, then fill every selected product/week with zero."""
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if first.dayofweek != 0 or last.dayofweek != 0 or first > last:
        raise ValueError("Weekly bounds must be ordered Mondays.")
    subset = clean.loc[clean.stock_code.isin(codes) & clean.invoice_date.ge(first) & clean.invoice_date.lt(last + pd.Timedelta(weeks=1))].copy()
    subset["week"] = subset.invoice_date.dt.to_period("W-SUN").dt.start_time
    totals = subset.groupby(["stock_code", "week"]).quantity.sum()
    grid = pd.MultiIndex.from_product([sorted(codes), pd.date_range(first, last, freq="W-MON")], names=["stock_code", "week"])
    return totals.reindex(grid, fill_value=0).rename("sales").reset_index()


def save_database(path: Path, clean: pd.DataFrame, weekly: pd.DataFrame, products: pd.DataFrame, quality: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Build a fresh database atomically so interrupted preparation preserves the old one.
    temporary = path.with_suffix(".building.sqlite")
    temporary.unlink(missing_ok=True)
    daily = clean.assign(date=clean.invoice_date.dt.strftime("%Y-%m-%d")).groupby("date").agg(sales=("quantity", "sum"), rows=("quantity", "size")).reset_index()
    with closing(sqlite3.connect(temporary)) as connection, connection:
        clean.to_sql("transactions", connection, index=False, chunksize=10000, dtype={"stock_code": "TEXT", "invoice": "TEXT", "customer_id": "TEXT"})
        weekly.to_sql("weekly_sales", connection, index=False, dtype={"stock_code": "TEXT"})
        products.to_sql("products", connection, index=False, dtype={"stock_code": "TEXT"})
        daily.to_sql("daily_sales", connection, index=False)
        pd.DataFrame(quality["excluded"].items(), columns=["reason", "count"]).to_sql("quality_counts", connection, index=False)
        connection.execute("CREATE INDEX idx_transactions_product_date ON transactions(stock_code, invoice_date)")
        connection.execute("CREATE UNIQUE INDEX idx_weekly_product_date ON weekly_sales(stock_code, week)")
        connection.execute("CREATE UNIQUE INDEX idx_products_code ON products(stock_code)")
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute("INSERT INTO metadata VALUES (?, ?)", ("data_quality", json.dumps(quality)))
    temporary.replace(path)


def load_weekly(path: Path) -> pd.DataFrame:
    with closing(sqlite3.connect(path)) as connection:
        return pd.read_sql_query("SELECT stock_code, week, sales FROM weekly_sales ORDER BY stock_code, week", connection, parse_dates=["week"])
