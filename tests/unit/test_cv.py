import json
import random
from datetime import date, timedelta

from factories import question

from arena.ledger import Ledger, layout
from arena.models import Evidence, Forecast, Resolution
from arena.scoring.cv import cv_lines


def fill(led: Ledger, days: int, per_day: int, ml_skill: float, start: date) -> None:
    rng = random.Random(1)
    for d in range(days):
        b = start + timedelta(days=d)
        qs = [question(entity=f"E{i}", batch=b) for i in range(per_day)]
        led.append(layout.questions_path(b), qs)
        fs, rs = [], []
        for q in qs:
            y = int(rng.random() < 0.5)
            for fid, sk in (("base_rate", 0.0), ("ml", ml_skill)):
                fs.append(
                    Forecast(
                        forecast_id=f"{q.question_id}::{fid}",
                        question_id=q.question_id,
                        forecaster_id=fid,
                        forecaster_version="1",
                        probability=0.5 + (sk if y else -sk),
                        created_at=q.lock_time - timedelta(hours=1),
                    )
                )
            rs.append(
                Resolution(
                    question_id=q.question_id,
                    outcome=y,
                    observed_value=1.0,
                    resolved_at=q.resolve_after,
                    evidence=Evidence(source_url="x", snapshot_sha256="0" * 64),
                )
            )
        led.append(layout.forecasts_path(b), fs)
        led.append(layout.resolutions_path(b + timedelta(days=1)), rs)
    led.write_raw(
        layout.OFFICIAL_START_PATH, json.dumps({"official_start": start.isoformat()}).encode()
    )


def test_refuses_to_call_a_too_early_comparison_a_win(tmp_path) -> None:
    led = Ledger(tmp_path)
    fill(led, days=10, per_day=5, ml_skill=0.4, start=date(2026, 1, 1))  # huge but early
    text = "\n".join(cv_lines(led))
    assert "too early to tell" in text and "beat" not in text.replace("beating", "")


def test_win_only_when_supported(tmp_path) -> None:
    led = Ledger(tmp_path)
    fill(led, days=35, per_day=10, ml_skill=0.3, start=date(2026, 1, 1))
    text = "\n".join(cv_lines(led))
    assert "ml beat base_rate" in text and "Official record: since 2026-01-01" in text


def test_no_win_without_interval_excluding_zero(tmp_path) -> None:
    led = Ledger(tmp_path)
    fill(led, days=35, per_day=10, ml_skill=0.0, start=date(2026, 1, 1))
    text = "\n".join(cv_lines(led))
    assert "beat base_rate" not in text and "no supported difference" in text
