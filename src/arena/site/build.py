"""`arena site build`: render the static site from the ledger (SPEC 11).

Every number on the site is computed here from the ledger by code (integrity rule I5).
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from arena.analytics.sql import (
    COLUMN_DOCS,
    column_types,
    export_parquet,
    run_dbt_marts,
    run_queries,
)
from arena.analytics.sql import connect as sql_connect
from arena.clock import Clock
from arena.config import DEFAULT_REPO_URL, DEFAULT_SITE_URL
from arena.ledger import Ledger
from arena.ledger.verify import verify
from arena.models import Question
from arena.ops.official import STREAK, update_official_start
from arena.ops.weekly import summaries as weekly_summaries
from arena.scoring.boards import MIN_DAYS, all_boards, official
from arena.scoring.core import counts, load
from arena.scoring.findings import findings, power_table
from arena.site.api import ENDPOINTS, build_api
from arena.site.cards_page import challenger_backtests, headline_backtest, load_cards
from arena.site.charts import forest_svg, race_svg, series_class
from arena.site.content import (
    AI_FORECASTERS,
    ATTRIBUTIONS,
    FEED_BATCHES,
    INFORMATION_SETS,
    NAV,
    NAV_MORE,
    PLACEHOLDER,
    SKIP_HELP,
)
from arena.site.game import live_deck, practice_deck
from arena.site.llm_obs import PRICE_SOURCE, load_spans, totals, traces_by_question, usage_rows
from arena.site.matrices import MIN_N, head_to_head, heatmap
from arena.site.methods_content import LIMITATIONS, PRINCIPLES
from arena.site.ops_status import llm_usage, missed_days, parse_failures, source_freshness
from arena.site.profiles import profile
from arena.site.recruiters import PROOFS
from arena.site.shaping import (
    _question_chart,
    _rows,
    _runs,
    agent_trace_of_day,
    calibration_panels,
    domain_stats,
    drift_badge,
    eval_runs,
    featured_row,
    json_validity_change,
    library_versions,
    live_versions,
    model_timeline,
    official_start,
    question_href,
    question_scores,
    race_data,
    simple_markdown,
    template_changelog,
    version_changelog,
)
from arena.site.titles import FORECASTER_NAMES, domain_name, forecaster_name, plain_title
from arena.site.topics import topic


@dataclass(frozen=True)
class SiteResult:
    """What was built."""

    out_dir: Path
    pages: list[str]


def _env() -> Environment:
    env = Environment(
        loader=PackageLoader("arena.site", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(
        plain_title=plain_title,
        fname=forecaster_name,
        dname=domain_name,
        qhref=question_href,
        is_ai=lambda fid: fid in AI_FORECASTERS,
        race_svg=race_svg,
        forest_svg=forest_svg,
        series_class=series_class,
        all_names=FORECASTER_NAMES,
    )
    return env


def build_site(
    ledger: Ledger,
    out_dir: Path,
    clock: Clock,
    content_dir: Path | None = None,
    site_url: str = DEFAULT_SITE_URL,
    llm_token_cap: int | None = None,
    evals_dir: Path | None = None,
    golden_path: Path | None = None,
    models_dir: Path | None = None,
    dashboard_url: str | None = None,
    marts_dir: Path | None = None,
) -> SiteResult:
    """Render every page into `out_dir` (built aside, then moved into place)."""
    rec = load(ledger)
    rep = verify(ledger)
    by_batch: dict[date, list[Question]] = {}
    for q in rec.questions.values():
        by_batch.setdefault(q.batch_date, []).append(q)
    batches = sorted(by_batch)
    latest_b = batches[-1] if batches else None
    prev_b = batches[-2] if len(batches) > 1 else None
    latest, fids = (
        _rows(sorted(by_batch[latest_b], key=lambda q: q.question_id), rec)
        if latest_b
        else ([], [])
    )
    previous, _ = (
        _rows(sorted(by_batch[prev_b], key=lambda q: q.question_id), rec) if prev_b else ([], [])
    )
    content = content_dir or Path("site_content")

    def read_content(name: str) -> Markup | None:
        path = content / name
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        if PLACEHOLDER in text:  # an unfinished draft is never published
            return None
        return simple_markdown(text)

    start_s = official_start(ledger)
    start = date.fromisoformat(start_s) if start_s else None
    off = official(rec.scored, start)
    rehearsal = [s for s in rec.scored if start is None or s.batch_date < start]
    off_days = len({s.batch_date for s in off})
    domains = sorted({q.domain for q in rec.questions.values()})
    headline = all_boards(off, domains, off_days)
    rehearsal_boards = all_boards(rehearsal, domains)
    common = {
        "nav": NAV,
        "nav_more": NAV_MORE,
        "root": "",
        "attributions": ATTRIBUTIONS,
        "built_at": clock.now().strftime("%Y-%m-%d %H:%M UTC"),
        "official_start": start_s,
        "qhref": question_href,
        "plain_title": plain_title,
        "fname": forecaster_name,
        "has_crypto": any(q.domain == "crypto" for q in rec.questions.values()),
        "dname": domain_name,
        "site_url": site_url.rstrip("/") + "/",
        "repo_url": DEFAULT_REPO_URL,
        "dashboard_url": dashboard_url,
    }
    archive = sorted(
        rec.questions.values(), key=lambda q: (q.batch_date, q.question_id), reverse=True
    )
    urows = usage_rows(load_spans(ledger))
    runs_w = weekly_summaries(ledger)
    game = {"live": live_deck(rec), "practice": practice_deck(golden_path)}
    info = {fid: (sees, cadence) for fid, sees, cadence in INFORMATION_SETS}
    mfids = sorted({s.forecaster_id for s in (off if off else rehearsal)})
    changelog = version_changelog(rec)
    fids = sorted({f.forecaster_id for f in rec.forecasts} | {s.forecaster_id for s in rec.skips})
    profiles = [profile(fid, rec, FORECASTER_NAMES, changelog, urows, info) for fid in fids]
    game_payload = json.dumps({**game, "names": FORECASTER_NAMES}, sort_keys=True)
    # A JSON data block is never executed; "</" is escaped so it cannot end the element.
    game_json = Markup(game_payload.replace("</", "<\\/"))
    pages: dict[str, tuple[str, dict[str, Any]]] = {
        "index.html": (
            "Home",
            {
                "race": race_data(off if off else rehearsal),
                "race_scope": "official record" if off else "rehearsal days",
                "featured": featured_row(latest),
                "topics": domain_stats(rec),
                "forecast_count": len(rec.forecasts),
                "ml_live": any(f.forecaster_id == "ml" for f in rec.forecasts),
                "backtest": headline_backtest(models_dir),
                "agent_card": agent_trace_of_day(traces_by_question(ledger), rec, latest_b),
                "days_live": len(batches),
                "counts": counts(rec),
                "verify_ok": rep.ok,
                "verify_summary": rep.summary(),
                "latest_batch": latest_b,
                "latest": latest,
                "forecasters": fids,
                "previous_batch": prev_b,
                "previous": previous,
                "headline": headline[0],
                "rehearsal_board": rehearsal_boards[0],
                "official_days": off_days,
            },
        ),
        "leaderboard.html": (
            "Leaderboard",
            {
                "headline": headline,
                "rehearsal": rehearsal_boards,
                "official_days": off_days,
                "heat": heatmap(off if off else rehearsal, mfids, domains),
                "h2h": head_to_head(off if off else rehearsal, mfids),
                "matrix_scope": "official record" if off else "rehearsal days",
                "min_n": MIN_N,
            },
        ),
        "calibration.html": (
            "Calibration",
            {
                "panels": calibration_panels(off if off else rehearsal),
                "scope": "official record" if off else "rehearsal days (not the official record)",
            },
        ),
        "questions/index.html": (
            "Questions",
            {"archive": archive, "rec": rec, "domains": domains, "current": None},
        ),
        "guide.html": ("Guide", {}),
        "stack.html": (
            "Tech stack",
            {
                "libraries": library_versions(),
                "live": live_versions(rec),
                "weekly": weekly_summaries(ledger)[:1],
            },
        ),
        "privacy.html": ("Privacy", {"owner_privacy": read_content("privacy.md")}),
        "imprint.html": (
            "Imprint",
            {"imprint": read_content("imprint.md") or read_content("legal.md")},
        ),
        "404.html": ("Page not found", {"base_href": site_url.rstrip("/") + "/"}),
        "findings.html": (
            "Findings",
            {
                "findings": findings(off, off_days),
                "human": read_content("findings.md"),
                "official_days": off_days,
                "min_days": MIN_DAYS,
                "power": power_table(rec.scored),
            },
        ),
        "methods.html": (
            "Methods",
            {
                "information_sets": INFORMATION_SETS,
                "changelog": version_changelog(rec),
                "template_changelog": template_changelog(rec),
                "principles": PRINCIPLES,
                "limitations": LIMITATIONS,
            },
        ),
        "experiments.html": (
            "Experiments",
            {
                "runs": runs_w,
                "timeline": model_timeline(runs_w),
                "drift_badge": drift_badge,
                "challengers": challenger_backtests(models_dir),
            },
        ),
        "status.html": (
            "Status",
            {
                "counts": counts(rec),
                "runs": _runs(ledger),
                "skip_help": SKIP_HELP,
                "streak": update_official_start(ledger, clock.now(), write=False),
                "streak_needed": STREAK,
                "missed": missed_days(ledger, clock.now().date()),
                "usage": llm_usage(ledger, clock.now().date()),
                "token_cap": llm_token_cap,
                "parse": parse_failures(rec),
                "fresh": source_freshness(rec, clock.now()),
                "now": clock.now(),
            },
        ),
        "llm.html": (
            "LLM observability",
            {
                "rows": urows,
                "total": totals(urows),
                "price_source": PRICE_SOURCE,
                "parse": parse_failures(rec),
            },
        ),
        "evals.html": ("LLM evals", {"runs": eval_runs(evals_dir)}),
        "backtests.html": ("Backtests", {"cards": load_cards(models_dir)}),
        "api.html": ("JSON API", {"endpoints": ENDPOINTS}),
        "de.html": (
            "Auf Deutsch",
            {
                "page_lang": "de",
                "k": {
                    "questions": len(rec.questions),
                    "forecasts": len(rec.forecasts),
                    "forecasters": len({f.forecaster_id for f in rec.forecasts}),
                },
            },
        ),
        "recruiters.html": (
            "For recruiters",
            {
                "proofs": PROOFS,
                "personal": read_content("recruiters.md"),
                "json_change": json_validity_change(eval_runs(evals_dir)),
                "k": {
                    "questions": len(rec.questions),
                    "forecasts": len(rec.forecasts),
                    "forecasters": len({f.forecaster_id for f in rec.forecasts}),
                    "days": len({q.batch_date for q in rec.questions.values()}),
                },
            },
        ),
        "forecasters/index.html": ("Forecasters", {"profiles": profiles}),
        "topics/index.html": ("Topics", {"topics": [topic(d, rec) for d in domains]}),
        "play.html": (
            "Can you beat the AI?",
            {
                "live": game["live"],
                "live_n": len(game["live"]),
                "practice_n": len(game["practice"]),
                "game_json": game_json,
            },
        ),
        "about.html": (
            "About",
            {"about": read_content("about.md"), "legal": read_content("legal.md")},
        ),
    }
    env = _env()
    con = sql_connect(rec)
    tmp = out_dir.with_name(out_dir.name + ".building")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "static").mkdir(parents=True)
    (tmp / "questions").mkdir()
    (tmp / "forecasters").mkdir()
    (tmp / "topics").mkdir()
    (tmp / "data").mkdir(exist_ok=True)
    (tmp / "data" / "game.json").write_text(game_payload + "\n", encoding="utf-8")
    pages["data.html"] = (
        "Open data & SQL",
        {
            "files": export_parquet(con, tmp / "data"),
            "results": run_queries(con),
            "dictionary": COLUMN_DOCS,
            "types": column_types(),
            "marts": run_dbt_marts(con, marts_dir),
        },
    )
    for name, (title, ctx) in pages.items():
        root = "../" if "/" in name else ""
        nav_page = "questions/index.html" if name == "questions/index.html" else name
        html_text = env.get_template(name.replace("/", "_")).render(
            title=title, page=nav_page, **{**common, "root": root}, **ctx
        )
        (tmp / name).write_text(html_text, encoding="utf-8")
    itpl = env.get_template("questions_index.html")
    for dom in domains:
        html_text = itpl.render(
            title=f"Questions: {domain_name(dom)}",
            page="questions/index.html",
            **{**common, "root": "../"},
            archive=[q for q in archive if q.domain == dom],
            rec=rec,
            domains=domains,
            current=dom,
        )
        (tmp / "questions" / f"topic-{dom}.html").write_text(html_text, encoding="utf-8")
    feed = env.get_template("feed.xml").render(
        **common,
        updated=clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        batches=[
            (b, sorted(by_batch[b], key=lambda q: q.question_id))
            for b in reversed(batches[-FEED_BATCHES:])
        ],
    )
    (tmp / "feed.xml").write_text(feed, encoding="utf-8")
    qtpl = env.get_template("question.html")
    qtraces = traces_by_question(ledger)
    ordered = sorted(rec.questions.values(), key=lambda q: (q.domain, q.batch_date, q.question_id))
    neighbours = {
        q.question_id: (
            ordered[i - 1] if i > 0 and ordered[i - 1].domain == q.domain else None,
            ordered[i + 1] if i + 1 < len(ordered) and ordered[i + 1].domain == q.domain else None,
        )
        for i, q in enumerate(ordered)
    }
    snaps: dict[tuple[str, date], dict[str, Any]] = {}
    for q in rec.questions.values():
        fs = sorted(
            (f for f in rec.forecasts if f.question_id == q.question_id),
            key=lambda f: f.forecaster_id,
        )
        sk = sorted(
            (s for s in rec.skips if s.question_id == q.question_id), key=lambda s: s.forecaster_id
        )
        res_q = rec.resolutions.get(q.question_id)
        html_text = qtpl.render(
            title=plain_title(q),
            scores=question_scores(fs, None if res_q is None else res_q.outcome),
            page="questions/index.html",
            **{**common, "root": "../"},
            q=q,
            forecasts=fs,
            skips=sk,
            resolution=rec.resolutions.get(q.question_id),
            void=rec.voids.get(q.question_id),
            before_lock=clock.now() < q.lock_time,
            traces=qtraces.get(q.question_id, []),
            chart=_question_chart(ledger, snaps, q, res_q),
            prev_q=neighbours[q.question_id][0],
            next_q=neighbours[q.question_id][1],
        )
        (tmp / "questions" / f"{q.question_id}.html").write_text(html_text, encoding="utf-8")
    ftpl = env.get_template("forecaster.html")
    for p in profiles:
        html_text = ftpl.render(
            title=forecaster_name(p["fid"]),
            page="forecasters/index.html",
            **{**common, "root": "../"},
            p=p,
        )
        (tmp / "forecasters" / f"{p['fid']}.html").write_text(html_text, encoding="utf-8")
    head_all = [
        b
        for b in (headline if off else rehearsal_boards)
        if b.kind == "all" and b.domain == "overall"
    ]
    build_api(
        tmp,
        rec,
        head_all[0] if head_all else None,
        "official" if off else "rehearsal",
        clock.now(),
        question_href,
    )
    ttpl = env.get_template("topic.html")
    scope = "official record" if off else "rehearsal days"
    for dom in domains:
        boards_d = [b for b in (headline if off else rehearsal_boards) if b.domain == dom]
        html_text = ttpl.render(
            title=domain_name(dom),
            page="topics/index.html",
            **{**common, "root": "../"},
            t=topic(dom, rec),
            boards=boards_d,
            scope=scope,
            race=race_data([s for s in (off if off else rehearsal) if s.domain == dom]),
        )
        (tmp / "topics" / f"{dom}.html").write_text(html_text, encoding="utf-8")
    static = Path(__file__).parent / "static"
    for f in static.iterdir():
        shutil.copy(f, tmp / "static" / f.name)
    (tmp / ".nojekyll").write_text("", encoding="utf-8")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    tmp.rename(out_dir)
    return SiteResult(out_dir, sorted(pages))
