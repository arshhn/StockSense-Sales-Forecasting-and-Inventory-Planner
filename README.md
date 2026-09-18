# StockSense — Sales Forecasting and Inventory Planner

A laptop-friendly ML portfolio project that forecasts weekly product sales and turns those forecasts into an **inventory planning simulation**. Built with Python, pandas, SQLite, scikit-learn, Streamlit and Plotly. It uses real UCI transactions, not synthetic demonstration data. No GPU, paid service, or external database is required.

The app is a historical demonstration: the last complete observed week ends **4 December 2011**. “Next week” means 5 December 2011, not next week in the current year. There is no live stock feed.

## Run it

Use **Python 3.12** (3.11–3.13 supported; 3.14 is excluded by the pinned environment). Run all commands from this repository's root. Allow a few minutes for installation and reading the million-row workbook; Excel parsing is slower than model fitting. Plan for roughly 1 GB free disk space plus the Python environment and several GB available RAM.

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m stocksense download
.\.venv\Scripts\python.exe -m stocksense prepare
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m stocksense train
.\.venv\Scripts\python.exe -m stocksense evaluate
.\.venv\Scripts\python.exe -m streamlit run app.py
```

macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m stocksense download
python -m stocksense prepare
python -m pytest -q
python -m stocksense train
python -m stocksense evaluate
python -m streamlit run app.py
```

Open the local URL printed by Streamlit, usually `http://localhost:8501`. Activation is optional on Windows because the commands use the environment's interpreter directly. For an existing prepared checkout, only the final command is needed. `python -m stocksense --help` lists the commands. `prepare --products 20` through `--products 50` changes the cohort; **re-run training afterward**. App fingerprints detect stale model/data combinations. The artifacts are regenerated locally; a fresh Git clone must prepare and train first.

`requirements.txt` pins the direct dependencies. `requirements-lock.txt` also records the transitive versions installed for this run; use `pip install -r requirements-lock.txt` to reproduce that environment more closely. On a slow filesystem, pip's optional bytecode compilation can take several minutes; `pip install --no-compile -r requirements.txt` skips that installation-time step. `python -m stocksense inspect` separately regenerates the source inspection without cleaning; `prepare` already includes it.

## Dataset and attribution

**Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D.** Licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Source: [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii). StockSense transforms the source into cleaned gross sales and weekly aggregates; it is not affiliated with UCI or the retailer.

If automatic downloading fails:

1. Open the UCI page above and click **Download (43.5 MB)**.
2. Save `online_retail_ii.zip` and extract it using your operating system's ZIP tool.
3. Copy **`online_retail_II.xlsx`** into **`data/raw/`** under this repository. Keep its original name and both sheets.
4. Run `python -m stocksense prepare`, then `python -m stocksense train` using your environment's Python.

