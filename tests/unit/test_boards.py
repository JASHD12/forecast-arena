import random
from datetime import date, timedelta

import pytest

from arena.scoring.boards import COMMON_GROUP, TOO_EARLY, board, official
from arena.scoring.core import Scored

START = date(2026, 1, 1)
SKILLS = dict.fromkeys(COMMON_GROUP, 0.0) | {"ml": 0.2, "agent": 0.3}


def make(
    days: int,
    per_day: int,
    forecasters: dict[str, float],
    seed: int = 0,
    domain: str = "power",
    skip: dict[str, set[int]] | None = None,
) -> list[Scored]:
    rng = random.Random(seed)
    out = []
    for d in range(days):
        for i in range(per_day):
            qid = f"{domain}-q-{d}-{i}"
            y = int(rng.random() < 0.5)
            for fid, skill in forecasters.items():
                if skip and (d * per_day + i) in skip.get(fid, set()):
                    continue
                p = 0.5 + (skill if y else -skill)
                out.append(Scored(qid, fid, "1", domain, START + timedelta(days=d), p, y))
    return out


def test_common_set_is_the_intersection() -> None:
    s = make(40, 10, SKILLS, skip={"agent": set(range(0, 400, 2))})
    b = board(s, "common")
    assert b.questions == 200 and set(b.forecasters) == set(COMMON_GROUP)
    assert b.missing_forecasters == []
    assert all(r.n == 200 for r in b.rows)
    assert board(s, "all").questions == 400  # agent is not in the all-questions group


def test_too_early_to_tell() -> None:
    small = make(10, 5, SKILLS)
    assert board(small, "common").label == TOO_EARLY  # under 30 days
    many_days_few = make(40, 1, SKILLS)
    assert board(many_days_few, "common").label == TOO_EARLY  # 200 < 300 forecasts
    big = make(40, 10, SKILLS)
    assert board(big, "common").label is None
    assert board(big, "common", official_days=20).label == TOO_EARLY


def test_supported_only_when_interval_excludes_zero() -> None:
    b = board(make(40, 10, SKILLS), "common")
    v = {r.forecaster_id: r.verdict for r in b.rows}
    assert v["ml"] == "supported: better than base_rate"
    assert v["llm_plain"] == "no supported difference from base_rate"
    assert v["base_rate"] == "reference"


def test_per_domain_and_official_filter() -> None:
    s = make(40, 10, SKILLS) + make(40, 10, {"base_rate": 0.0}, domain="weather")
    assert board(s, "common", "weather").questions == 0
    assert board(s, "common", "power").questions == 400
    assert official(s, None) == []
    assert len(official(s, START + timedelta(days=30))) == len(s) // 4


@pytest.mark.parametrize("missing", COMMON_GROUP)
def test_missing_required_member_cannot_shrink_the_headline_group(missing: str) -> None:
    s = make(40, 10, {fid: skill for fid, skill in SKILLS.items() if fid != missing})
    b = board(s, "common")
    assert set(b.forecasters) == set(COMMON_GROUP)
    assert b.missing_forecasters == [missing]
    assert b.questions == 0 and b.rows == [] and b.label == TOO_EARLY


@pytest.mark.parametrize("skipping", COMMON_GROUP)
def test_skip_by_any_required_member_excludes_the_question(skipping: str) -> None:
    s = make(1, 3, SKILLS, skip={skipping: {1}})
    b = board(s, "common")
    assert b.missing_forecasters == []
    assert b.questions == 2 and all(r.n == 2 for r in b.rows)
