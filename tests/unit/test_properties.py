"""Property-based tests (Hypothesis): invariants that must hold for any input, not just
the hand-picked examples of the other tests."""

import math
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from factories import B, forecast, question
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.ledger.seal import seal_batch
from arena.ledger.verify import verify
from arena.models import canonical_json, parse_record
from arena.scoring.core import CLIP_HIGH, CLIP_LOW, brier, clip, log_score

probs = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
outcomes = st.integers(min_value=0, max_value=1)
pairs = st.lists(st.tuples(probs, outcomes), min_size=1, max_size=60)


@given(p=probs, fid=st.from_regex(r"[a-z][a-z0-9_]{0,20}", fullmatch=True))
def test_canonical_json_round_trips_and_is_stable(p: float, fid: str) -> None:
    f = forecast(question(), fid, p)
    line = canonical_json(f)
    back = parse_record(line)
    assert back == f
    assert canonical_json(back) == line  # serialising twice changes nothing
    assert line.endswith("\n") and line.count("\n") == 1


@given(pairs)
def test_brier_and_log_score_bounds(data: list[tuple[float, int]]) -> None:
    ps, ys = [p for p, _ in data], [y for _, y in data]
    b = brier(ps, ys)
    assert (CLIP_LOW**2) - 1e-12 <= b <= (CLIP_HIGH**2) + 1e-12  # clipping bounds it
    assert 0.0 <= brier(ps, ys, clipped=False) <= 1.0
    ls = log_score(ps, ys)
    assert -math.log(CLIP_HIGH) - 1e-12 <= ls <= -math.log(CLIP_LOW) + 1e-12
    # A coin flip always scores 0.25, whatever happened.
    assert brier([0.5] * len(ys), ys) == 0.25


@given(pairs)
def test_perfect_hindsight_beats_any_forecast(data: list[tuple[float, int]]) -> None:
    ps, ys = [p for p, _ in data], [y for _, y in data]
    assert brier([float(y) for y in ys], ys) <= brier(ps, ys) + 1e-12


@given(probs)
def test_clip_is_monotone_and_bounded(p: float) -> None:
    c = clip(p)
    assert CLIP_LOW <= c <= CLIP_HIGH
    assert clip(min(1.0, p + 0.1)) >= c


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.data())
def test_any_single_byte_change_in_a_sealed_batch_is_detected(data: st.DataObject) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        led = Ledger(Path(tmp))
        q = question()
        led.append(layout.questions_path(B), [q])
        led.append(layout.forecasts_path(B), [forecast(q, "base_rate", 0.6)])
        seal_batch(led, B, FixedClock(datetime(2026, 11, 12, 5, 35, tzinfo=UTC)))
        assert verify(led).ok
        rel = data.draw(st.sampled_from([layout.questions_path(B), layout.forecasts_path(B)]))
        path = led.abspath(rel)
        raw = bytearray(path.read_bytes())
        i = data.draw(st.integers(min_value=0, max_value=len(raw) - 1))
        new = data.draw(st.integers(min_value=0, max_value=255).filter(lambda b: b != raw[i]))
        raw[i] = new
        path.write_bytes(bytes(raw))
        assert not verify(led).ok


@given(st.integers(min_value=0, max_value=200))
def test_forecasts_after_lock_never_verify(minutes_late: int) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        led = Ledger(Path(tmp))
        q = question()
        late = forecast(q).model_copy(
            update={"created_at": q.lock_time + timedelta(minutes=minutes_late, seconds=1)}
        )
        led.append(layout.questions_path(B), [q])
        led.append(layout.forecasts_path(B), [late])
        assert not verify(led).ok
