"""Offline end-to-end run: five simulated days through the real job code (SPEC 13).

Data: recorded SMARD fixtures. Time: a fixed clock moved through the daily schedule of
SPEC 4 (two morning runs, four resolve runs). Ends with ledger verification. A second
schedule adds the evening job (T160): questions published at 18:00 UTC the day before.
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
from arena.ops.jobs import evening, morning, resolve
from arena.ops.wiring import build_forecasters

FIRST = date(2026, 10, 21)
SETTINGS = Settings.from_env({"ARENA_LLM_QUESTIONS_PER_DOMAIN": "3"})
GOOD = json.dumps({"probability": 0.5, "rationale": "Fake.", "key_factors": []})


def answer(system, turns, tools):
    return GOOD


DAYS = 5
MORNINGS = (time(5, 30), time(7, 0))
RESOLVES = (time(3, 30), time(12, 30), time(16, 30), time(20, 30))
EVENINGS = (time(18, 0), time(19, 30))


def run_schedule(root, with_evening: bool = False) -> Ledger:
    led = Ledger(root)
    clock = FixedClock(datetime.combine(FIRST, time(0), tzinfo=UTC))
    domains = [fixture_domain()]
    forecasters, guard = build_forecasters(
        led, domains, SETTINGS, FIRST, llm=FakeLLM(answer), clock=clock
    )

    def attach(rec) -> None:  # as the CLI does: usage goes into the run manifest
        if guard is not None:
            guard.recorder = rec

    for i in range(DAYS + 1):
        day = FIRST + timedelta(days=i)
        events = [(t, "resolve") for t in RESOLVES]
        if i < DAYS:
            events += [(t, "morning") for t in MORNINGS]
        if with_evening and i < DAYS - 1:
            events += [(t, "evening") for t in EVENINGS]
        for t, job in sorted(events):
            clock.set(datetime.combine(day, t, tzinfo=UTC))
            if job == "morning":
                morning(led, day, clock, domains, forecasters, on_record=attach)
            elif job == "evening":
                evening(led, day + timedelta(days=1), clock, domains)
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
    traces = [
        json.loads(x)
        for rel in led.list_files("agent_traces")
        for x in led.read_bytes(rel).decode().splitlines()
    ]
    spans = [s for t in traces for s in t.get("spans", [])]
    assert {t["forecaster_id"] for t in traces} == {"llm_plain", "llm_context", "agent"}
    assert spans and all(s["model"] and s["question_id"] and s["duration_ms"] >= 0 for s in spans)
    llm_page = (site.out_dir / "llm.html").read_text()
    assert "Calls per day" in llm_page and "fake-model-1" in llm_page
    traced = spans[0]["question_id"]
    qpage = (site.out_dir / "questions" / f"{traced}.html").read_text()
    assert "How the AI forecasters worked" in qpage
    assert "The data at forecast time" in qpage and 'class="qchart"' in qpage
    assert 'rel="next"' in qpage or 'rel="prev"' in qpage
    status = (site.out_dir / "status.html").read_text()
    for panel in ("Missed days", "Source freshness", "LLM usage", "LLM parse failures"):
        assert panel in status, panel
    from arena.site.ops_status import llm_usage, parse_failures, source_freshness

    assert sum(u.requests for u in llm_usage(led, FIRST + timedelta(days=DAYS), DAYS + 1)) > 0
    assert {p.forecaster_id for p in parse_failures(rec)} == {"llm_plain", "llm_context", "agent"}
    now = datetime(2026, 10, 27, tzinfo=UTC)
    assert [f.domain for f in source_freshness(rec, now)] == ["power"]


def test_evening_publication(tmp_path) -> None:
    """T160: questions appear the evening before; forecasts still in the morning; same lock."""
    led = run_schedule(tmp_path / "ledger", with_evening=True)
    qs = [r for _, r in led.iter_family("questions") if isinstance(r, Question)]
    fs = [r for _, r in led.iter_family("forecasts") if isinstance(r, Forecast)]
    assert len({q.batch_date for q in qs}) == DAYS
    for q in qs:
        assert q.lock_time == datetime.combine(q.batch_date, time(9, 30), tzinfo=UTC)
        if q.batch_date == FIRST:  # no evening run before the first day: morning, version 1
            assert q.template_version == 1 and q.created_at.date() == FIRST
        else:
            assert q.template_version == 2 and q.question_id.endswith("-v2")
            assert q.created_at == datetime.combine(
                q.batch_date - timedelta(days=1), time(18, 0), tzinfo=UTC
            )
    by_id = {q.question_id: q for q in qs}
    for f in fs:
        q = by_id[f.question_id]
        assert q.created_at <= f.created_at < q.lock_time  # forecasts after publication
        assert f.created_at.date() == q.batch_date and f.created_at.time() < time(9, 30)
    assert len([f for f in fs if f.forecaster_id == "base_rate"]) == len(qs)
    morning_v2 = [q for q in qs if q.template_version == 2]
    assert morning_v2 and len(morning_v2) == len(qs) - sum(q.batch_date == FIRST for q in qs)
    rep = verify(led)
    assert rep.ok, rep.summary()
    from arena.scoring.core import counts, load

    assert counts(load(led)).open == 0
    next_batch = FIRST + timedelta(days=DAYS + 1)  # tomorrow's questions, published tonight
    clock = FixedClock(datetime.combine(next_batch - timedelta(days=1), time(21), tzinfo=UTC))
    assert evening(led, next_batch, clock, [fixture_domain()]).written["questions"] > 0
    from arena.site.build import build_site
    from arena.site.linkcheck import check_site

    site = build_site(led, tmp_path / "site", clock)
    assert check_site(site.out_dir) == []
    methods = (site.out_dir / "methods.html").read_text()
    assert "Question template versions" in methods and "evening before the batch day" in methods
    new = next(q for q in load(led).questions.values() if q.batch_date == next_batch)
    page = (site.out_dir / "questions" / f"{new.question_id}.html").read_text()
    assert "Forecasts lock at" in page and "No forecasts yet" in page


def test_rerunning_the_schedule_changes_nothing(tmp_path) -> None:
    a = run_schedule(tmp_path / "a", with_evening=True)
    b = run_schedule(tmp_path / "b", with_evening=True)
    files = [f for f in a.list_files() if not f.startswith("runs/")]
    assert files == [f for f in b.list_files() if not f.startswith("runs/")]
    for f in files:
        if not f.startswith("chain/"):  # seals embed sealed_at, also deterministic here
            assert a.read_bytes(f) == b.read_bytes(f), f
