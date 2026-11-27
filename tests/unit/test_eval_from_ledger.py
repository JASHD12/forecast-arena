"""Frozen golden sets from live ledger days (T380): scope, labelling, what is left out."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, date, datetime, time
from pathlib import Path

from click.testing import CliRunner
from crypto_fixtures import fixture_crypto

from arena.cli import main
from arena.evals import from_ledger as fl
from arena.evals.golden import load
from arena.ledger import Ledger, layout
from arena.models import Forecast, Resolution

B = date(2026, 11, 3)
ASOF = datetime.combine(B, time(5, 30), tzinfo=UTC)
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)


def _ledger(
    tmp_path: Path, *, snapshot_for: int | None = None, resolve: int | None = None
) -> tuple[Ledger, list]:
    dom = fixture_crypto()
    qs = dom.generate_questions(B, ASOF)
    led = Ledger(tmp_path / "ledger")
    led.append(layout.questions_path(B), qs)
    led.append(
        layout.forecasts_path(B),
        [
            Forecast(
                forecast_id=f"{q.question_id}::base_rate",
                question_id=q.question_id,
                forecaster_id="base_rate",
                forecaster_version="1",
                probability=0.4,
                created_at=ASOF,
            )
            for q in qs
        ],
    )
    done = qs if resolve is None else qs[:resolve]
    res = [r for q in done if isinstance(r := dom.resolve(q, NOW), Resolution)]
    led.append(layout.resolutions_path(NOW.date()), res)
    snap = {
        q.question_id: dom.context(q, ASOF)
        for q in (qs if snapshot_for is None else qs[:snapshot_for])
    }
    rel = f"{layout.snapshot_dir('crypto', B)}/morning_context.json.gz"
    led.write_raw(
        rel, gzip.compress(json.dumps(snap, sort_keys=True, default=str).encode(), mtime=0)
    )
    return led, qs


def test_items_carry_context_outcome_and_base_rate(tmp_path: Path) -> None:
    led, qs = _ledger(tmp_path)
    b = fl.build_from_ledger(led, ["crypto"], B)
    assert len(b.items) == len(qs) and b.dropped == {}
    it = b.items[0]
    assert it.base_rate == 0.4 and it.outcome in (0, 1) and it.asof == ASOF
    assert "daily_usd_00utc" in it.context


def test_other_topics_and_later_days_are_not_included(tmp_path: Path) -> None:
    led, _ = _ledger(tmp_path)
    assert fl.build_from_ledger(led, ["weather"], B).items == []
    assert fl.build_from_ledger(led, ["crypto"], date(2026, 11, 2)).items == []


def test_unresolved_and_snapshotless_questions_are_dropped_and_counted(tmp_path: Path) -> None:
    led, qs = _ledger(tmp_path, snapshot_for=6, resolve=8)
    b = fl.build_from_ledger(led, ["crypto"], B)
    assert len(b.items) == 6
    assert b.dropped == {"no morning snapshot": 2, "no resolution (open or void)": len(qs) - 8}


def test_cli_freezes_a_hashed_file_with_a_label(tmp_path: Path) -> None:
    led, qs = _ledger(tmp_path)
    out = tmp_path / "golden.jsonl"
    res = CliRunner().invoke(
        main,
        [
            "--ledger-dir",
            str(led.root),
            "eval",
            "build",
            "--from-ledger",
            "--topics",
            "crypto",
            "--until",
            "2026-11-03",
            "--out",
            str(out),
        ],
    )
    assert res.exit_code == 0, res.output
    assert "replay of live days" in res.output
    items, sha = load(out)
    meta = json.loads(out.with_suffix(".meta.json").read_text())
    assert meta["sha256"] == sha and meta["label"] == fl.LABEL and meta["items"] == len(items)
    assert (
        meta["items_per_topic"] == {"crypto": len(qs)} and meta["until_batch_day"] == "2026-11-03"
    )


def test_cli_refuses_to_freeze_nothing_and_needs_until(tmp_path: Path) -> None:
    led, _ = _ledger(tmp_path)
    base = [
        "--ledger-dir",
        str(led.root),
        "eval",
        "build",
        "--from-ledger",
        "--out",
        str(tmp_path / "g.jsonl"),
    ]
    assert CliRunner().invoke(main, base).exit_code != 0
    res = CliRunner().invoke(main, [*base, "--topics", "weather", "--until", "2026-11-03"])
    assert res.exit_code != 0 and "nothing frozen" in res.output


def test_committed_replay_set_matches_its_sidecar() -> None:
    golden = Path(__file__).parents[2] / "evals" / "golden"
    for meta_path in golden.glob("replay-*.meta.json"):
        meta = json.loads(meta_path.read_text())
        _, sha = load(golden / meta["file"])
        assert sha == meta["sha256"] and meta["label"] == fl.LABEL
        assert meta["items"] == sum(meta["items_per_topic"].values()) > 0
