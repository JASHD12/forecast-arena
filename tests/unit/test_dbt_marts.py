"""dbt marts (T152): the mart SQL the Data page runs agrees with the scoring code."""

from datetime import timedelta
from pathlib import Path

import pytest
from factories import B, forecast, question

from arena.analytics.sql import connect, run_dbt_marts
from arena.ledger import Ledger, layout
from arena.models import Evidence, Resolution
from arena.scoring.core import load

MARTS = Path(__file__).resolve().parents[2] / "analytics" / "dbt" / "models" / "marts"


def test_marts_match_the_scoring_code(tmp_path) -> None:
    led = Ledger(tmp_path)
    ev = Evidence(source_url="https://x", snapshot_sha256="a" * 64, values_used={})
    for i in range(2):
        d = B + timedelta(days=i)
        qs = [question(batch=d), question(batch=d, template="max_gt")]
        led.append(layout.questions_path(d), qs)
        fs = [forecast(q, "base_rate", 0.5) for q in qs]
        fs += [forecast(q, "ml", 0.995 if k else 0.2) for k, q in enumerate(qs)]
        led.append(layout.forecasts_path(d), fs)
        rs = [
            Resolution(
                question_id=q.question_id,
                outcome=k,
                observed_value=1.0,
                resolved_at=q.resolve_after,
                evidence=ev,
            )
            for k, q in enumerate(qs)
        ]
        led.append(layout.resolutions_path(d), rs)
    rec = load(led)
    marts = {m["name"]: m for m in run_dbt_marts(connect(rec), MARTS)}
    assert set(marts) == {"mart_daily_scores", "mart_forecaster_topic"}
    topic = {(r[0], r[1]): r for r in marts["mart_forecaster_topic"]["rows"]}
    for fid in ("base_rate", "ml"):
        ss = [s for s in rec.scored if s.forecaster_id == fid]
        expected = sum((min(max(s.probability, 0.01), 0.99) - s.outcome) ** 2 for s in ss) / len(ss)
        assert topic[(fid, "power")][3] == pytest.approx(expected)  # clipping matches SPEC 10
        assert topic[(fid, "power")][2] == len(ss)
    assert len(marts["mart_daily_scores"]["rows"]) == 4  # 2 days x 2 forecasters
    assert run_dbt_marts(connect(rec), None) == []


def test_every_ref_in_the_marts_resolves() -> None:
    import re

    models = {p.stem for p in (MARTS.parent).rglob("*.sql")}
    for f in MARTS.glob("*.sql"):
        for ref in re.findall(r"ref\('([a-z_]+)'\)", f.read_text()):
            assert ref in models, (f.name, ref)
