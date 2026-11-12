import random
from datetime import date, timedelta

from arena.scoring.core import Scored
from arena.scoring.findings import (
    CONTRADICTED,
    SUPPORTED,
    TOO_EARLY,
    UNDECIDED,
    compare,
    findings,
)

START = date(2026, 1, 1)


def data(
    skills: dict[str, float],
    domain: str,
    template: str = "mean_gt",
    days: int = 40,
    per_day: int = 10,
    seed: int = 0,
) -> list[Scored]:
    rng = random.Random(seed)
    out = []
    for d in range(days):
        for i in range(per_day):
            qid = f"{domain}-{template}-E{i}-{d}-v1"
            y = int(rng.random() < 0.5)
            for fid, sk in skills.items():
                noise = rng.uniform(-0.05, 0.05)
                p = 0.5 + (sk if y else -sk) + noise
                out.append(Scored(qid, fid, "1", domain, START + timedelta(days=d), p, y))
    return out


def test_too_early_before_30_days() -> None:
    fs = findings(data({"ml": 0.3, "llm_plain": 0.0}, "power"), official_days=12)
    assert all(f.status == TOO_EARLY for f in fs)


def test_h1_supported_only_with_interval_excluding_zero() -> None:
    clear = data({"ml": 0.3, "llm_plain": 0.0, "llm_context": 0.0, "agent": 0.0}, "power")
    assert findings(clear, 40)[0].status == SUPPORTED
    tied = data({"ml": 0.0, "llm_plain": 0.0, "llm_context": 0.0, "agent": 0.0}, "power")
    f = findings(tied, 40)[0]
    assert f.status == UNDECIDED
    assert all("no supported difference" in c.sentence() for c in f.comparisons)
    worse = data({"ml": -0.2, "llm_plain": 0.2, "llm_context": 0.0, "agent": 0.0}, "weather")
    assert findings(worse, 40)[0].status == CONTRADICTED


def test_no_statement_claims_support_unless_interval_excludes_zero() -> None:
    for seed in range(5):
        s = data(
            {"ml": 0.02, "llm_plain": 0.0, "agent": 0.01, "base_rate": 0.0},
            "power",
            days=35,
            per_day=3,
            seed=seed,
        )
        s += data({"agent": 0.02, "ml": 0.0}, "attention", days=35, per_day=3, seed=seed)
        for f in findings(s, 35):
            for c in f.comparisons:
                said_better = "had the lower Brier score" in c.sentence()
                assert said_better == c.interval.excludes_zero
            if f.status in (SUPPORTED, CONTRADICTED) and f.key in ("H1", "H2"):
                assert (
                    all(c.interval.excludes_zero for c in f.comparisons) or f.status == CONTRADICTED
                )


def test_h3_and_h4() -> None:
    s = data({"base_rate": 0.0, "ml": 0.0}, "markets", template="up")
    h3 = findings(s, 40)[2]
    assert h3.key == "H3" and h3.status == SUPPORTED
    s2 = data({"base_rate": 0.0, "ml": 0.3}, "markets", template="up")
    assert findings(s2, 40)[2].status == CONTRADICTED
    assert findings(s, 40)[3].status == UNDECIDED  # no ensemble yet
    assert compare(s, "ml", "nobody") is None
