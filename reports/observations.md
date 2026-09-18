# Observations from the prepared real data

Generated from SQLite after fixed cleaning. These are descriptive observations, not model-selection evidence or causal claims.

- The selected cohort contains **30 products × 104 complete weeks = 3,120 product-weeks**.
- **84077 — WORLD WAR 2 GLIDERS ASSTD DESIGNS** leads training-period unit volume with **84,073 units**. Ranking uses the initial training period only.
- **141 of 3,120 product-weeks (4.5%)** have zero observed sales. Zeros do not distinguish stockouts, delisting, or no purchases.
- Calendar month **11** has the highest mean weekly cohort volume: **21,028.8 units**, from 9 week starts. The seasonal summary uses all complete weeks and only about two annual cycles.
- The largest selected product-week is **21982**, week of **2010-03-22**, at **11,414 units**. Large orders are retained, so aggregate errors may be strongly influenced by spikes.
- Monthly totals below cover **all cleaned products and countries**. The last month is partial; do not interpret its short total as a demand collapse.

| Month | All-product recorded units |
|---|---:|
| 2009-12 | 425,218 |
| 2010-01 | 390,414 |
| 2010-02 | 381,626 |
| 2010-03 | 525,043 |
| 2010-04 | 366,067 |
| 2010-05 | 395,438 |
| 2010-06 | 406,238 |
| 2010-07 | 337,556 |
| 2010-08 | 471,931 |
| 2010-09 | 583,367 |
| 2010-10 | 619,511 |
| 2010-11 | 724,265 |
| 2010-12 | 357,529 |
| 2011-01 | 386,738 |
| 2011-02 | 282,627 |
| 2011-03 | 376,182 |
| 2011-04 | 307,651 |
| 2011-05 | 394,653 |
| 2011-06 | 388,124 |
| 2011-07 | 399,291 |
| 2011-08 | 420,695 |
| 2011-09 | 568,701 |
| 2011-10 | 619,597 |
| 2011-11 | 746,952 |
| 2011-12 | 312,647 |

Cleaning issues and mutually exclusive exclusion counts: see `data_quality.json`. Gross sales are not net sales after returns and are only a proxy for demand.
