"""`arena site build`: render the static site from the ledger (SPEC 11).

Every number on the site is computed here from the ledger by code (integrity rule I5).
"""

from __future__ import annotations

import html
import json
import re
import shutil
import urllib.parse
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from arena.agent.tools import GDELT_ATTRIBUTION
from arena.analytics.sql import connect as sql_connect
from arena.analytics.sql import export_parquet, run_queries
from arena.clock import Clock
from arena.config import DEFAULT_REPO_URL, DEFAULT_SITE_URL
from arena.ledger import Ledger, layout
from arena.ledger.verify import verify
from arena.models import Question, RunManifest
from arena.ops.official import STREAK, update_official_start
from arena.ops.weekly import summaries as weekly_summaries
from arena.scoring.boards import MIN_DAYS, all_boards, official
from arena.scoring.core import Scored, clip, counts, load
from arena.scoring.findings import findings, power_table
from arena.scoring.stats import calibration_bins, expected_calibration_error, murphy
from arena.site.charts import forest_svg, race_svg, reliability_svg, series_class
from arena.site.methods_content import LIMITATIONS, PRINCIPLES
from arena.site.ops_status import llm_usage, missed_days, parse_failures, source_freshness
from arena.site.titles import FORECASTER_NAMES, domain_name, forecaster_name, plain_title
from arena.sources.brightsky import ATTRIBUTION as WX_ATTRIBUTION
from arena.sources.brightsky import LICENCE as WX_LICENCE
from arena.sources.ecb import ATTRIBUTION as ECB_ATTRIBUTION
from arena.sources.smard import ATTRIBUTION as SMARD_ATTRIBUTION
from arena.sources.smard import LICENCE as SMARD_LICENCE
from arena.sources.wikimedia import ATTRIBUTION as WIKI_ATTRIBUTION

NAV: tuple[tuple[str, str], ...] = (
    ("index.html", "Home"),
    ("questions/index.html", "Questions"),
    ("leaderboard.html", "Leaderboard"),
    ("calibration.html", "Calibration"),
    ("findings.html", "Findings"),
    ("guide.html", "Guide"),
    ("methods.html", "Methods"),
    ("stack.html", "Tech stack"),
    ("status.html", "Status"),
    ("about.html", "About"),
)
#: CC BY 4.0 asks to indicate changes: daily statistics, thresholds and returns are
#: computed by this project from the published values.
ATTRIBUTIONS = (
    f"electricity prices: {SMARD_ATTRIBUTION} ({SMARD_LICENCE}; daily statistics computed "
    "by this project)",
    f"weather: {WX_ATTRIBUTION} ({WX_LICENCE}; daily values computed by this project)",
    f"attention: {WIKI_ATTRIBUTION}",
    f"exchange rates: {ECB_ATTRIBUTION}",
    f"news headlines for the agent: {GDELT_ATTRIBUTION}",
)
FEED_BATCHES = 7
#: Marker of an unfinished owner-written draft (docs/legal/*.md); such files stay unpublished.
PLACEHOLDER = "[FILL IN"
SKIP_HELP = {
    "not_sampled": "the AI forecasters answer a fixed daily sample per topic, to cap cost",
    "budget_exhausted": "the daily AI token or request cap was reached",
    "parse_failure": "the AI answer did not match the required JSON format, even after a repair",
    "model_missing": "no AI model or key configured",
    "error": "the forecaster raised an error (for example missing input data)",
}
#: Libraries shown on the tech-stack page, with the version installed where the site is
#: built (read at build time, never typed in by hand).
STACK_LIBRARIES = (
    ("scikit-learn", "gradient-boosted quantile regression and classification, calibration"),
    ("numpy", "numerics"),
    ("scipy", "Student-t distributions for volatility models"),
    ("anthropic", "official Claude SDK for the LLM and agent forecasters"),
    ("pydantic", "typed, validated ledger records and settings"),
    ("jinja2", "static site generation"),
    ("click", "command-line interface for every job"),
    ("joblib", "model artefacts in the registry"),
    ("lightgbm", "challenger gradient-boosting models (quantile regression, classification)"),
    ("optuna", "hyperparameter search for the LightGBM challenger (time-series folds)"),
    ("shap", "SHAP explanations of LightGBM models"),
    ("statsmodels", "ETS and SARIMAX benchmarks in the power backtest"),
    ("fastembed", "local ONNX text embeddings for the agent's similar-questions tool (RAG)"),
    ("chronos-forecasting", "Chronos-Bolt tiny (pretrained time-series model), backtest only"),
    ("mlflow-skinny", "experiment tracking of the weekly retraining (SQLite backend)"),
    ("evidently", "data-drift reports on model inputs"),
)


