"""T205: the site says honestly whether the players' intake works."""

from datetime import UTC, date, datetime

from arena.ledger import Ledger
from arena.models import RunManifest, canonical_json
from arena.site.ops_status import players_state

TODAY = date(2026, 11, 19)


def _run(led: Ledger, n: int, warnings: list[str], counts: dict[str, int] | None = None) -> None:
    start = datetime(2026, 11, 19, 17, n, tzinfo=UTC)
    m = RunManifest(
        run_id=f"2026-11-19-players-{n}",
        job="players",
        batch_date=TODAY,
        started_at=start,
        ended_at=start,
        status="ok",
        dry_run=False,
        code_sha="0" * 40,
        warnings=warnings,
        counts=counts or {},
    )
    led.write_raw(f"runs/2026/11/19-players-{n}.json", canonical_json(m).encode())


def test_never_ran(tmp_path) -> None:
    s = players_state(Ledger(tmp_path / "l"), TODAY)
    assert s.state == "never_ran" and "H15" in s.text and s.last_run is None


def test_not_configured_then_late_then_wrote(tmp_path) -> None:
    led = Ledger(tmp_path / "l")
    _run(led, 1, ["no players CSV configured (ARENA_PLAYERS_CSV_URL); nothing to do"])
    assert players_state(led, TODAY).state == "not_configured"
    _run(led, 2, ["late run: 2026-11-19T17:31 is at or after lock 2026-11-19T09:30"])
    late = players_state(led, TODAY)
    assert late.state == "late" and "H20" in late.text
    _run(led, 3, [], {"players": 2})
    assert players_state(led, TODAY).state == "wrote"