Alternatively, pass your file directly: `python -m stocksense prepare --workbook "C:\path\online_retail_II.xlsx"`. Do not substitute the one-year Online Retail dataset. The downloader fetches [UCI's official ZIP](https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip), reuses an existing workbook, and never fabricates a fallback. A source SHA-256 fingerprint is recorded in `reports/data_quality.json`.

## What the source inspection found

Both sheets were inspected before choosing cleaning rules. [Source inspection](reports/source_inspection.json) records the findings and unusual product-code examples.

| Raw-data observation | Count |
|---|---:|
| Transaction rows across two sheets | 1,067,371 |
| Exact duplicates across all eight original fields | 34,335 |
| Cancellation rows (invoice begins C) | 19,494 |
| Negative quantities | 22,950 |
| Zero or negative prices | 6,207 |
| Missing customer IDs | 243,007 |
| Missing descriptions | 4,382 |

These flags **overlap**; do not add them. The preparation audit also records sequential, mutually exclusive exclusion counts, which do reconcile to the final retained row count. The sheets overlap in calendar time, so duplicates are checked across the combined workbook.

See [measured exploratory observations](reports/observations.md) for volume leaders, zero-sales weeks, seasonal patterns and monthly totals.

Cleaning decisions in `stocksense/data.py`:

- Preserve stock codes as strings, including leading zeros, suffixes and letter case. Do not cast them to integers. `DCGS0058`, `SP1002` and `PADS` can be physical products; a numeric-only filter would be wrong.
- Remove exact duplicate original rows. Without invoice-line IDs, some identical lines could be legitimate; this is a documented assumption.
- Exclude missing invoice/product/date, cancellation invoices, negative/zero/nonfinite quantities and nonpositive/nonfinite prices. Returns are audited separately, not subtracted from current sales. The target is **gross positive sales**, not net sales or uncensored demand.
- Exclude known postage, carriage, fees, manual entries, adjustments, samples, gift vouchers and test product codes through a reviewed code list. Preserve other codes; no broad text search for “stock” or “check,” which also occur in genuine names.
- Keep missing customer IDs because customer-level features are not needed. Missing descriptions get a display label only; sales, prices and identifiers are never imputed. In this workbook, all positive-quantity, positive-price rows had descriptions.
- Keep large positive orders: the source contains wholesalers, and arbitrary clipping could erase real demand. An extreme sale may subsequently be cancelled; this gross-sales target can still count the original line.
- Pool all recorded countries into one product-level series. The planner assumes one pooled stock position; it is not a country/warehouse allocation system.

Weeks run Monday–Sunday. The first partial week beginning 30 November 2009 and the last beginning 5 December 2011 are excluded from forecasting. The 104 complete weeks run from 7 December 2009 through the week beginning 28 November 2011. Partial-week transactions remain in the cleaned SQL transaction table and the explicitly labelled daily overview.

For the selected products, every complete week is present. No recorded transaction becomes **zero observed sales**; this also covers weeks before a product's first recorded sale. The data cannot distinguish store closure, unavailability, a stockout or genuinely zero demand. No partial-week scaling is performed.

## Architecture and artifacts

```text
UCI workbook (both sheets)
  -> source.py / data.py: audit + clean + training-only product selection
  -> SQLite: transactions, weekly_sales, products, daily_sales, quality_counts
  -> features.py: past sales + calendar features
  -> forecasting.py / evaluation.py: rolling validation -> frozen-policy test
  -> saved model + predictions + metrics
  -> app.py + inventory.py: explain, compare, simulate replenishment
```

| Location | Purpose |
|---|---|
| `stocksense/__main__.py` | Reproducible download, prepare, train and evaluate commands |
| `stocksense/data.py` | Cleaning audit, full-week grid, cohort selection, SQLite |
| `stocksense/features.py` | Grouped lags and shifted rolling statistics |
| `stocksense/forecasting.py` | Both baselines, pooled forest and recursive forecasts |
| `stocksense/evaluation.py` | Chronological backtests, selection, metrics and failure cases |
| `stocksense/inventory.py` | Validated replenishment arithmetic |
| `app.py` | Streamlit interface with Plotly charts |
| `stocksense/ui.py`, `.streamlit/config.toml` | Reusable light theme, responsive cards, and Helvetica-first typography |
| `tests/` | Cleaning, aggregation, temporal leakage, metrics, inventory and app checks |
| `reports/` | Small, versionable inspection and measured results |
| `data/processed/stocksense.sqlite` | All cleaned transactions plus selected-product weekly panel |
| `artifacts/` | Model, prediction-level results, metrics, configuration and environment |

Raw workbook/ZIP, SQLite, pickle/joblib models, environments and large generated files are ignored by Git. Small audited metrics remain under `reports/`. Only load joblib artifacts produced by this project: pickle-based models can execute code when loaded.

## Forecasting and honest evaluation

The default cohort is the **30 highest-unit products with at least 26 active weeks in the initial training period**. Ties are broken by stock code. Both the cohort and display descriptions are fixed using initial training only; test sales cannot decide which products are included.

| Stage | Monday week labels | Purpose |
|---|---|---|
| Initial training | 2009-12-07 to 2011-07-11 | Select products and fit initial models (84 weeks) |
| Rolling validation | 2011-07-18 to 2011-10-03 | Three consecutive four-week forecast blocks (12 weeks) |
| Final rolling test | 2011-10-10 to 2011-11-28 | Two consecutive four-week blocks (8 weeks) |

The dates above refer to week starts; a row's full week's actuals are known only after Sunday. Every origin uses an expanding history ending before the forecasted Monday. Later origins can use actuals from earlier completed blocks, matching a periodic real forecasting workflow. This is a **prequential test with refits**, not a single frozen eight-week forecast. Candidate settings and the winning method never change based on final-test scores.

Methods:

1. **Previous week:** repeat the most recent observed sales at every future step.
2. **Trailing four weeks:** average the last four available weekly values; at steps 2–4, prior predictions enter that window.
3. **Pooled random forest:** one-hot product identity, lags 1/2/4/8, shifted rolling mean 4/8 and standard deviation 4, cyclical week-of-year, month and year. Two small predefined candidates use seed 42. The first eight rows per product are excluded from fitting because their history is incomplete.

All sales-derived features shift by at least one week. Multiweek forecasts append predictions to history recursively, never hidden future actuals. The same function runs during backtesting and the app. Two forest configurations (80 trees/depth 8/min leaf 4; 120 trees/depth 12/min leaf 2) keep experimentation manageable. Scikit-learn already provides the needed model; XGBoost would add a dependency without evidence it is necessary.

Model selection minimizes pooled validation WAPE, with MAE as an explicit fallback if the validation actual total is zero. Ties favor a baseline. The selected tree is evaluated even if a baseline wins, so its weaknesses remain visible. `deployment_model.joblib` is a **separate refit using all complete history after evaluation** and is never used for reported test scores.

**MAE** is the average absolute error, in units per product-week. **WAPE** is `sum(abs(actual - forecast)) / sum(actual)`, displayed as a percentage. WAPE emphasizes high-volume products; it is not “accuracy.” When the actual total is zero, WAPE is undefined and shown as N/A, even for a perfect all-zero prediction; MAE remains useful. Metrics are reported overall, by product, by horizon, and by product/horizon.

## Measured results

The reproducible run records exact results in [test metrics](reports/test_metrics.csv), [validation metrics](reports/validation_metrics.csv), [experiment metadata](reports/evaluation_summary.json), and [tree failure cases](reports/failure_cases.csv). The completed run's summary is also in [the project report](docs/project_report.md). Scores are historical offline errors, not evidence of cost savings or stockout reduction.

| Method | Validation MAE | Validation WAPE | Final-test MAE | Final-test WAPE |
|---|---:|---:|---:|---:|
| Previous week | 299.08 | 68.23% | 360.60 | 73.64% |
| **Trailing four-week average — selected** | **262.06** | **59.79%** | **289.72** | **59.17%** |
| Small random forest | 275.09 | 62.76% | 289.15 | 59.05% |
| Flexible random forest | 288.93 | 65.92% | Not selected for test | Not selected for test |

Each method was evaluated on 360 validation and 240 final-test product-weeks. **The baseline won validation and remains the default.** The tree's tiny test advantage does not justify switching after seeing the holdout. These are substantial errors; this is an honest prototype, not a production-accuracy claim. The small forest lost to at least one baseline on **22 of 30 products**. For example, product `84077` had tree MAE 887.13 versus previous-week MAE 686.75; product `21980` had tree MAE 280.39 versus trailing-average MAE 91.31.

On this Windows/Python 3.12.14 run, preparation took 61.10 seconds and validation/test/refit took 3.52 seconds, excluding installation and cold imports. These are observed local timings, not hardware-independent promises. The SQLite database is about 134 MB and the compressed deployment model about 0.30 MB.

## Inventory planning simulation

```text
lead_time_sales = sum(forecast[1 : lead_time_weeks])
suggested_order = ceil(max(0,
    lead_time_sales + safety_stock - current_stock - on_order))
```

Lead time is an integer **1–4 weeks**. Stock and safety stock are user assumptions in units. Forecasts remain fractional until the final order is rounded upward to a whole unit. Negative or nonfinite inputs are rejected.

**Arrival assumption:** count on-order stock only if it is usable when needed within the lead-time window. The app treats all entered incoming stock as meeting that assumption; it has no actual arrival dates. An order placed now arrives after the supplier lead time and cannot prevent a shortage occurring before then. This simplified target-stock calculation omits review-period buffers, backorders, reservations, expiry, minimum orders, case packs and carrying costs. Safety stock is user-supplied, not inferred as a service-level guarantee.

## Demo in five minutes

1. Open the app and explain that its forecast origin is historical. Show the data-quality counters and why their overlapping raw flags differ from sequential exclusions.
2. Select a product and inspect its weekly sales, spikes, seasonality and zero weeks. Show the four-week forecast and switch between the three methods.
3. Show validation scores, then untouched-for-selection test scores, including a product where the forest loses to a baseline. Explain MAE in units and WAPE as relative absolute error.
4. Enter current stock, incoming stock, lead time and safety stock. Increase current stock until the suggestion reaches zero. Explain when incoming stock is allowed to count.
5. Open `features.py` to show `shift(1)`, the recursive forecast loop, and a leakage test. Finish with the demand/stockout limitation.

The automated app test uses Streamlit AppTest and exercises product/method choices and inventory inputs; with no local artifacts, its full-data scenario is skipped explicitly. Run tests again after training to include that scenario.

The interface and charts prefer locally installed **Helvetica Neue / Helvetica**, falling back to **Arial** and then the system sans-serif font. Helvetica is not bundled or downloaded; on Windows systems without Helvetica installed, Arial renders the interface. Visual styling is isolated in `stocksense/ui.py`, so presentation changes do not affect forecasting or inventory calculations.

**Executed verification: 48 tests passed, with no skips after training.** Recomputed evaluation metrics matched the saved predictions, and `pip check` reported no broken requirements. See [the verification record](reports/verification.md) for timings and artifact fingerprints.

## Limitations and next steps

Observed sales are only a proxy for demand: lost sales caused by stockouts are unavailable. Historical data from one gift retailer, a high-volume cohort, only about two years of seasonality, large wholesale orders, changing assortment and a holiday-heavy final test limit generalization. Product identifiers may differ by case; they are deliberately not merged without an authoritative catalogue. The date grid assumes the interior recording period is complete. Cleaning decisions are documented source-level rules, not thresholds optimized against test performance.

There are no prediction intervals, causal business-impact estimates or automatic purchases. Recursive errors can accumulate; trees can smooth or miss new spikes. Reasonable future experiments are broader rolling-year holdouts, promotion/availability data, probabilistic forecasts and inventory simulation with real arrival dates. They require a new untouched evaluation period if used to tune models after viewing these test scores.

See [the short project report](docs/project_report.md), [three verified resume bullets](docs/resume_bullets.md), and [ten code-grounded interview questions](docs/interview_questions.md).
