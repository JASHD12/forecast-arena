from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.ledger.manifest import manifests_for_day, run_manifest
from arena.ledger.verify import verify

D = date(2026, 11, 12)


def test_manifest_written_on_success(tmp_path: Path) -> None:
    led = Ledger(tmp_path)
    clock = FixedClock(datetime(2026, 11, 12, 5, 30, tzinfo=UTC))
    with run_manifest(led, "morning", D, clock) as rec:
        rec.count("questions", 3)
        rec.warn("source late")
        rec.add_llm_usage(requests=2, input_tokens=100)
        rec.add_llm_usage(requests=1)
        clock.advance(timedelta(minutes=4))
    (m,) = manifests_for_day(led, D)
    assert m.status == "ok" and m.error is None
    assert m.counts == {"questions": 3}
    assert m.llm_usage == {"requests": 3, "input_tokens": 100}
    assert m.ended_at - m.started_at == timedelta(minutes=4)
    assert m.package_versions["pydantic"]
    assert led.exists("runs/2026/11/12-morning-1.json")
    assert verify(led).ok


def test_manifest_written_on_failure_and_numbered(tmp_path: Path) -> None:
    led = Ledger(tmp_path)
    clock = FixedClock(datetime(2026, 11, 12, 7, tzinfo=UTC))
    with run_manifest(led, "morning", D, clock):
        pass
    with pytest.raises(RuntimeError), run_manifest(led, "morning", D, clock):
        raise RuntimeError("source down")
    runs = {m.run_id: m for m in manifests_for_day(led, D)}
    assert set(runs) == {"2026-11-12-morning-1", "2026-11-12-morning-2"}
    failed = runs["2026-11-12-morning-2"]
    assert failed.status == "failed" and failed.error == "RuntimeError: source down"
