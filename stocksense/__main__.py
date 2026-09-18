"""Reproducible command-line entry point: python -m stocksense --help."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata
import json
import platform
import time
import pandas as pd

from stocksense.data import aggregate_weekly, clean_transactions, complete_week_bounds, inspect_source, load_weekly, read_workbook, save_database, select_products
from stocksense.source import download, sha256


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def prepare(args):
    started = time.perf_counter()
    home = args.home
    workbook = args.workbook or download(home / "data/raw")
    if not 20 <= args.products <= 50:
        raise ValueError("Choose 20–50 products for this project.")
    raw, sheets = read_workbook(workbook)
    write_json(home / "reports/source_inspection.json", inspect_source(raw, sheets))
    clean, quality = clean_transactions(raw)
    start, end = complete_week_bounds(quality["raw_date_min"], quality["raw_date_max"])
    weeks = pd.date_range(start, end, freq="W-MON")
    validation_weeks, test_weeks = 12, 8
    if len(weeks) < 52:
        raise ValueError("Need at least 52 complete weeks for this experiment.")
    selection_end = weeks[-(validation_weeks + test_weeks + 1)]
    products = select_products(clean, start, selection_end, n=args.products)
    weekly = aggregate_weekly(clean, products.stock_code.tolist(), start, end)
    quality.update({
        "source_url": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
        "source_sha256": sha256(workbook), "source_sheets": sheets,
        "complete_week_start": str(start.date()), "complete_week_end": str(end.date()),
        "complete_weeks": len(weeks), "selected_products": len(products),
        "selected_codes": products.stock_code.tolist(),
        "selection_end": str(selection_end.date()), "selection_min_active_weeks": 26,
        "selection_rule": "Top units sold in initial training; ties by stock code; at least 26 active training weeks",
        "validation_weeks": validation_weeks, "test_weeks": test_weeks,
        "partial_week_rows_excluded_from_weekly": int((clean.invoice_date.lt(start) | clean.invoice_date.ge(end + pd.Timedelta(weeks=1))).sum()),
        "weekly_sha256": hashlib.sha256(weekly.to_csv(index=False).encode()).hexdigest(),
        "zero_sales_product_weeks": int(weekly.sales.eq(0).sum()),
        "weekly_rows": len(weekly),
    })
    print(f"Cleaned {len(raw):,} source rows to {len(clean):,}; storing SQLite ...", flush=True)
    save_database(home / "data/processed/stocksense.sqlite", clean, weekly, products, quality)
    quality["preparation_seconds"] = round(time.perf_counter() - started, 2)
    write_json(home / "reports/data_quality.json", quality)
    products.to_csv(home / "reports/selected_products.csv", index=False)
    from stocksense.reporting import write_observations
    write_observations(home / "data/processed/stocksense.sqlite", home / "reports/observations.md")
    print(json.dumps(quality, indent=2), flush=True)


def train(args):
    import joblib
    from stocksense.evaluation import evaluate
    started = time.perf_counter()
    home = args.home
    quality_path = home / "reports/data_quality.json"
    if not quality_path.exists():
        raise ValueError("Run python -m stocksense prepare first.")
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    weekly = load_weekly(home / "data/processed/stocksense.sqlite")
    print("Running rolling validation, then frozen-policy final test ...", flush=True)
    result = evaluate(weekly, validation_weeks=quality["validation_weeks"], test_weeks=quality["test_weeks"])
    if result["summary"]["initial_training_end"] != quality["selection_end"]:
        raise ValueError("Product-selection cutoff and evaluation cutoff disagree; re-run preparation.")
    output = home / "artifacts"
    output.mkdir(parents=True, exist_ok=True)
    for name in ["validation_predictions", "validation_metrics", "test_predictions", "test_metrics", "failure_cases"]:
        result[name].to_csv(output / f"{name}.csv", index=False)
    joblib.dump(result["deployment_model"], output / "deployment_model.joblib", compress=3)
    summary = {**result["summary"], "weekly_sha256": quality["weekly_sha256"], "source_sha256": quality["source_sha256"], "training_seconds": round(time.perf_counter()-started, 2)}
    write_json(output / "evaluation_summary.json", summary)
    write_json(output / "training_config.json", result["config"])
    environment = {"python": platform.python_version(), "platform": platform.platform(), "packages": {name: importlib.metadata.version(name) for name in ["numpy", "pandas", "scikit-learn", "streamlit", "plotly", "openpyxl", "joblib", "pytest"]}}
    write_json(output / "environment.json", environment)
    # Small measured artifacts belong in Git; raw data, SQLite and models do not.
    reports = home / "reports"
    for name in ["validation_metrics", "test_metrics", "failure_cases"]:
        result[name].to_csv(reports / f"{name}.csv", index=False)
    write_json(reports / "evaluation_summary.json", summary)
    write_json(reports / "training_config.json", result["config"])
    write_json(reports / "environment.json", environment)
    print("VALIDATION", flush=True)
    print(result["validation_metrics"].query("scope == 'overall'").to_string(index=False), flush=True)
    print("FINAL TEST (never used for selection)", flush=True)
    print(result["test_metrics"].query("scope == 'overall'").to_string(index=False), flush=True)
    print(json.dumps(summary, indent=2), flush=True)


def evaluate_saved(args):
    """Recalculate metrics from saved out-of-sample predictions, without fitting."""
    from stocksense.evaluation import summarize_metrics
    predictions = pd.read_csv(args.home / "artifacts/test_predictions.csv", dtype={"stock_code": str})
    metrics = summarize_metrics(predictions)
    saved = pd.read_csv(args.home / "artifacts/test_metrics.csv", dtype={"stock_code": str})
    for frame in (metrics, saved):
        frame["stock_code"] = frame["stock_code"].astype("string")
    pd.testing.assert_frame_equal(metrics, saved, check_dtype=False, check_exact=False, atol=1e-9, rtol=1e-9)
    print("Saved metrics verified against predictions.")
    print(metrics.query("scope == 'overall'").to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="StockSense: reproducible weekly sales forecasting")
    parser.add_argument("--home", type=Path, default=Path.cwd(), help="Project data/artifact directory (default: current directory)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("download", help="Download original UCI workbook")
    commands.add_parser("inspect", help="Inspect actual workbook without filtering (prepare also saves this audit)")
    preparation = commands.add_parser("prepare", help="Read both sheets, clean, select products, store SQLite")
    preparation.add_argument("--workbook", type=Path, help="Use manually downloaded workbook")
    preparation.add_argument("--products", type=int, default=30)
    commands.add_parser("train", help="Validate candidates, evaluate final test, save deployment model")
    commands.add_parser("evaluate", help="Verify saved final-test metrics without retraining")
    args = parser.parse_args()
    try:
        if args.command == "download":
            print(download(args.home / "data/raw").resolve())
        elif args.command == "inspect":
            raw, sheets = read_workbook(download(args.home / "data/raw"))
            report = inspect_source(raw, sheets)
            write_json(args.home / "reports/source_inspection.json", report)
            print(json.dumps(report, indent=2))
        elif args.command == "prepare":
            prepare(args)
        elif args.command == "train":
            train(args)
        else:
            evaluate_saved(args)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        parser.exit(1, f"StockSense: {exc}\n")


if __name__ == "__main__":
    main()
