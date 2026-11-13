import gzip
import os
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest

from arena.domains.markets import GRACE, MarketsDomain, markets_domain_from_rates
from arena.models import Resolution, Void, canonical_json
from arena.sources.ecb import parse_csv

FIX = Path(__file__).parents[1] / "fixtures" / "ecb" / "exr_usd_jpy_2019-01-01.csv.gz"
GOLDEN = Path(__file__).parents[1] / "fixtures" / "golden" / "markets"
RATES = parse_csv(gzip.decompress(FIX.read_bytes()).decode())


def dom(skips: list[str] | None = None) -> MarketsDomain:
    on_skip = skips.append if skips is not None else None
    return markets_domain_from_rates(RATES, "fixture://ecb", "e" * 64, on_skip=on_skip)


def gen(b: date, skips=None):
    return dom(skips).generate_questions(b, datetime.combine(b, time(5, 30), tzinfo=UTC))


CASES = {"friday": date(2026, 11, 6), "before_easter": date(2026, 4, 2)}


@pytest.mark.parametrize("name", sorted(CASES))
def test_golden(name: str) -> None:
    got = "".join(canonical_json(q) for q in gen(CASES[name]))
    path = GOLDEN / f"{name}.jsonl"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(got, encoding="utf-8")
    assert got == path.read_text(encoding="utf-8")


def test_friday_batch_targets_monday() -> None:
    qs = gen(date(2026, 11, 6))
    assert {q.template for q in qs} == {"absmove_gt", "up"} and len(qs) == 4
    assert all(q.target_date == date(2026, 11, 9) for q in qs)
    assert all(q.resolve_after == datetime(2026, 11, 9, 16, tzinfo=UTC) for q in qs)


def test_weekend_and_holiday_have_no_questions() -> None:
    skips: list[str] = []
    assert gen(date(2026, 11, 7), skips) == [] and gen(date(2026, 11, 8), skips) == []
    assert gen(date(2026, 4, 3), skips) == []  # Good Friday
    assert gen(date(2026, 4, 6), skips) == []  # Easter Monday
    assert gen(date(2025, 12, 25), skips) == []
    assert all("publication day" in s for s in skips)
    assert {q.target_date for q in gen(date(2026, 4, 2))} == {date(2026, 4, 7)}


def test_fixing_of_batch_day_not_visible_at_lock() -> None:
    d = dom()
    q = gen(date(2026, 11, 6))[0]
    ctx = d.context(q, q.lock_time)
    assert max(f["day"] for f in ctx["fixings"]) == "2026-11-05"


def test_resolution() -> None:
    d = dom()
    qs = {q.template + q.entity: q for q in gen(date(2026, 11, 6))}
    up = d.resolve(qs["upEUR_USD"], qs["upEUR_USD"].resolve_after)
    assert isinstance(up, Resolution)
    assert up.evidence.values_used["f0"] == RATES["USD"][date(2026, 11, 6)]
    assert up.outcome == int(RATES["USD"][date(2026, 11, 9)] > RATES["USD"][date(2026, 11, 6)])
    mv = d.resolve(qs["absmove_gtEUR_JPY"], qs["absmove_gtEUR_JPY"].resolve_after)
    assert isinstance(mv, Resolution) and mv.outcome == int(
        mv.observed_value > qs["absmove_gtEUR_JPY"].threshold
    )
    assert d.resolve(qs["upEUR_USD"], qs["upEUR_USD"].resolve_after - timedelta(seconds=1)) is None


def test_missing_fixing_voids_after_grace() -> None:
    q = gen(date(2026, 11, 11))[0]  # F1 = 12 Nov: not in the fixture
    d = dom()
    assert d.resolve(q, q.resolve_after) is None
    v = d.resolve(q, q.resolve_after + GRACE)
    assert isinstance(v, Void) and v.reason_code == "source_missing"
