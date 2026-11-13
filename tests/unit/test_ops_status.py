from datetime import UTC, date, datetime, timedelta

from factories import B, forecast, question

from arena.ledger import Ledger, layout
from arena.models import Evidence, Resolution, RunManifest, Skip, canonical_json
from arena.scoring.core import load
from arena.site.ops_status import llm_usage, missed_days, parse_failures, source_freshness


def _led(tmp_path) -> Ledger:
    led = Ledger(tmp_path)
    led.append(layout.questions_path(B), [question()])
    return led


def test_missed_days_counts_unsealed_days_before_today(tmp_path) -> None:
    led = _led(tmp_path)
    led.write_raw(layout.batch_seal_path(B), b"{}\n")
    assert missed_days(led, B) == []  # today is never "missed" yet
    assert missed_days(led, B + timedelta(days=3)) == [B + timedelta(days=1), B + timedelta(days=2)]
    assert missed_days(Ledger(tmp_path / "empty"), B) == []


def test_llm_usage_sums_manifests_per_day(tmp_path) -> None:
    led = _led(tmp_path)
    t = datetime.combine(B, datetime.min.time(), tzinfo=UTC) + timedelta(hours=5)
    for n, req in ((1, 2), (2, 3)):
        m = RunManifest(
            run_id=f"m{n}",
            job="morning",
            batch_date=B,
            started_at=t,
            ended_at=t,
            code_sha="0" * 40,
            status="ok",
            dry_run=False,
            llm_usage={"requests": req, "input_tokens": 100 * req, "output_tokens": 10 * req},
        )
        led.write_raw(f"runs/{B:%Y/%m/%d}-morning-{n}.json", canonical_json(m).encode())
    today = llm_usage(led, B, days=2)
    assert today[0].day == B and today[0].requests == 5 and today[0].total == 550
    assert today[1].requests == 0


def test_parse_failures_and_freshness(tmp_path) -> None:
    led = Ledger(tmp_path)
    q1, q2 = question(), question(template="max_gt")
    led.append(layout.questions_path(B), [q1, q2])
    skip = Skip(
        question_id=q2.question_id,
        forecaster_id="llm_plain",
        created_at=q2.created_at,
        reason_code="parse_failure",
        detail="bad JSON",
    )
    led.append(
        layout.forecasts_path(B),
        [forecast(q1, "llm_plain", 0.4), skip, forecast(q1, "base_rate", 0.5)],
    )
    rows = parse_failures(load(led))
    assert [(r.forecaster_id, r.forecasts, r.parse_failures) for r in rows] == [("llm_plain", 1, 1)]
    assert rows[0].failure_rate == 0.5
    res = Resolution(
        question_id=q1.question_id,
        outcome=1,
        observed_value=1.0,
        resolved_at=q1.resolve_after,
        evidence=Evidence(source_url="https://x", snapshot_sha256="a" * 64, values_used={}),
    )
    led.append(layout.resolutions_path(B), [res])
    late = q2.resolve_after + timedelta(days=2)
    (f,) = source_freshness(load(led), late)
    assert f.domain == q1.domain and f.last_batch == B and f.last_resolved_at == q1.resolve_after
    assert f.overdue == 1 and f.stale(late)
    assert not f.stale(datetime.combine(B, datetime.min.time(), tzinfo=UTC))
    assert isinstance(f.last_batch, date)