def library_versions() -> list[dict[str, str]]:
    """Name, installed version (or "not installed here") and role of each library."""
    from importlib.metadata import PackageNotFoundError, version

    out = []
    for name, role in STACK_LIBRARIES:
        try:
            v = version(name)
        except PackageNotFoundError:
            v = "used by the weekly job; not installed in this build"
        out.append({"name": name, "version": v, "role": role})
    return out


def live_versions(rec: Any) -> list[dict[str, str]]:
    """The most recent version string each forecaster published, from the ledger."""
    latest: dict[str, tuple[Any, str]] = {}
    for f in rec.forecasts:
        cur = latest.get(f.forecaster_id)
        if cur is None or f.created_at > cur[0]:
            latest[f.forecaster_id] = (f.created_at, f.forecaster_version)
    rows = []
    for fid in sorted(latest):
        v = latest[fid][1]
        rows.append({"id": fid, "version": v, "model": v.split("|", 1)[0] if "|" in v else v})
    return rows


INFORMATION_SETS = (
    ("base_rate", "Trailing outcomes of the same template and entity", "all questions"),
    ("persistence", "Yesterday's outcome of the same template and entity", "all questions"),
    ("ml", "The full as-of context", "all questions (planned)"),
    (
        "llm_plain",
        "Question text, resolution rule, current date; no data, no tools",
        "daily sample (planned)",
    ),
    (
        "llm_context",
        "The above plus a compact rendering of the as-of context",
        "daily sample (planned)",
    ),
    ("agent", "As llm_context, plus read-only tools", "daily sample (planned)"),
)


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


AI_FORECASTERS = frozenset({"llm_plain", "llm_context", "agent"})


def race_data(scored: Sequence[Scored]) -> dict[str, Any]:
    """Cumulative mean (clipped) Brier score per forecaster after each batch day, on the
    questions every plotted forecaster answered (a fair, like-for-like race). Display only;
    the leaderboards with intervals come from `arena.scoring`."""
    by_q: dict[str, dict[str, Scored]] = {}
    for s in scored:
        by_q.setdefault(s.question_id, {})[s.forecaster_id] = s
    fids = sorted({s.forecaster_id for s in scored})
    common = [q for q, m in by_q.items() if all(f in m for f in fids)]
    if len(fids) < 2 or not common:
        return {"days": [], "series": {}, "n": 0, "fids": fids}
    days = sorted({by_q[q][fids[0]].batch_date for q in common})
    series: dict[str, list[tuple[str, float]]] = {f: [] for f in fids}
    for f in fids:
        tot, cnt = 0.0, 0
        for d in days:
            for q in common:
                s = by_q[q][f]
                if s.batch_date == d:
                    tot += (clip(s.probability) - s.outcome) ** 2
                    cnt += 1
            series[f].append((d.isoformat(), tot / cnt))
    return {"days": [d.isoformat() for d in days], "series": series, "n": len(common),
            "fids": fids}  # fmt: skip


