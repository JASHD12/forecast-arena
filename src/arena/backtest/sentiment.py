"""Walk-forward backtest of `sentiment-gdelt-r1` (T374), as pre-registered in
``lab/prereg/sentiment.md`` (registered before this module existed).

Questions, contexts and outcomes come from the real crypto domain (`CryptoDomain`:
``generate_questions``, ``context``, ``resolve``) built from the recorded CoinGecko history. The
GDELT numbers are the recorded raw responses (``tests/fixtures/gdelt/history``), put through
the as-of rule of ``arena.sources.gdelt_tone`` (a day counts from the next day 12:00 UTC, so a
morning run on day B sees days up to B-2). The first test day is price-history day 120
(2026-03-12), the model is refit every 7 days on questions whose outcomes were known that
morning (batch days up to two days earlier, so no gap-day outcome leaks) and the arms are
compared on identical questions. A question without usable GDELT numbers is not scored for any
arm and is counted. This is a backtest (I4): it never enters a live score.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from arena.domains.crypto import COINS, CryptoDomain
from arena.forecasters import sentiment as S
from arena.forecasters.baselines import MIN_INSTANCES, laplace
from arena.forecasters.ml_crypto import CryptoModel
from arena.models import Resolution
from arena.scoring.stats import paired_brier_difference
from arena.sources import gdelt_tone as G

MORNING = time(5, 30)
FIRST_QUESTION_DAY = date(2026, 1, 1)
FIRST_TEST_DAY = date(2026, 3, 12)  # price-history day 120 (day 1 = 2025-11-13)
REFIT_EVERY = 7
GAP_DAYS = 2
MIN_TEST = 800
BASE_WINDOW = 90
FAR = datetime.max.replace(tzinfo=UTC)
_CHUNK = re.compile(
    r"^(?P<coin>[a-z]+)_(?P<mode>timelinetone|timelinevolraw)_(\d{8})_(\d{8})\.json$"
)


@dataclass
class News:
    """Recorded GDELT numbers of one coin and which days were actually recorded."""

    tone: dict[date, float] = field(default_factory=dict)
    count: dict[date, int] = field(default_factory=dict)
    covered_count: set[date] = field(default_factory=set)
    covered_tone: set[date] = field(default_factory=set)


def load_news(history_dir: Path) -> dict[str, News]:
    """Parse every recorded chunk; a day is 'covered' only when its chunk was recorded."""
    out = {c: News() for c in COINS}
    for path in sorted(history_dir.glob("*_timeline*.json")):
        m = _CHUNK.match(path.name)
        if not m or m["coin"] not in out:
            continue
        a = datetime.strptime(m[3], "%Y%m%d").replace(tzinfo=UTC).date()
        b = datetime.strptime(m[4], "%Y%m%d").replace(tzinfo=UTC).date()
        days = {a + timedelta(days=i) for i in range((b - a).days + 1)}
        payload = json.loads(path.read_text("utf-8"))
        news = out[m["coin"]]
        if m["mode"] == "timelinetone":
            news.tone.update(G.parse_tone(payload))
            news.covered_tone |= days
        else:
            counts, _ = G.parse_counts(payload)
            news.count.update(counts)
            news.covered_count |= days
    return out


@dataclass
class Row:
    """One question of the backtest."""

    day: date
    coin: str
    template: str
    outcome: int
    p_ml: float
    base: float
    vec: list[float] | None
    why: str


def build_rows(domain: CryptoDomain, news: dict[str, News], last: date) -> list[Row]:
    """Every crypto question from FIRST_QUESTION_DAY to `last` with its as-of features."""
    ml = CryptoModel()
    rows: list[Row] = []
    known: dict[tuple[str, str], list[tuple[datetime, date, int]]] = {}
    b = FIRST_QUESTION_DAY
    while b <= last:
        asof = datetime.combine(b, MORNING, tzinfo=UTC)
        for q in domain.generate_questions(b, asof):
            if q.template not in S.TEMPLATES:
                continue
            res = domain.resolve(q, FAR)
            if not isinstance(res, Resolution):
                continue
            past = [
                o
                for (ra, td, o) in known.get((q.template, q.entity), [])
                if ra <= asof and td < q.target_date
            ][-BASE_WINDOW:]
            base = laplace(sum(past), len(past)) if len(past) >= MIN_INSTANCES else 0.5
            ctx = domain.context(q, asof)
            p_ml = ml.probability(q, ctx)
            n = news[q.entity]
            ctx["gdelt"] = S.gdelt_context(n.tone, n.count, n.covered_count, asof)
            vec, why = S.features(q.template, ctx["gdelt"], p_ml)
            rows.append(Row(b, q.entity, q.template, res.outcome, p_ml, base, vec, why))
            known.setdefault((q.template, q.entity), []).append(
                (q.resolve_after, q.target_date, res.outcome)
            )
        b += timedelta(days=1)
    return rows


def walk_forward(rows: list[Row], first_test: date = FIRST_TEST_DAY) -> list[tuple[Row, float]]:
    """(row, sentiment probability) for every test question that has features and a model."""
    out: list[tuple[Row, float]] = []
    last_day = max(r.day for r in rows)
    refit = first_test
    day = first_test
    models: dict[str, S.SentimentModel | None] = {}
    while day <= last_day:
        if (day - first_test).days % REFIT_EVERY == 0:
            refit = day
            models = {}
            for t in S.TEMPLATES:
                train = [
                    r
                    for r in rows
                    if r.template == t
                    and r.vec is not None
                    and r.day <= refit - timedelta(GAP_DAYS)
                ]
                models[t] = S.fit(t, [r.vec for r in train if r.vec], [r.outcome for r in train])
        for r in rows:
            if r.day != day or r.vec is None:
                continue
            m = models.get(r.template)
            if m is not None:
                out.append((r, m.probability(r.vec)))
        day += timedelta(days=1)
    return out


def _brier(p: list[float], y: list[int]) -> float:
    return sum((a - b) ** 2 for a, b in zip(p, y, strict=True)) / len(y)


def summarise(rows: list[Row], scored: list[tuple[Row, float]]) -> dict[str, Any]:
    """Metrics, paired intervals and counts per template, from the walk-forward output."""
    metrics: dict[str, dict[str, float | int | str | None]] = {}
    paired: list[dict[str, Any]] = []
    notes: list[str] = []
    for t in S.TEMPLATES:
        test_rows = [r for r in rows if r.template == t and r.day >= FIRST_TEST_DAY]
        sub = [(r, p) for r, p in scored if r.template == t]
        metrics[f"questions / {t}"] = {
            "n": len(test_rows),
            "without_gdelt_features": sum(1 for r in test_rows if r.vec is None),
            "no_model_yet": sum(1 for r in test_rows if r.vec is not None) - len(sub),
        }
        if not sub:
            metrics[f"sentiment / {t}"] = {"n": 0}
            notes.append(f"{t}: no scored question (no model could be fitted yet)")
            continue
        y = [r.outcome for r, _ in sub]
        days = [r.day for r, _ in sub]
        arms: dict[str, list[float]] = {
            "sentiment": [p for _, p in sub],
            "ml": [r.p_ml if t == "bigmove" else 0.5 for r, _ in sub],
            "base_rate": [r.base for r, _ in sub],
            "always_0.5": [0.5] * len(sub),
        }
        for name, p in arms.items():
            metrics[f"{name} / {t}"] = {"n": len(sub), "brier": round(_brier(p, y), 4)}
        for other in ("ml", "base_rate", "always_0.5"):
            if t == "up" and other == "ml":
                continue  # `ml` answers 0.5 for `up`: identical to always_0.5
            iv = paired_brier_difference(days, arms["sentiment"], arms[other], y)
            paired.append(
                {
                    "a": "sentiment",
                    "b": other,
                    "split": t,
                    "diff": round(iv.estimate, 5),
                    "lo": round(iv.low, 5),
                    "hi": round(iv.high, 5),
                    "n": iv.n,
                    "days": iv.days,
                }
            )
        if len(sub) < MIN_TEST:
            notes.append(f"{t}: {len(sub)} scored questions, fewer than {MIN_TEST}: inconclusive")
    return {"metrics": metrics, "paired": paired, "notes": notes}


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
