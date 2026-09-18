# Executed verification

Environment: Windows 11, Python 3.12.14, direct pinned dependencies recorded in `environment.json`; transitive versions in `../requirements-lock.txt`.

| Check | Actual result |
|---|---|
| Official UCI workbook download | 45,622,278-byte workbook obtained from the official UCI archive; both yearly sheets inspected |
| Pinned-environment `python -m stocksense prepare` | Passed; 1,003,357 retained rows, 30 products, 104 complete weeks, 3,120 product-weeks; 61.10 seconds |
| `python -m stocksense train` | Passed; three validation origins, two final-test origins, saved deployment tree and all evaluation artifacts; 3.52 seconds |
| `python -m stocksense evaluate` | Passed; recomputed metrics agree with saved prediction-level results |
| `python -m pytest -q` after artifacts existed | **48 passed in 7.18 seconds**, no skipped tests |
| `python -m pip check` | No broken requirements found |
| Streamlit server | Started successfully at `http://127.0.0.1:8501` |
| Browser rendering | Verified actual dashboard, Plotly history/forecast chart, baseline-selected default, 30 products, 104 weeks, historical origin, and inventory suggestion in the local browser |

The tests use deliberately constructed fixtures only for correctness. Forecast scores use the real UCI workbook. The full app test loads the real prepared database and model, switches through all three forecast methods, changes product and chart horizon, changes all four inventory inputs, and checks that sufficient stock produces a zero replenishment suggestion. It also covers missing-data setup and stale-artifact handling.

The raw workbook SHA-256 is `bcbe73b35f5b7babf197fb0cb983a11f5d9ff929078d4aa53d171b1f2df2e980`. Prepared weekly-panel SHA-256 is `69023bbf95f733bee74584f0ce8787000e2bd9941ef9996c41f6b831d23e06f2`.
