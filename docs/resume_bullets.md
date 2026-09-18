# Three verified resume bullets

- Built **StockSense**, a Python/pandas and SQLite pipeline processing **1,067,371 real UCI retail rows** into **1,003,357 cleaned transactions** and a **30-product, 104-week** sales forecasting panel.
- Compared two sales baselines with a pooled random forest using **three rolling validation blocks and two held-out test blocks**; selected the trailing four-week average on validation, achieving **289.72-unit MAE and 59.17% WAPE** on 240 final-test product-weeks.
- Developed a **Streamlit/Plotly inventory planning simulator** with recursive 1–4-week forecasts, auditable replenishment calculations and **48 passing tests** covering data quality, temporal leakage, metric edge cases and app interactions.

Evidence: `reports/data_quality.json`, `reports/evaluation_summary.json`, `reports/test_metrics.csv`, and `reports/verification.md`. These are historical offline results; do not describe WAPE as accuracy or claim actual cost savings, fewer stockouts, a deployed production system, or that the forest won validation.
