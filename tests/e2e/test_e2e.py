"""Offline end-to-end run: five simulated days through the real job code (SPEC 13).

Data: recorded SMARD fixtures. Time: a fixed clock moved through the daily schedule of
SPEC 4 (two morning runs, four resolve runs). Ends with ledger verification.
"""

import json
from datetime import UTC, date, datetime, time, timedelta

from power_fixtures import fixture_domain

from arena.clock import FixedClock
from arena.config import Settings
from arena.ledger import Ledger, layout
from arena.ledger.verify import verify
from arena.llm.client import FakeLLM
from arena.models import Forecast, Question, Resolution, Skip
from arena.ops.jobs import morning, resolve
from arena.ops.wiring import build_forecasters

FIRST = date(2026, 10, 21)
SETTINGS = Settings.from_env({"ARENA_LLM_QUESTIONS_PER_DOMAIN": "3"})
GOOD = json.dumps({"probability": 0.5, "rationale": "Fake.", "key_factors": []})


def answer(system, turns, tools):
    return GOOD


DAYS = 5
MORNINGS = (time(5, 30), time(7, 0))
RESOLVES = (time(3, 30), time(12, 30), time(16, 30), time(20, 30))


def run_schedule(root) -> Ledger:
    led = Ledger(root)
    clock = FixedClock(datetime.combine(FIRST, time(0), tzinfo=UTC))
    domains = [fixture_domain()]
    forecasters, guard = build_forecasters(led, domains, SETTINGS, FIRST, llm=FakeLLM(answer))

    def attach(rec) -> None:  # as the CLI does: usage goes into the run manifest
        if guard is not None:
            guard.recorder = rec

    for i in range(DAYS + 1):
        day = FIRST + timedelta(days=i)
        events = [(t, "resolve") for t in RESOLVES]
        if i < DAYS:
            events += [(t, "morning") for t in MORNINGS]
        for t, job in sorted(events):
            clock.set(datetime.combine(day, t, tzinfo=UTC))
            if job == "morning":
                morning(led, day, clock, domains, forecasters, on_record=attach)
            else:
                resolve(led, clock, domains)
    return led


def test_five_days_offline(tmp_path) -> None:
    led = run_schedule(tmp_path / "ledger")
    qs = [r for _, r in led.iter_family("questions") if isinstance(r, Question)]
    fs = [r for _, r in led.iter_family("forecasts") if isinstance(r, Forecast)]
    rs = [r for _, r in led.iter_family("resolutions") if isinstance(r, Resolution)]
    assert len({q.batch_date for q in qs}) == DAYS
    assert len(qs) >= 5 * DAYS
    base = [f for f in fs if f.forecaster_id in ("base_rate", "persistence")]
    assert len(base) == 2 * len(qs)  # base_rate and persistence answer everything
    llm = {
        fid: {f.question_id for f in fs if f.forecaster_id == fid}
        for fid in ("llm_plain", "llm_context", "agent")
    }
    assert llm["llm_plain"] == llm["llm_context"] == llm["agent"]  # paired daily sample
    assert led.exists(layout.agent_traces_path(FIRST))
    assert len(llm["llm_plain"]) == 3 * DAYS
    skips = [r for _, r in led.iter_family("forecasts") if isinstance(r, Skip)]
    assert {s.reason_code for s in skips} == {"not_sampled"}
    assert {r.question_id for r in rs} == {q.question_id for q in qs}
    for d in range(DAYS):
        assert led.exists(layout.batch_seal_path(FIRST + timedelta(days=d)))
        assert led.exists(layout.day_seal_path(FIRST + timedelta(days=d)))
    assert any(r.evidence.values_used["hours"] == 25 for r in rs)  # 25 Oct 2026
    rep = verify(led)
    assert rep.ok, rep.summary()
    from arena.scoring.core import counts, leaderboard, load

    rec = load(led)
    board = {r.forecaster_id: r for r in leaderboard(rec.scored)}
    assert set(board) == {"base_rate", "persistence", "llm_plain", "llm_context", "agent"}
    assert board["base_rate"].n == len(qs) and board["base_rate"].skill == 0
    assert counts(rec).open == 0

    from arena.site.build import build_site
    from arena.site.linkcheck import check_site

    site = build_site(led, tmp_path / "site", FixedClock(datetime(2026, 10, 27, tzinfo=UTC)))
    assert check_site(site.out_dir) == []
    home = (site.out_dir / "index.html").read_text()
    assert "base_rate" in home and "not advice" in home and "SMARD.de" in home
    status = (site.out_dir / "status.html").read_text()
    for panel in ("Missed days", "Source freshness", "LLM usage", "LLM parse failures"):
        assert panel in status, panel
    from arena.site.ops_status import llm_usage, parse_failures, source_freshness

    assert sum(u.requests for u in llm_usage(led, FIRST + timedelta(days=DAYS), DAYS + 1)) > 0
    assert {p.forecaster_id for p in parse_failures(rec)} == {"llm_plain", "llm_context", "agent"}
    now = datetime(2026, 10, 27, tzinfo=UTC)
    assert [f.domain for f in source_freshness(rec, now)] == ["power"]


def test_rerunning_the_schedule_changes_nothing(tmp_path) -> None:
    a = run_schedule(tmp_path / "a")
    b = run_schedule(tmp_path / "b")
    files = [f for f in a.list_files() if not f.startswith("runs/")]
    assert files == [f for f in b.list_files() if not f.startswith("runs/")]
    for f in files:
        if not f.startswith("chain/"):  # seals embed sealed_at, also deterministic here
            assert a.read_bytes(f) == b.read_bytes(f), f
