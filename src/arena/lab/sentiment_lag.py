"""How news tone and article volume line up with crypto moves, by day offset (T402).

For a move on day D (the question's move: the price at 00:00 UTC of D+1 against 00:00 UTC of D)
and a GDELT day X = D + k: the pooled Pearson correlation of the article-volume surprise with the
absolute move, and of the per-coin demeaned tone with the signed move. News after the move
(k = +1) reacts to it; the as-of rule of `sentiment` only allows a question on batch day B to see
day B-2 for the move of day B+1, that is k = -3. Descriptive, offline, from the recorded fixtures;
it changes no decision of the pre-registration (`lab/prereg/sentiment.md`), which stays as
evaluated.

Days with no articles (count 0) and GDELT-wide outages (no count for any coin) are left out, the
r2 rules of `arena.forecasters.sentiment`.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, timedelta

import numpy as np

from arena.backtest.sentiment import News
from arena.forecasters.sentiment import outage_days

OFFSETS = (1, 0, -1, -2, -3)
PRIOR = 7


def _corr(a: list[float], b: list[float]) -> float | None:
    if len(a) < 30:
        return None
    x, y = np.asarray(a), np.asarray(b)
    if x.std() == 0 or y.std() == 0:
        return None
    return float(np.corrcoef(x, y)[0, 1])


def lag_table(
    prices: Mapping[str, Mapping[date, float]], news: Mapping[str, News]
) -> list[dict[str, float | int | None]]:
    """Per offset k: correlations and pair counts, pooled over the coins."""
    covered = set().union(*(n.covered_count for n in news.values()))
    out_days = outage_days({c: n.count for c, n in news.items()}, covered)
    tone_mean = {
        c: float(np.mean([v for d, v in n.tone.items() if n.count.get(d, 0) > 0] or [0.0]))
        for c, n in news.items()
    }
    rows: list[dict[str, float | int | None]] = []
    for k in OFFSETS:
        vol_x: list[float] = []
        absr: list[float] = []
        tone_x: list[float] = []
        ret: list[float] = []
        for coin, n in news.items():
            p = prices[coin]
            for d in sorted(p):
                nxt = d + timedelta(days=1)
                if nxt not in p:
                    continue
                r = p[nxt] / p[d] - 1.0  # the move of day D: 00:00 UTC of D to 00:00 UTC of D+1
                x = d + timedelta(days=k)
                if x in out_days or n.count.get(x, 0) <= 0:
                    continue
                prior = [
                    n.count[x - timedelta(days=i)]
                    for i in range(1, PRIOR + 1)
                    if n.count.get(x - timedelta(days=i), 0) > 0
                ]
                if len(prior) >= 4:
                    vol_x.append(math.log((n.count[x] + 1.0) / (sum(prior) / len(prior) + 1.0)))
                    absr.append(abs(r))
                if x in n.tone:
                    tone_x.append(n.tone[x] - tone_mean[coin])
                    ret.append(r)
        rows.append(
            {
                "offset": k,
                "corr_volume_abs_move": _corr(vol_x, absr),
                "n_volume": len(vol_x),
                "corr_tone_move": _corr(tone_x, ret),
                "n_tone": len(tone_x),
            }
        )
    return rows
