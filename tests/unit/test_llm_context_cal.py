"""`llm_context_cal` (T382): the map, the power-only rule, skips, wiring and the committed fit."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
from crypto_fixtures import fixture_crypto

from arena.config import Settings
from arena.forecasters import llm_context_cal as C
from arena.models import Forecast, Question, Skip
from arena.ops.health import expected_forecasters

ROOT = Path(__file__).parents[2]
ASOF = datetime(2026, 11, 10, 5, 30, tzinfo=UTC)


def _q(domain: str) -> Question:
    q = fixture_crypto().generate_questions(
        date(2026, 11, 10), datetime.combine(date(2026, 11, 10), time(5, 30), tzinfo=UTC)
    )[0]
    return q.model_copy(update={"domain": domain})


def test_extremizing_map_moves_probabilities_away_from_one_half() -> None:
    cal = C.CalMap(1.5, 0.0, 1000, "l", "t")
    assert cal.apply(0.5) == pytest.approx(0.5)
    assert cal.apply(0.7) > 0.7 and cal.apply(0.3) < 0.3
    assert 0.01 <= cal.apply(0.999) <= 0.99 and 0.01 <= cal.apply(0.0001) <= 0.99


def test_version_changes_with_the_map() -> None:
    a = C.CalMap(1.5, 0.2, 10, "l", "t").version
    assert a.startswith("cal-platt-r1|") and a != C.CalMap(1.6, 0.2, 10, "l", "t").version


def test_power_is_calibrated_other_topics_pass_through_and_missing_raw_is_a_skip() -> None:
    f = C.LLMContextCal(C.CalMap(2.0, 0.0, 1000, "l", "t"))
    assert f.needs_peers and f.forecaster_id == "llm_context_cal"
    ctx = {"peer_forecasts": {"llm_context": 0.7}}
    out = f.forecast(_q("power"), ctx, ASOF)
    assert isinstance(out, Forecast) and out.probability > 0.7 and out.meta["calibrated"] is True
    other = f.forecast(_q("weather"), ctx, ASOF)
    assert (
        isinstance(other, Forecast)
        and other.probability == 0.7
        and other.meta["calibrated"] is False
    )
    skip = f.forecast(_q("power"), {"peer_forecasts": {"ml": 0.5}}, ASOF)
    assert isinstance(skip, Skip) and skip.reason_code == "not_sampled"


def test_fit_needs_enough_answers_and_recovers_an_extremizing_slope() -> None:
    import random

    rng = random.Random(0)
    p, y = [], []
    for _ in range(3000):  # truth is more extreme than the answers: true slope 2
        raw = rng.uniform(0.2, 0.8)
        p.append(raw)
        y.append(int(rng.random() < C.sigmoid(2.0 * C.logit(raw))))
    cal = C.fit_map(p, y)
    assert 1.6 < cal.a < 2.4 and abs(cal.b) < 0.3
    with pytest.raises(ValueError):
        C.fit_map(p[:50], y[:50])


def test_flag_is_off_and_the_roster_follows_it() -> None:
    assert Settings.from_env({}).llm_context_cal is False
    assert "llm_context_cal" not in expected_forecasters(Settings.from_env({}))
    assert "llm_context_cal" in expected_forecasters(
        Settings.from_env({"ARENA_LLM_CONTEXT_CAL": "1"})
    )


def test_the_committed_map_is_the_preregistered_fit_on_the_training_answers() -> None:
    doc = json.loads((ROOT / C.ARTEFACT).read_text("utf-8"))
    labels = json.loads((ROOT / "lab/data/distill-labels-v1.json").read_text("utf-8"))
    out = {}
    with gzip.open(ROOT / "lab/data/forecast-sft/train.jsonl.gz", "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            out[r["id"]] = int(r["outcome"])
    pairs = [(p, out[i]) for i, p in zip(labels["ids"], labels["p"], strict=True) if p is not None]
    cal = C.fit_map([p for p, _ in pairs], [y for _, y in pairs])
    assert doc["n_train"] == len(pairs) == 1198
    assert doc["a"] == pytest.approx(cal.a, abs=1e-5) and doc["b"] == pytest.approx(cal.b, abs=1e-5)
    loaded = C.load_map(ROOT / C.ARTEFACT)
    assert loaded is not None and loaded.version == doc["version"]
    assert C.load_map(ROOT / "no-such-file.json") is None
