# Ten interview questions about StockSense

Use these explanations as a starting point, then demonstrate the named functions. The small test fixtures are deliberately constructed examples; the project's measured scores come only from the real UCI workbook.

1. **What exactly does your model predict?**

   It predicts positive recorded units for each selected product during a Monday–Sunday week. `clean_transactions()` removes cancellations and nonpositive quantities instead of subtracting returns from later weeks. This makes the target gross observed sales, not net revenue, net sales after returns, or true demand. The source has no stock availability or lost-sales records, so a zero-sales week cannot prove zero demand.

2. **What did inspecting the actual dataset change about your cleaning?**

   The two workbook sheets contain 1,067,371 rows, including missing customer IDs, exact duplicates, cancellations, invalid prices, and non-product charges. Alphabetic codes are not automatically invalid: `DCGS0058` describes a physical product. `data.py` therefore preserves identifiers as strings and uses an explicit non-product list. Missing customer IDs are retained because forecasting aggregate product sales does not require customer identity. Missing descriptions receive a display label; quantities and identifiers are never invented.

3. **Why fill missing weeks with zero and remove partial weeks?**

   A lag of one row means one week only when each product has a complete weekly calendar. `aggregate_weekly()` constructs that calendar and fills absent product-week transactions with zero recorded units. `complete_week_bounds()` drops incomplete boundary weeks. Otherwise, a short week may look like a sudden demand collapse. Zero filling is an assumption about observed records; delisting, stockouts, and genuine zero purchases remain indistinguishable.

4. **How did you prevent information leakage?**

   `select_products()` ranks products using initial training-period quantities only. `build_features()` groups by product, shifts sales, and then computes rolling statistics, so the target week cannot appear in its own predictors. Random forest training receives only history before each forecast origin. Tests change current/future sales and verify that earlier feature rows stay identical. Another test changes final-test actuals and verifies that validation metrics and the selected method stay unchanged.

5. **Why use rolling validation instead of a random split?**

   A random split can train on December while predicting October, which does not match deployment. `evaluate()` uses three consecutive four-week validation blocks and two final four-week test blocks. History expands between blocks. The method and tree configuration are selected before the final test is scored. Earlier test observations become usable at the next origin only after that block would have elapsed; this evaluates a fixed retraining policy, not one permanently frozen fitted estimator.

6. **How do you forecast four weeks without knowing next week's actual sales?**

   `forecast()` predicts week 1, appends that prediction to a temporary history, and repeats. Week 2's lag can therefore contain week 1's prediction. This is recursive forecasting, and the same implementation is used in backtests and the app. Errors can accumulate with horizon. The previous-week baseline stays constant across the four weeks; the trailing-four-week baseline updates its window with predictions as well.

7. **Why a random forest, and why might a baseline beat it?**

   The pooled `RandomForestRegressor` shares information across products, using one-hot product identity, lags, rolling mean/variability, and calendar features. It needs no GPU or scaling. Only two small configurations are tried to keep selection understandable. A forest averages training examples and may underpredict a new bulk-order spike or seasonal jump. A recent-sales baseline can adapt faster after a level change. `failure_cases.csv` reports actual products where the chosen tree has greater test MAE than a baseline; complexity is not a success criterion.

8. **What do MAE and WAPE tell you, and what do they hide?**

   MAE is the average absolute error in units per product-week forecast. WAPE is total absolute error divided by total actual units, stored as a fraction. It emphasizes high-volume products; it is not classification accuracy and need not be below 100%. `error_metrics()` returns undefined WAPE when actual volume is zero and still reports MAE. The same test records make overall MAE and WAPE rank methods identically. Product and horizon reports expose errors that an overall number can hide.

9. **How is the inventory recommendation calculated?**

   `replenishment_plan()` computes `ceil(max(0, forecast over lead time + safety stock - current stock - stock on order))`. The user supplies safety stock and a one-to-four-week lead time. Incoming stock is assumed to arrive before it is needed; a newly suggested order arrives at the end of the lead time. This aggregate calculation cannot guarantee that stock lasts until delivery. It is a planning simulation, with no claims about actual cost savings or stockout reduction.

10. **How would you demonstrate engineering quality and improve the project next?**

    Show the download/inspect/prepare/train commands, inspect the SQLite `weekly_sales` table, and demonstrate the saved metrics and app. The tests cover code preservation, weekly boundaries, missing weeks, causal features, recursive prediction, split isolation, and inventory arithmetic. Pinned dependencies and seed 42 improve reproducibility. A sensible next step would be collecting stock availability and arrival dates, then evaluating probabilistic forecasts and inventory outcomes under a specified service objective. These are future work, not features or achievements claimed by this project.
