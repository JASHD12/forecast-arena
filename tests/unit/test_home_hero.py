"""T186: the home hero's BACKTEST card and the recruiter page are generated, not typed."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from arena.clock import FixedClock
from arena.ledger import Ledger
from arena.site.build import build_site, json_validity_change
from arena.site.cards_page import headline_backtest

ROOT = Path(__file__).resolve().parents[2]
MODELS, EVALS = ROOT / "docs" / "models", ROOT / "evals" / "results"


def _site(tmp_path):
    clock = FixedClock(datetime(2026, 11, 13, tzinfo=UTC))
    return build_site(
        Ledger(tmp_path / "l"),
        tmp_path / "site",
        clock,
        ROOT / "site_content",
        models_dir=MODELS,
        evals_dir=EVALS,
    ).out_dir


def test_backtest_card_matches_the_model_card(tmp_path) -> None:
    card = (MODELS / "power.md").read_text()
    bt = headline_backtest(MODELS)
    assert bt is not None and bt["days"] == 365 and bt["supported"]
    for fid, v, _ in bt["rows"]:
        assert re.search(rf"^\| {fid} \| \d+ \| {re.escape(v)} \|", card, re.M), fid
    assert f"| ml - base_rate | {bt['diff']} | {bt['interval']} |" in card
    home = (_site(tmp_path) / "index.html").read_text()
    assert ">backtest</span>" in home and bt["diff"] in home and "Not the live record" in home
    assert "joining soon" not in home
    assert headline_backtest(tmp_path / "missing") is None


def test_recruiter_page_is_honest_and_computed(tmp_path) -> None:
    page = (_site(tmp_path) / "recruiters.html").read_text()
    assert "by one person" not in page and "AI coding agent" in page
    assert "Five things worth 30 seconds" in page and 'href="guide.html#verify"' in page
    runs = [json.loads(p.read_text()) for p in EVALS.glob("eval-*.json")]
    ch = json_validity_change(runs)
    assert ch is not None and f"from {ch['before']} to {ch['after']}" in page
    assert json_validity_change(runs[:1]) is None


def test_experiments_shows_labelled_challenger_backtests_until_a_weekly_run(tmp_path) -> None:
    from arena.site.cards_page import challenger_backtests

    rows = challenger_backtests(MODELS)
    assert {r["challenger"] for r in rows} >= {"ml_lgbm", "ml_mlp", "ts_chronos"}
    lgbm = next(r for r in rows if r["challenger"] == "ml_lgbm")
    assert lgbm["supported"] and lgbm["better"]
    assert (
        f"| ml_lgbm - ml | {lgbm['diff']} | {lgbm['interval']} |"
        in (MODELS / "power-lgbm.md").read_text()
    )
    page = (_site(tmp_path) / "experiments.html").read_text()
    assert "Challengers against the champion" in page and "not the live record" in page
    assert lgbm["diff"] in page and "better than the champion" in page
    assert challenger_backtests(None) == []


def test_agent_card_only_from_real_successful_traces() -> None:
    from datetime import date
    from types import SimpleNamespace

    from arena.site.shaping import agent_trace_of_day

    q = SimpleNamespace(batch_date=date(2026, 11, 1))
    rec = SimpleNamespace(questions={"q1": q}, forecasts=[], resolutions={})
    ok = {
        "forecaster_id": "agent",
        "outcome": "forecast",
        "tool_calls": [{"tool": "get_series"}, {"tool": "get_base_rate"}],
    }
    bad = {"forecaster_id": "agent", "outcome": "error", "tool_calls": []}
    card = agent_trace_of_day({"q1": [ok]}, rec, date(2026, 11, 2))
    assert card and card["tools"] == ["get_series", "get_base_rate"] and card["probability"] is None
    assert agent_trace_of_day({"q1": [bad]}, rec, date(2026, 11, 2)) is None
    assert agent_trace_of_day({"q1": [ok]}, rec, date(2026, 10, 31)) is None  # not after batch
    assert agent_trace_of_day({}, rec, None) is None


def test_home_standings_state_questions_and_days() -> None:
    """T201: the standings card says how many questions and days stand behind the ranks."""
    from types import SimpleNamespace as NS

    from arena.site.build import _env

    src = (ROOT / "src" / "arena" / "site" / "templates" / "index.html").read_text()
    m = re.search(r"(<p class=\"st-note\">.*?</p>)", src, re.S)
    assert m
    tpl = _env().from_string(m.group(1))
    one = tpl.render(board=NS(questions=24, days=3, label="too early to tell"))
    assert "24 questions · 3 days" in one and "too early to tell" in one
    assert "1 day<" in tpl.render(board=NS(questions=8, days=1, label=None))


def test_no_unfinished_placeholder_text_on_any_page(tmp_path) -> None:
    """T202: no draft marker or 'owner confirmation' sentence reaches a built page."""
    out = _site(tmp_path)
    pages = list(out.rglob("*.html"))
    assert pages
    for page in pages:
        text = page.read_text()
        assert "owner confirmation" not in text, page.name
        assert "[FILL IN" not in text, page.name


def _row(qid: str, domain: str, pn: dict[str, float], outcome=None, state: str = "open") -> dict:
    return {"qid": qid, "domain": domain, "pn": pn, "outcome": outcome, "state": state}


def test_home_cards_prefer_answered_questions_and_spread_over_topics() -> None:
    """Home page diet: six full cards, the best-answered first, one topic does not take them all."""
    from arena.site.shaping import pick_cards, split_outcomes

    rows = [_row(f"w{i}", "weather", {"a": 0.5}) for i in range(8)]
    rows += [_row("p1", "power", {"a": 0.2, "b": 0.8, "c": 0.5}), _row("p2", "power", {"a": 0.5})]
    rows += [_row("m1", "markets", {"a": 0.4, "b": 0.45})]
    picked = pick_cards(rows, 4)
    assert [r["qid"] for r in picked][:1] == ["p1"] and len(picked) == 4
    assert {r["domain"] for r in picked} == {"power", "markets", "weather"}
    assert pick_cards([], 6) == [] and len(pick_cards(rows, 20)) == len(rows)

    done = [_row(f"d{i}", "power", {}, outcome=i % 2) for i in range(10)]
    out = split_outcomes(
        [*done, _row("o", "power", {}), _row("v", "power", {}, state="void (bug)")], 8
    )
    assert (
        len(out["shown"]) == 8 and out["resolved"] == 10 and out["open"] == 1 and out["total"] == 12
    )


def test_home_page_lists_only_answered_forecasters_on_cards(tmp_path) -> None:
    """Rows without a forecast ('–') are replaced by one summary line."""
    home = (_site(tmp_path) / "index.html").read_text()
    assert 'class="bars bars-rest"' not in home  # the empty-ledger build has no cards at all
    import re

    card_html = "".join(re.findall(r'<li class="qcard">.*?</li>', home, re.S))
    assert "<abbr" not in card_html  # no dash placeholders inside cards
