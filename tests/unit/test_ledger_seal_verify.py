import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from factories import B, forecast, question, resolution

from arena.clock import FixedClock
from arena.ledger import Ledger, LedgerError, layout
from arena.ledger.seal import seal_batch, seal_day, seal_pending_days
from arena.ledger.verify import verify
from arena.models import canonical_json, parse_record

B2 = B + timedelta(days=1)


def morning(led: Ledger, clock: FixedClock, batch) -> None:
    clock.set(datetime(batch.year, batch.month, batch.day, 6, tzinfo=UTC))
    qs = [question("A", batch), question("B", batch)]
    led.append(layout.questions_path(batch), qs)
    led.append(
        layout.forecasts_path(batch),
        [forecast(q, f, p) for q in qs for f, p in (("base_rate", 0.5), ("ml", 0.7))],
    )
    seal_batch(led, batch, clock)


@pytest.fixture
def led(tmp_path: Path) -> Ledger:
    led = Ledger(tmp_path)
    clock = FixedClock(datetime(2026, 11, 12, 6, tzinfo=UTC))
    morning(led, clock, B)
    clock.set(datetime(2026, 11, 12, 13, tzinfo=UTC))
    led.append(layout.resolutions_path(B), [resolution(question("A", B))])
    morning(led, clock, B2)  # 2026-11-13 06:00
    assert [s.day for s in seal_pending_days(led, clock)] == [B]
    clock.set(datetime(2026, 11, 14, 3, 30, tzinfo=UTC))
    assert [s.day for s in seal_pending_days(led, clock)] == [B2]
    return led


def test_untouched_ledger_passes(led: Ledger) -> None:
    rep = verify(led)
    assert rep.ok, rep.summary()
    assert rep.batch_seals == 2 and rep.day_seals == 2 and rep.forecasts == 8


def test_sealed_files_refuse_appends(led: Ledger) -> None:
    with pytest.raises(LedgerError, match="sealed"):
        led.append(layout.questions_path(B), [question("Z", B)])


def _rewrite(led: Ledger, rel: str, fn) -> None:
    path = led.abspath(rel)
    lines = path.read_text().splitlines(keepends=True)
    path.write_text("".join(fn(lines)))


def test_edit_detected(led: Ledger) -> None:
    def edit(lines):
        rec = parse_record(lines[0])
        return [canonical_json(rec.model_copy(update={"probability": 0.99})), *lines[1:]]

    _rewrite(led, layout.forecasts_path(B), edit)
    rep = verify(led)
    assert not rep.ok
    assert any("forecasts/2026/11/12.jsonl changed after the seal" in e for e in rep.errors)


def test_delete_line_detected(led: Ledger) -> None:
    _rewrite(led, layout.forecasts_path(B), lambda lines: lines[1:])
    assert any("changed after the seal" in e for e in verify(led).errors)


def test_delete_file_detected(led: Ledger) -> None:
    led.abspath(layout.resolutions_path(B)).unlink()
    assert any("resolutions/2026/11/12.jsonl is missing" in e for e in verify(led).errors)


def test_reorder_detected(led: Ledger) -> None:
    _rewrite(led, layout.questions_path(B2), lambda lines: list(reversed(lines)))
    assert any("changed after the seal" in e for e in verify(led).errors)


def test_added_file_after_seal_detected(led: Ledger) -> None:
    led.abspath("runs/2026/11/12-morning-9.json").parent.mkdir(parents=True, exist_ok=True)
    src = led.abspath(layout.batch_seal_path(B)).read_text()
    led.abspath("runs/2026/11/12-morning-9.json").write_text(src)
    assert any("added after the seal" in e for e in verify(led).errors)


def test_chain_tamper_detected(led: Ledger) -> None:
    rel = layout.day_seal_path(B)
    data = json.loads(led.abspath(rel).read_text())
    data["chain_sha256"] = "f" * 64
    led.abspath(rel).write_text(json.dumps(data, sort_keys=True, separators=(",", ":")) + "\n")
    errors = verify(led).errors
    assert any("chain_sha256 does not match" in e for e in errors)
    assert any("does not link" in e for e in errors)


def test_late_forecast_detected(tmp_path: Path) -> None:
    led = Ledger(tmp_path)
    q = question("A", B)
    led.append(layout.questions_path(B), [q])
    led.append(layout.forecasts_path(B), [forecast(q, early=-1)])  # one hour after lock
    rep = verify(led)
    assert any("is not before lock" in e for e in rep.errors), rep.summary()


def test_cannot_seal_unfinished_day_or_out_of_order(led: Ledger) -> None:
    clock = FixedClock(datetime(2026, 11, 14, 12, tzinfo=UTC))
    with pytest.raises(LedgerError, match="not over"):
        seal_day(led, B2 + timedelta(days=1), clock)
    with pytest.raises(LedgerError, match="already sealed"):
        led.abspath(layout.day_seal_path(B)).unlink()
        seal_day(led, B, clock)


def test_seal_is_idempotent(led: Ledger) -> None:
    clock = FixedClock(datetime(2026, 11, 20, tzinfo=UTC))
    before = led.read_bytes(layout.day_seal_path(B))
    seal_day(led, B, clock)
    seal_batch(led, B, clock)
    assert led.read_bytes(layout.day_seal_path(B)) == before
