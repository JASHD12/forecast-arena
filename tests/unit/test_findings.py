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
    skills = {"ml": 0.3, "llm_plain": 0.0, "llm_context": 0.0, "agent": 0.0}
    clear = data(skills, "power") + data(skills, "weather")
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
    assert h3.key == "H3" and h3.status == UNDECIDED
    s2 = data({"base_rate": 0.0, "ml": 0.3}, "markets", template="up")
    assert findings(s2, 40)[2].status == CONTRADICTED
    assert findings(s, 40)[3].status == UNDECIDED  # no ensemble yet
    assert compare(s, "ml", "nobody") is None


def test_h1_requires_every_llm_comparison_and_numeric_domain_coverage() -> None:
    one_llm = data({"ml": 0.3, "llm_plain": 0.0}, "power")
    f = findings(one_llm, 40)[0]
    assert f.status == UNDECIDED
    assert "llm_context" in f.note and "agent" in f.note and "weather" in f.note
    power_only = data({"ml": 0.3, "llm_plain": 0.0, "llm_context": 0.0, "agent": 0.0}, "power")
    f = findings(power_only, 40)[0]
    assert f.status == UNDECIDED and "weather" in f.note
    assert all(c.domains == ("power",) and "on power" in c.sentence() for c in f.comparisons)
    # Missing other comparisons cannot erase a supported counterexample.
    loss = findings(data({"ml": 0.0, "llm_plain": 0.3}, "power"), 40)[0]
    assert loss.status == CONTRADICTED and "llm_context" in loss.note


def test_h3_and_h4_need_conclusive_comparisons_in_the_hypothesized_direction() -> None:
    h3 = findings(data({"base_rate": 0.3, "ml": 0.0}, "markets", template="up"), 40)[2]
    assert h3.status == SUPPORTED and all(c.interval.low > 0 for c in h3.comparisons)
    tied = data({"base_rate": 0.0, "ensemble": 0.0}, "power")
    assert findings(tied, 40)[3].status == UNDECIDED
    better = data({"base_rate": 0.0, "ensemble": 0.3}, "power")
    assert findings(better, 40)[3].status == SUPPORTED
    worse = data({"base_rate": 0.3, "ensemble": 0.0}, "power")
    assert findings(worse, 40)[3].status == CONTRADICTED
    # An observed competitor without a comparable question prevents an all-members claim.
    unpaired = data({"ml": 0.0}, "weather")
    assert findings(better + unpaired, 40)[3].status == UNDECIDED


def test_crossing_zero_intervals_never_support_h3_or_h4() -> None:
    # Exercise decision wording independently of random bootstrap outcomes.
    from unittest.mock import patch

    from arena.scoring.findings import Comparison
    from arena.scoring.stats import Interval

    samples = data({"base_rate": 0.0, "ml": 0.0, "ensemble": 0.0}, "markets", template="up")
    with patch("arena.scoring.findings.compare") as mocked:
        mocked.side_effect = lambda scored, a, b, *args: Comparison(
            a, b, 400, Interval(0.01, -0.2, 0.2, 400, 40), ("markets",)
        )
        result = findings(samples, 40)
    assert result[2].status == UNDECIDED and result[3].status == UNDECIDED
