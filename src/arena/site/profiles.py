"""Forecaster profile pages (T132): what a forecaster sees, its versions, scores over time,
calibration, best and worst calls, skips and (for AI forecasters) model calls and cost.

Display only: every number is computed from the ledger here; the headline comparisons
with intervals stay on the leaderboard (`arena.scoring`).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Any

from arena.scoring.core import Record, Scored, brier, log_score
from arena.scoring.stats import calibration_bins, expected_calibration_error
from arena.site.charts import race_svg, reliability_svg
from arena.site.llm_obs import UsageRow

#: Model cards in the repository (docs/models) per forecaster.
MODEL_CARDS: dict[str, list[tuple[str, str]]] = {
    "ml": [
        ("Electricity", "docs/models/power.md"),
        ("Attention", "docs/models/attention.md"),
        ("Markets", "docs/models/markets.md"),
    ],
}
CALLS = 5


def _cumulative(ss: Sequence[Scored]) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    tot, n = 0.0, 0
    for day in sorted({s.batch_date for s in ss}):
        day_ss = [s for s in ss if s.batch_date == day]
        tot += sum((min(max(s.probability, 0.01), 0.99) - s.outcome) ** 2 for s in day_ss)
        n += len(day_ss)
        out.append((day.isoformat(), tot / n))
    return out


def profile(
    fid: str,
    rec: Record,
    names: dict[str, str],
    changelog: Sequence[dict[str, Any]],
    usage: Sequence[UsageRow],
    info: dict[str, tuple[str, str]],
) -> dict[str, Any]:
    """Everything the profile template shows for one forecaster."""
    mine = [s for s in rec.scored if s.forecaster_id == fid]
    base = {s.question_id: s for s in rec.scored if s.forecaster_id == "base_rate"}
    ps, ys = [s.probability for s in mine], [s.outcome for s in mine]
    out: dict[str, Any] = {
        "fid": fid,
        "sees": info.get(fid, ("", ""))[0],
        "cadence": info.get(fid, ("", ""))[1],
        "cards": MODEL_CARDS.get(fid, []),
        "versions": [r for r in changelog if r["forecaster"] == fid],
        "n_forecasts": sum(1 for f in rec.forecasts if f.forecaster_id == fid),
        "skips": dict(Counter(s.reason_code for s in rec.skips if s.forecaster_id == fid)),
        "n": len(mine),
        "brier": brier(ps, ys) if mine else None,
        "log": log_score(ps, ys) if mine else None,
        "topics": sorted({s.domain for s in mine}),
    }
    pairs = [(s, base[s.question_id]) for s in mine if s.question_id in base]
    if pairs and fid != "base_rate":
        out["base_brier"] = brier([b.probability for _, b in pairs], [b.outcome for _, b in pairs])
        out["brier_same"] = brier([s.probability for s, _ in pairs], [s.outcome for s, _ in pairs])
        out["n_same"] = len(pairs)
    series = {fid: _cumulative(mine)}
    if fid != "base_rate" and pairs:
        series["base_rate"] = _cumulative([b for _, b in pairs])
    days = sorted({d for pts in series.values() for d, _ in pts})
    out["race"] = race_svg(series, names, days) if len(days) >= 2 else None
    out["race_rows"] = series
    if len(mine) >= 10:
        bins = calibration_bins(ps, ys)
        out["calibration"] = {
            "svg": reliability_svg(fid, bins),
            "bins": bins,
            "ece": expected_calibration_error(ps, ys),
        }
    ranked = sorted(mine, key=lambda s: ((s.probability - s.outcome) ** 2, s.question_id))
    out["best"] = ranked[:CALLS]
    out["worst"] = list(reversed(ranked[-CALLS:])) if len(ranked) > CALLS else []
    rows = [u for u in usage if u.forecaster_id == fid]
    if rows:
        known = [u.cost_usd for u in rows if u.cost_usd is not None]
        out["usage"] = {
            "calls": sum(u.calls for u in rows),
            "tokens": sum(u.input_tokens + u.output_tokens for u in rows),
            "cost": sum(known) if known else None,
        }
    return out
