"""Data shaping for the site pages: turn ledger records into template rows (T187).

Split out of `site/build.py`. Every number shown on the site is computed here or in the
scoring package from the ledger by code (integrity rule I5).
"""

from __future__ import annotations

import gzip
import html
import json
import re
import urllib.parse
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from markupsafe import Markup

from arena.ledger import Ledger, layout
from arena.models import Question, RunManifest
from arena.scoring.core import Scored, clip
from arena.scoring.stats import calibration_bins, expected_calibration_error, murphy
from arena.site.charts import reliability_svg
from arena.site.content import (
    STACK_LIBRARIES,
    TEMPLATE_VERSION_NOTES,
)
from arena.site.qchart import chart_data, series_svg
from arena.site.titles import plain_title


def library_versions() -> list[dict[str, str]]:
    """Name, installed version (or "not installed here") and role of each library."""
    from importlib.metadata import PackageNotFoundError, version

    out = []
    for name, role in STACK_LIBRARIES:
        try:
            v = version(name)
        except PackageNotFoundError:
            v = "installed by another job, not by this site build"
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
    return {"days": [d.isoformat() for d in days], "series": series, "n": len(common), "fids": fids}


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
    order = [
        "base_rate",
        "persistence",
        "ml",
        "llm_plain",
        "llm_context",
        "llm_local",
        "agent",
        "agent_graph",
    ]
    ordered = [f for f in order if f in fids] + sorted(fids - set(order))
    return rows, ordered


def _runs(ledger: Ledger, limit: int = 20) -> list[RunManifest]:
    out = []
    for rel in ledger.list_files("runs"):
        rec = ledger.read_json(rel)
        if isinstance(rec, RunManifest):
            out.append(rec)
    return sorted(out, key=lambda r: r.started_at, reverse=True)[:limit]


def _question_chart(
    ledger: Ledger, snaps: dict[tuple[str, date], dict[str, Any]], q: Question, res: Any
) -> dict[str, Any] | None:
    """Chart (SVG and table rows) from the morning snapshot of the question's batch."""
    key = (q.domain, q.batch_date)
    if key not in snaps:
        rel = f"{layout.snapshot_dir(q.domain, q.batch_date)}/morning_context.json.gz"
        snaps[key] = (
            json.loads(gzip.decompress(ledger.read_bytes(rel))) if ledger.exists(rel) else {}
        )
    ctx = snaps[key].get(q.question_id)
    if not isinstance(ctx, dict):
        return None
    cd = chart_data(q, ctx, None if res is None else res.observed_value)
    if cd is None or not any(pts for _, pts in cd.series):
        return None
    return {"svg": series_svg(cd), "data": cd}


def model_timeline(runs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every weekly decision per domain, newest first (promotions and keeps)."""
    out = []
    for r in runs:
        if r.get("dry_run"):
            continue
        for d in r.get("decisions", []):
            out.append(
                {
                    "day": r["day"],
                    "domain": d["domain"],
                    "promoted": d.get("promoted"),
                    "family": d.get("best_family"),
                    "reason": d.get("reason", ""),
                }
            )
    return out


def drift_badge(metrics: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    """Share of drifted inputs from Evidently's drifted-columns metric, as a badge."""
    for m in metrics:
        if "DriftedColumnsCount" in str(m.get("metric")):
            hit = re.search(r"share=([0-9.]+)", str(m.get("value")))
            if hit:
                share = float(hit.group(1))
                return {"alert": share >= 0.5, "text": f"{share:.0%} of model inputs drifted"}
    return None


def eval_runs(evals_dir: Path | None) -> list[dict[str, Any]]:
    """Committed evaluation results (T124), newest first; fake CI-gate runs are skipped."""
    if evals_dir is None or not evals_dir.is_dir():
        return []
    runs = []
    for p in sorted(evals_dir.glob("*.json")):
        if p.name.startswith("fake-"):
            continue
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("kind") == "evaluation":
            runs.append(r)
    return sorted(runs, key=lambda r: str(r.get("created_at")), reverse=True)


def json_validity_change(
    runs: Sequence[dict[str, Any]], fid: str = "llm_plain"
) -> dict[str, str] | None:
    """First-try valid JSON of `fid` in the oldest and newest eval run, as percentages (T186).

    Computed from the committed eval results, so the recruiter page never types it (I5).
    """
    vals = []
    for r in sorted(runs, key=lambda r: str(r.get("created_at"))):
        v = r.get("metrics", {}).get(fid, {}).get("json_valid_first_try")
        if v is not None:
            vals.append(v)
    if len(vals) < 2:
        return None
    return {"before": f"{100 * vals[0]:.0f}%", "after": f"{100 * vals[-1]:.0f}%"}


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


def template_changelog(rec: Any) -> list[dict[str, Any]]:
    """First and last batch date of each (domain, template, template_version) (SPEC 2.9)."""
    span: dict[tuple[str, str, int], list[date]] = {}
    for q in rec.questions.values():
        k = (q.domain, q.template, q.template_version)
        lo_hi = span.setdefault(k, [q.batch_date, q.batch_date])
        lo_hi[0], lo_hi[1] = min(lo_hi[0], q.batch_date), max(lo_hi[1], q.batch_date)
    rows = [
        {
            "domain": k[0],
            "template": k[1],
            "version": k[2],
            "since": v[0],
            "until": v[1],
            "note": TEMPLATE_VERSION_NOTES.get(k[2], ""),
        }
        for k, v in span.items()
    ]
    return sorted(rows, key=lambda r: (r["since"], r["domain"], r["template"], r["version"]))


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


#: Agent forecasters whose tool use is worth showing on the home page.
AGENT_IDS = ("agent", "agent_graph")


def agent_trace_of_day(
    traces: dict[str, list[dict[str, Any]]], rec: Any, batch: date | None
) -> dict[str, Any] | None:
    """The home page's "how the agent worked" card (T189): from the newest batch (up to
    `batch`) that has a successful agent trace, the one with the most tool calls, with the
    published probability. None if there is none; nothing is invented to fill it (I5)."""
    if batch is None:
        return None
    best: tuple[date, int, str, dict[str, Any]] | None = None
    for qid, lines in sorted(traces.items()):
        q = rec.questions.get(qid)
        if q is None or q.batch_date > batch:
            continue
        for t in lines:
            if t.get("forecaster_id") in AGENT_IDS and t.get("outcome") == "forecast":
                key = (q.batch_date, len(t.get("tool_calls") or []))
                if best is None or key > best[:2]:
                    best = (*key, qid, t)
    if best is None:
        return None
    _, _, qid, t = best
    fc = next(
        (
            f
            for f in rec.forecasts
            if f.question_id == qid and f.forecaster_id == t["forecaster_id"]
        ),
        None,
    )
    return {
        "question": rec.questions[qid],
        "href": question_href(qid),
        "forecaster_id": t["forecaster_id"],
        "tools": [c.get("tool") for c in t.get("tool_calls") or []],
        "probability": None if fc is None else fc.probability,
        "outcome": None if qid not in rec.resolutions else rec.resolutions[qid].outcome,
    }
