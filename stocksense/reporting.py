"""Small, human-readable observations derived from the prepared real dataset."""
from contextlib import closing
from pathlib import Path
import sqlite3
import pandas as pd


def write_observations(database: Path, output: Path) -> None:
    with closing(sqlite3.connect(database)) as connection:
        weekly = pd.read_sql_query("SELECT * FROM weekly_sales", connection, parse_dates=["week"])
        products = pd.read_sql_query("SELECT * FROM products ORDER BY training_units DESC", connection)
        daily = pd.read_sql_query("SELECT * FROM daily_sales", connection, parse_dates=["date"])
    totals = weekly.groupby("week").sales.sum()
    seasonal = totals.groupby(totals.index.month).agg(["mean", "size"])
    peak_month = int(seasonal["mean"].idxmax())
    leader = products.iloc[0]
    biggest = weekly.loc[weekly.sales.idxmax()]
    zero = int(weekly.sales.eq(0).sum())
    monthly = daily.set_index("date").sales.resample("MS").sum()
    body = [
        "# Observations from the prepared real data", "",
        "Generated from SQLite after fixed cleaning. These are descriptive observations, not model-selection evidence or causal claims.", "",
        f"- The selected cohort contains **{len(products)} products × {weekly.week.nunique()} complete weeks = {len(weekly):,} product-weeks**.",
        f"- **{leader.stock_code} — {leader.description}** leads training-period unit volume with **{leader.training_units:,.0f} units**. Ranking uses the initial training period only.",
        f"- **{zero:,} of {len(weekly):,} product-weeks ({zero / len(weekly):.1%})** have zero observed sales. Zeros do not distinguish stockouts, delisting, or no purchases.",
        f"- Calendar month **{peak_month}** has the highest mean weekly cohort volume: **{seasonal.loc[peak_month, 'mean']:,.1f} units**, from {seasonal.loc[peak_month, 'size']:.0f} week starts. The seasonal summary uses all complete weeks and only about two annual cycles.",
        f"- The largest selected product-week is **{biggest.stock_code}**, week of **{biggest.week.date()}**, at **{biggest.sales:,.0f} units**. Large orders are retained, so aggregate errors may be strongly influenced by spikes.",
        "- Monthly totals below cover **all cleaned products and countries**. The last month is partial; do not interpret its short total as a demand collapse.", "",
        "| Month | All-product recorded units |", "|---|---:|",
    ]
    body += [f"| {date:%Y-%m} | {value:,.0f} |" for date, value in monthly.items()]
    body += ["", "Cleaning issues and mutually exclusive exclusion counts: see `data_quality.json`. Gross sales are not net sales after returns and are only a proxy for demand.", ""]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(body), encoding="utf-8")
