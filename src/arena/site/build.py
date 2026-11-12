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
from arena.clock import Clock
from arena.ledger import Ledger, layout
from arena.ledger.verify import verify
from arena.models import Question, RunManifest
from arena.scoring.boards import all_boards, official
from arena.scoring.core import Scored, counts, load
from arena.scoring.findings import findings
from arena.scoring.stats import calibration_bins, expected_calibration_error, murphy
from arena.site.charts import reliability_svg
from arena.site.methods_content import LIMITATIONS, PRINCIPLES
from arena.sources.brightsky import ATTRIBUTION as WX_ATTRIBUTION
from arena.sources.brightsky import LICENCE as WX_LICENCE
from arena.sources.ecb import ATTRIBUTION as ECB_ATTRIBUTION
from arena.sources.smard import ATTRIBUTION as SMARD_ATTRIBUTION
from arena.sources.smard import LICENCE as SMARD_LICENCE
from arena.sources.wikimedia import ATTRIBUTION as WIKI_ATTRIBUTION

NAV: tuple[tuple[str, str], ...] = (
    ("index.html", "Home"),
    ("leaderboard.html", "Leaderboard"),
    ("calibration.html", "Calibration"),
    ("questions/index.html", "Questions"),
    ("findings.html", "Findings"),
    ("methods.html", "Methods"),
    ("status.html", "Status"),
    ("about.html", "About"),
)
ATTRIBUTIONS = (
    f"electricity prices: {SMARD_ATTRIBUTION} ({SMARD_LICENCE})",
    f"weather: {WX_ATTRIBUTION} ({WX_LICENCE})",
    f"attention: {WIKI_ATTRIBUTION}",
    f"exchange rates: {ECB_ATTRIBUTION}",
    f"news headlines for the agent: {GDELT_ATTRIBUTION}",
)
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
    return Environment(
        loader=PackageLoader("arena.site", "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


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
    fids: set[str] = set()
    for f in rec.forecasts:
        by_q.setdefault(f.question_id, {})[f.forecaster_id] = _fmt_p(f.probability)
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
    ledger: Ledger, out_dir: Path, clock: Clock, content_dir: Path | None = None
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
        return simple_markdown(path.read_text(encoding="utf-8")) if path.is_file() else None

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
    }
    archive = sorted(
        rec.questions.values(), key=lambda q: (q.batch_date, q.question_id), reverse=True
    )
    pages: dict[str, tuple[str, dict[str, Any]]] = {
        "index.html": (
            "Home",
            {
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
        "questions/index.html": ("Questions", {"archive": archive, "rec": rec}),
        "findings.html": (
            "Findings",
            {"findings": findings(off, off_days), "human": read_content("findings.md")},
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
        "status.html": ("Status", {"counts": counts(rec), "runs": _runs(ledger)}),
        "about.html": (
            "About",
            {"about": read_content("about.md"), "legal": read_content("legal.md")},
        ),
    }
    env = _env()
    tmp = out_dir.with_name(out_dir.name + ".building")
    if tmp.exists():
        shutil.rmtree(tmp)
    (tmp / "static").mkdir(parents=True)
    (tmp / "questions").mkdir()
    for name, (title, ctx) in pages.items():
        root = "../" if "/" in name else ""
        nav_page = "questions/index.html" if name == "questions/index.html" else name
        html_text = env.get_template(name.replace("/", "_")).render(
            title=title, page=nav_page, **{**common, "root": root}, **ctx
        )
        (tmp / name).write_text(html_text, encoding="utf-8")
    qtpl = env.get_template("question.html")
    for q in rec.questions.values():
        fs = sorted(
            (f for f in rec.forecasts if f.question_id == q.question_id),
            key=lambda f: f.forecaster_id,
        )
        sk = sorted(
            (s for s in rec.skips if s.question_id == q.question_id), key=lambda s: s.forecaster_id
        )
        html_text = qtpl.render(
            title=q.question_id,
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
