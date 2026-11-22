"""The Ask the Arena knowledge pack (T311): published data only, schema, size budget."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from factories import forecast, question

from arena.clock import FixedClock
from arena.ledger import Ledger, layout
from arena.site import chatpack
from arena.site.build import build_site

CLOCK = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))


def _pack(tmp: Path, ledger: Ledger) -> dict:
    res = build_site(ledger, tmp / "site", CLOCK, tmp / "none")
    return json.loads((res.out_dir / "chat" / "pack.json").read_text(encoding="utf-8"))


def test_empty_ledger_still_has_documents_and_a_disclaimer(tmp_path: Path) -> None:
    pack = _pack(tmp_path, Ledger(tmp_path / "l"))
    assert pack["version"] == chatpack.PACK_VERSION and pack["built"] == "2026-11-13"
    assert pack["questions"] == [] and pack["docs"]
    assert "no advice of any kind" in pack["disclaimer"]
    assert {d["path"].split("/")[0] for d in pack["docs"]} == {"docs"}
    assert (tmp_path / "site" / "chat" / "pack.json").stat().st_size < chatpack.MAX_BYTES


def test_questions_carry_locked_forecasts_and_outcomes(tmp_path: Path) -> None:
    led = Ledger(tmp_path / "l")
    q = question()
    led.append(layout.questions_path(q.batch_date), [q])
    led.append(
        layout.forecasts_path(q.batch_date),
        [forecast(q, "base_rate", 0.61), forecast(q, "ml", 0.2)],
    )
    pack = _pack(tmp_path, led)
    row = pack["questions"][0]
    assert row["id"] == q.question_id and row["state"] == "open" and row["outcome"] is None
    assert row["f"]["ml"] == [0.2, None] and row["f"]["base_rate"] == [0.61, None]
    assert pack["forecasters"]["ml"] == "ML model"
    # no rationale, trace or private field leaks into the pack
    assert set(row) == {
        "id", "domain", "template", "entity", "title", "text", "target", "batch", "lock",
        "threshold", "unit", "state", "outcome", "f",
    }  # fmt: skip


def test_pack_size_is_capped(tmp_path: Path) -> None:
    big = {"docs": [{"text": "x" * 2_000_000}]}
    with pytest.raises(ValueError, match="over the budget"):
        chatpack.write_pack(big, tmp_path)