def featured_row(rows: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    """The latest question on which the forecasters disagree most (display only)."""
    best, spread = None, -1.0
    for r in rows:
        ps = list(r["pn"].values())
        if len(ps) >= 2 and max(ps) - min(ps) > spread:
            best, spread = r, max(ps) - min(ps)
    return None if best is None else {**best, "spread": spread}


def domain_stats(rec: Any) -> list[dict[str, Any]]:
    """Questions and resolved questions per domain."""
    out: dict[str, dict[str, Any]] = {}
    for q in rec.questions.values():
        d = out.setdefault(q.domain, {"domain": q.domain, "questions": 0, "resolved": 0})
        d["questions"] += 1
        if q.question_id in rec.resolutions:
            d["resolved"] += 1
    return [out[k] for k in sorted(out)]


def question_scores(forecasts: Sequence[Any], outcome: int | None) -> list[dict[str, Any]]:
    """Per forecast of one question: probability and, once resolved, its (clipped) Brier
    score; closest first. Display only; leaderboards come from `arena.scoring`."""
    rows = []
    for f in forecasts:
        b = None if outcome is None else (clip(f.probability) - outcome) ** 2
        rows.append({"f": f, "brier": b})
    if outcome is not None:
        rows.sort(key=lambda r: (r["brier"], r["f"].forecaster_id))
    return rows


def simple_markdown(text: str) -> Markup:
    """Tiny, safe renderer for human-written pages: paragraphs, `#` headings, links.

    Everything is HTML-escaped first; only [text](https://...) links are turned into anchors.
    """
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    out = []
    for b in blocks:
        esc = html.escape(b)
        esc = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', esc)
        m = re.match(r"^(#{1,3})\s+(.*)$", esc)
        if m:
            level = len(m.group(1)) + 1
            out.append(f"<h{level}>{m.group(2)}</h{level}>")
        else:
            out.append("<p>" + esc.replace("\n", "<br>") + "</p>")
    return Markup("\n".join(out))


def _fmt_p(p: float) -> str:
    return f"{p:.2f}"


def _rows(questions: Sequence[Question], rec: Any) -> tuple[list[dict[str, Any]], list[str]]:
    by_q: dict[str, dict[str, str]] = {}
    pn: dict[str, dict[str, float]] = {}
    fids: set[str] = set()
    for f in rec.forecasts:
        by_q.setdefault(f.question_id, {})[f.forecaster_id] = _fmt_p(f.probability)
        pn.setdefault(f.question_id, {})[f.forecaster_id] = f.probability
        fids.add(f.forecaster_id)
    rows = []
    for q in questions:
        r = rec.resolutions.get(q.question_id)
        v = rec.voids.get(q.question_id)
        state = f"void ({v.reason_code})" if v is not None and r is None else "open"
        rows.append(
            {
                "qid": q.question_id,
                "text": q.text,
                "title": plain_title(q),
                "domain": q.domain,
                "pn": pn.get(q.question_id, {}),
                "lock": q.lock_time.strftime("%Y-%m-%d %H:%M UTC"),
                "p": by_q.get(q.question_id, {}),
                "outcome": None if r is None else r.outcome,
                "observed": None if r is None else r.observed_value,
                "state": state,
            }
        )
    order = ["base_rate", "persistence", "ml", "llm_plain", "llm_context", "agent"]
    ordered = [f for f in order if f in fids] + sorted(fids - set(order))
    return rows, ordered


def _runs(ledger: Ledger, limit: int = 20) -> list[RunManifest]:
    out = []
    for rel in ledger.list_files("runs"):
        rec = ledger.read_json(rel)
        if isinstance(rec, RunManifest):
            out.append(rec)
    return sorted(out, key=lambda r: r.started_at, reverse=True)[:limit]


def official_start(ledger: Ledger) -> str | None:
    """The official start date if `meta/official_start.json` exists."""
    if not ledger.exists(layout.OFFICIAL_START_PATH):
        return None
    data = json.loads(ledger.read_bytes(layout.OFFICIAL_START_PATH))
    value = data.get("official_start")
    return str(value) if value else None


def version_changelog(rec: Any) -> list[dict[str, Any]]:
    """First batch date on which each (forecaster, version) appeared."""
    first: dict[tuple[str, str], date] = {}
    for f in rec.forecasts:
        q = rec.questions.get(f.question_id)
        if q is None:
            continue
        k = (f.forecaster_id, f.forecaster_version)
        if k not in first or q.batch_date < first[k]:
            first[k] = q.batch_date
    rows = [{"forecaster": k[0], "version": k[1], "since": d} for k, d in first.items()]
    return sorted(rows, key=lambda r: (r["since"], r["forecaster"], r["version"]))


def calibration_panels(scored: Sequence[Scored]) -> list[dict[str, Any]]:
    """Per forecaster: bins, ECE, Murphy decomposition and the SVG diagram."""
    by: dict[str, list[Scored]] = {}
    for s in scored:
        by.setdefault(s.forecaster_id, []).append(s)
    out = []
    for fid in sorted(by):
        ss = by[fid]
        p, y = [s.probability for s in ss], [s.outcome for s in ss]
        bins = calibration_bins(p, y)
        out.append(
            {
                "forecaster": fid,
                "n": len(ss),
                "bins": bins,
                "svg": reliability_svg(fid, bins),
                "ece": expected_calibration_error(p, y),
                "murphy": murphy(p, y),
            }
        )
    return out


def question_href(question_id: str, prefix: str = "questions/") -> str:
    """Link to a question page (ids may contain '%', which is encoded)."""
    return prefix + urllib.parse.quote(question_id, safe="") + ".html"


def build_site(
    ledger: Ledger,
    out_dir: Path,
    clock: Clock,
    content_dir: Path | None = None,
    site_url: str = DEFAULT_SITE_URL,
    llm_token_cap: int | None = None,
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
    }
    archive = sorted(
        rec.questions.values(), key=lambda q: (q.batch_date, q.question_id), reverse=True
    )
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
            {"headline": headline, "rehearsal": rehearsal_boards, "official_days": off_days},
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
                "principles": PRINCIPLES,
                "limitations": LIMITATIONS,
            },
        ),
        "experiments.html": ("Experiments", {"runs": weekly_summaries(ledger)}),
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
    pages["data.html"] = (
        "Open data & SQL",
        {"files": export_parquet(con, tmp / "data"), "results": run_queries(con)},
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
        )
        (tmp / "questions" / f"{q.question_id}.html").write_text(html_text, encoding="utf-8")
    static = Path(__file__).parent / "static"
    for f in static.iterdir():
        shutil.copy(f, tmp / "static" / f.name)
    (tmp / ".nojekyll").write_text("", encoding="utf-8")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    tmp.rename(out_dir)
    return SiteResult(out_dir, sorted(pages))
