# Backtest slices: where `ml` beats `persistence` (power)

BACKTEST, not the live record (run `power-2025-11-01-2026-10-31-20261112T1356`). Brier score per slice on the same questions; difference = `ml` minus `persistence` with a 95% day-block bootstrap interval (negative: `ml` is better). Slices under 20 questions are not described. "No supported difference" means the data cannot tell the two apart in that slice, not that they are equal; with this many slices, a few intervals will exclude zero by chance alone.

`persistence` is not clearly worse than `ml` in: template evening_gt, month 2025-11, month 2025-12, month 2026-01, month 2026-02, month 2026-04, month 2026-07, month 2026-08, month 2026-10, target day holiday. In the other slices with at least 20 questions `ml` is better with an interval that excludes zero.

**By template**

| Slice | n | days | ml Brier | persistence Brier | Difference | 95% interval | Verdict |
|---|---|---|---|---|---|---|---|
| evening_gt | 365 | 365 | 0.1995 | 0.2094 | -0.0100 | [-0.0288, +0.0093] | no supported difference |
| max_gt | 365 | 365 | 0.2066 | 0.2317 | -0.0251 | [-0.0436, -0.0060] | ml better |
| mean_gt | 365 | 365 | 0.1850 | 0.2212 | -0.0362 | [-0.0547, -0.0174] | ml better |
| min_lt | 365 | 365 | 0.1491 | 0.1817 | -0.0326 | [-0.0557, -0.0108] | ml better |
| spread_gt | 365 | 365 | 0.2092 | 0.2290 | -0.0198 | [-0.0391, -0.0005] | ml better |
| up_vs_today | 365 | 365 | 0.2085 | 0.2499 | -0.0413 | [-0.0598, -0.0208] | ml better |

**By month**

| Slice | n | days | ml Brier | persistence Brier | Difference | 95% interval | Verdict |
|---|---|---|---|---|---|---|---|
| 2025-11 | 174 | 29 | 0.2097 | 0.2056 | +0.0042 | [-0.0275, +0.0366] | no supported difference |
| 2025-12 | 186 | 31 | 0.2096 | 0.2178 | -0.0082 | [-0.0479, +0.0295] | no supported difference |
| 2026-01 | 186 | 31 | 0.1676 | 0.1836 | -0.0160 | [-0.0554, +0.0232] | no supported difference |
| 2026-02 | 168 | 28 | 0.1859 | 0.2134 | -0.0274 | [-0.0674, +0.0120] | no supported difference |
| 2026-03 | 186 | 31 | 0.1889 | 0.2248 | -0.0360 | [-0.0634, -0.0103] | ml better |
| 2026-04 | 180 | 30 | 0.1901 | 0.2129 | -0.0227 | [-0.0528, +0.0075] | no supported difference |
| 2026-05 | 186 | 31 | 0.1666 | 0.2127 | -0.0461 | [-0.0814, -0.0120] | ml better |
| 2026-06 | 180 | 30 | 0.1823 | 0.2609 | -0.0786 | [-0.1248, -0.0317] | ml better |
| 2026-07 | 186 | 31 | 0.2198 | 0.2278 | -0.0080 | [-0.0467, +0.0319] | no supported difference |
| 2026-08 | 186 | 31 | 0.2043 | 0.2357 | -0.0313 | [-0.0669, +0.0062] | no supported difference |
| 2026-09 | 180 | 30 | 0.2101 | 0.2453 | -0.0352 | [-0.0660, -0.0055] | ml better |
| 2026-10 | 186 | 31 | 0.1818 | 0.2084 | -0.0266 | [-0.0662, +0.0165] | no supported difference |
| 2026-11 | 6 | 1 | 0.1766 | 0.1288 | +0.0478 | [+0.0478, +0.0478] | too few questions |

**By target day**

| Slice | n | days | ml Brier | persistence Brier | Difference | 95% interval | Verdict |
|---|---|---|---|---|---|---|---|
| holiday | 54 | 9 | 0.1528 | 0.2032 | -0.0505 | [-0.1239, +0.0206] | no supported difference |
| weekday | 1512 | 252 | 0.1984 | 0.2215 | -0.0231 | [-0.0361, -0.0097] | ml better |
| weekend | 624 | 104 | 0.1834 | 0.2195 | -0.0362 | [-0.0571, -0.0169] | ml better |
