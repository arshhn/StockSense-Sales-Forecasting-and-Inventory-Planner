# StockSense — short project report

## Objective and scope

StockSense forecasts weekly product sales and converts forecasts into a transparent inventory planning simulation. It is a CPU-only student project built with pandas, SQLite, scikit-learn, Streamlit, and Plotly. The default scope is 30 high-volume products, with sales pooled across all countries. This keeps the application understandable and narrows the evaluation claim: results describe these selected products, not all products or all retailers.

Data comes from [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii), contributed by Daqing Chen, [DOI 10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D). The source's real workbook is used for all reported results. Tests use small, explicitly constructed examples to check arithmetic and invariants, not to estimate forecast accuracy.

## What inspection showed and how it informed preparation

`reports/source_inspection.json` records two sheets, 1,067,371 rows, and dates from 1 December 2009 to 9 December 2011. The initial inspection found 34,335 exact duplicates, 243,007 missing customer IDs, 4,382 missing descriptions, 19,494 cancellation rows, 22,950 negative-quantity rows, and 6,207 nonpositive prices. These flags overlap and must not be added together as a count of distinct bad rows.

`clean_transactions()` excludes exact duplicates, missing essential identifiers/dates, cancellation invoices, nonpositive or invalid quantities/prices, and explicit non-product codes such as postage, fees, discounts, gift vouchers, and tests. The real run retains 1,003,357 rows. Separate disjoint exclusion counts reconcile raw and clean row totals. Exact duplicate removal is an assumption because the source has no unique line-item ID. Anonymous customer purchases remain useful for product forecasting. Missing descriptions become `Unknown description`, a display label only.

Product identifiers are text throughout Excel ingestion, pandas, SQLite, and artifact reads. A numeric-only filter would incorrectly discard physical products such as `DCGS0058`. Returns are audited and excluded rather than subtracted. Positive outliers are retained because a large order is not automatically an error. This means the target is gross observed positive sales and can include an order subsequently returned or cancelled; it is not net demand after invoice reconciliation.

The pipeline sums units into Monday–Sunday weeks and drops incomplete boundary weeks. The real run has 104 complete weeks, or 3,120 product-weeks; 141 (4.5%) have zero recorded sales. It builds a rectangular product-by-week calendar and fills missing observations with zero recorded sales. This is needed for lags to refer to calendar weeks, but does not imply that latent demand was zero. Sales lost during stockouts, delisting periods, and unavailable inventory cannot be identified from this dataset. The 30 products are selected by initial training-period unit volume with at least 26 active weeks; later sales and descriptions do not choose the cohort.

## Forecasting and evaluation decisions

Two baselines predict the previous week's sales and a trailing four-week average. A pooled random forest uses product identity, lags at 1/2/4/8 weeks, shifted rolling mean/standard deviation, and known calendar features. All sales features are grouped by product and shifted before aggregation. The first eight weeks have insufficient lag history and do not become fitted training examples. Two modest tree configurations and random seed 42 keep training reproducible and laptop-friendly; no XGBoost dependency is needed.

Validation uses three nonoverlapping four-week blocks, each fitted on all earlier history. The lowest validation WAPE selects the method, with MAE used if actual volume is zero and a baseline preferred on exact ties. The final eight weeks are reserved for reporting. They form two four-week blocks: after the first block has elapsed, its actuals can enter the next training history. This is a fixed expanding-history evaluation policy. Test errors never choose the method or hyperparameters.

Within every block, weeks 1–4 are predicted recursively: a later prediction uses earlier predictions, never future actual sales. The trailing-average baseline follows this same recursive convention. The deployment tree is refitted on all complete observed weeks only after evaluation and is a separate artifact from the fits that generated test scores.

MAE reports units of average absolute error. WAPE divides absolute error totals by actual unit totals; zero-volume groups receive undefined WAPE and a usable MAE. Reports include overall, product, horizon, and product-by-horizon metrics. `failure_cases.csv` lists every product/baseline pair where the selected tree has higher test MAE, preventing an aggregate improvement from hiding weaker cases.

## Measured results and failure cases

The pinned Python 3.12.14 run used 84 initial training weeks (2009-12-07–2011-07-11), 12 validation weeks (2011-07-18–2011-10-03), and eight final-test weeks (2011-10-10–2011-11-28). Dates label Monday-start weeks. There were 360 validation and 240 final-test predictions per evaluated method.

| Method | Validation MAE | Validation WAPE | Test MAE | Test WAPE |
|---|---:|---:|---:|---:|
| Previous week | 299.08 | 68.23% | 360.60 | 73.64% |
| Trailing four-week average | **262.06** | **59.79%** | 289.72 | 59.17% |
| Small random forest | 275.09 | 62.76% | 289.15 | 59.05% |
| Flexible random forest | 288.93 | 65.92% | Not evaluated | Not evaluated |

The trailing-average baseline won validation and remains the app default. The small forest was the stronger tree candidate; its tiny test advantage does not justify changing the selected method after seeing the holdout. No significance claim is made from this short test. The large WAPE values show why these forecasts should be treated as uncertain planning inputs.

The forest had higher test MAE than at least one baseline for **22 of 30 products**. Product `84077` had forest MAE **887.13 units**, versus **686.75** for previous week. For `21980`, the forest had MAE **280.39** versus **91.31** for the trailing average. Its mean actual sales were **84.875 units/week**, while the forest predicted **365.26** on average. Its fourth forecast in the first test block reached **1,195.89** against an actual **112**. This directly demonstrates overprediction and an unstable recursive path for that case; it does not establish which feature caused the error. Product `21975` also shows overprediction: mean actual **137.625**, mean forest prediction **327.65**, and tree MAE **198.32** versus previous-week MAE **42.38**.

All numbers above come from saved predictions and metrics under `artifacts/`, with small shareable copies under `reports/`. Preparation took **61.10 seconds** and validation/test/deployment refit **3.52 seconds** on this machine, excluding installation and cold imports. The compressed tree is approximately **0.30 MB**. These timings are local measurements, not universal performance guarantees.

## Inventory interpretation and limitations

The planner calculates `ceil(max(0, lead-time forecast + safety stock - current stock - on-order stock))`. Users enter hypothetical stock, incoming stock, whole-week lead time, and safety stock. Incoming units are assumed to arrive before needed within the lead time; a new order arrives at its end. This aggregate formula does not track daily availability, arrival schedules, pack sizes, order minimums, costs, or service levels. It cannot establish whether a stockout occurs before delivery.

The app provides descriptive sales/seasonality views, training-period top products, data-quality counts, product forecasts, baseline comparison, failure cases, and inventory inputs. Exploration uses the available historical sample and does not drive model selection. About two annual cycles, only eight test weeks, product selection toward established high-volume items, and bulk-order spikes limit generalization. Point forecasts have no calibrated uncertainty intervals. No actual business savings or stockout reductions are claimed.

**48 tests passed**, including a real-artifact Streamlit AppTest that changes methods, product, horizon and inventory assumptions. Checks cover cleaning rules (including nullable missing numeric values), string identifiers through SQLite, complete-week boundaries, zero filling, training-only product selection, feature causality, recursive inference, final-test isolation, metric edge cases, stale artifacts and replenishment arithmetic. The evaluation command independently recalculated saved final-test metrics from predictions and matched them within numerical tolerance. See the README for reproducible commands.
