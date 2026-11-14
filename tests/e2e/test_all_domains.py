"""All four live domains through the real job code on recorded fixtures (T046).

Evening 2026-11-11 18:00 UTC publishes tomorrow's questions for power, weather, Wikipedia
attention and exchange rates; the morning run answers them with every forecaster before the
lock; the ledger verifies. Data: the recorded fixtures of each source (tests/fixtures).
"""

import gzip
import json
from datetime import UTC, date, datetime
from pathlib import Path

from power_fixtures import fixture_domain
from test_attention import FixtureSource
from weather_fixtures import fixture_weather

from arena.clock import FixedClock
from arena.config import Settings
from arena.domains.attention import AttentionDomain
from arena.domains.markets import markets_domain_from_rates
from arena.ledger import Ledger
from arena.ledger.verify import verify
from arena.llm.client import FakeLLM
from arena.models import Forecast, Question, Skip
from arena.ops.jobs import evening, morning
from arena.ops.wiring import build_forecasters
from arena.sources.ecb import parse_csv

ROOT = Path(__file__).resolve().parents[2]
BATCH = date(2026, 11, 12)
RATES = parse_csv(
    gzip.decompress(
        (ROOT / "tests" / "fixtures" / "ecb" / "exr_usd_jpy_2019-01-01.csv.gz").read_bytes()
    ).decode()
)
GOOD = json.dumps({"probability": 0.5, "rationale": "Fake.", "key_factors": []})


def domains(skips: list[str]):
    return [
        fixture_domain(skips),
        fixture_weather(skips, forecast_at=datetime(2026, 11, 11, 17, tzinfo=UTC)),
        AttentionDomain(FixtureSource(), on_skip=skips.append),
        markets_domain_from_rates(RATES, "fixture://ecb", "e" * 64, on_skip=skips.append),
    ]


def test_four_domains_evening_then_morning_then_verify(tmp_path) -> None:
    led = Ledger(tmp_path / "ledger")
    skips: list[str] = []
    doms = domains(skips)
    clock = FixedClock(datetime(2026, 11, 11, 18, tzinfo=UTC))
    r = evening(led, BATCH, clock, doms)
    qs = [
        q for q in led.read(f"questions/2026/11/{BATCH.day:02d}.jsonl") if isinstance(q, Question)
    ]
    assert not r.warnings and r.written["questions"] == len(qs) >= 25
    by_domain = {
        d: [q for q in qs if q.domain == d] for d in ("power", "weather", "attention", "markets")
    }
    assert all(by_domain.values()), {d: len(v) for d, v in by_domain.items()}
    assert {q.template_version for q in qs} == {2}
    assert {q.lock_time for q in qs} == {datetime(2026, 11, 12, 9, 30, tzinfo=UTC)}
    assert len({q.question_id for q in qs}) == len(qs)

    clock.set(datetime(2026, 11, 12, 5, 30, tzinfo=UTC))
    settings = Settings.from_env({"ARENA_LLM_QUESTIONS_PER_DOMAIN": "2"})
    fcs, _ = build_forecasters(
        led, doms, settings, BATCH, llm=FakeLLM(lambda s, t, tl: GOOD), clock=clock
    )
    m = morning(led, BATCH, clock, doms, fcs)
    assert "questions" not in m.written  # the evening already published every domain
    recs = [x for _, x in led.iter_family("forecasts")]
    forecasts = [x for x in recs if isinstance(x, Forecast)]
    base = {f.question_id for f in forecasts if f.forecaster_id == "base_rate"}
    assert base == {q.question_id for q in qs}  # the base rate answers every question
    sampled = {f.question_id for f in forecasts if f.forecaster_id == "llm_plain"}
    assert {q.domain for q in qs if q.question_id in sampled} == set(by_domain)  # per domain
    reasons = {x.reason_code for x in recs if isinstance(x, Skip)}
    assert reasons <= {"not_sampled", "model_missing"}, reasons
    rep = verify(led)
    assert rep.ok, rep.summary()
