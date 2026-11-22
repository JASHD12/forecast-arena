"""The forecast-audit case page (T322): a German electricity alert study, from its report.

Everything on the page is read from the committed files of
`examples/forecast-audit/german-electricity`: the report written by the standalone tool, plus
the case and prediction CSVs. Nothing is typed here: sentences and tables are generated from
those numbers (I5), so the page cannot drift from the JSON a reader can reproduce.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from markupsafe import Markup, escape

DEFAULT_DIR = (
    Path(__file__).resolve().parents[3] / "examples" / "forecast-audit" / "german-electricity"
)
NAMES = {
    "base_rate": "Base rate",
    "fine_tuned_gguf": "Fine-tuned 1.5B model",
    "always_alert": "Always alert",
    "never_alert": "Never alert",
}
CHART_POLICIES = ("base_rate", "fine_tuned_gguf", "always_alert")
CHART_CLASS = {"base_rate": "s-ref", "fine_tuned_gguf": "s-1", "always_alert": "s-5"}
CHART_WIDE = (680, 300)
CHART_NARROW = (360, 340)


def _csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def _ratio(fa: float, miss: float) -> str:
    return f"{fa:g} : {miss:g}"


def load_case(directory: Path | None = None) -> dict[str, Any] | None:
    """The case for the page, or None when its files are not there (the page is then omitted)."""
    d = directory or DEFAULT_DIR
    try:
        report = json.loads((d / "expected" / "report.json").read_text(encoding="utf-8"))
        cases = _csv(d / "cases.csv")
        preds = _csv(d / "predictions.csv")
        audited = _csv(d / "expected" / "cases-audited.csv")
    except (OSError, ValueError):
        return None
    cand, base = report["candidate"], report["baseline"]
    n = len(cases)
    yes = sum(c["outcome"] == "1" for c in cases)
    primary = report["decision"]
    pol = {p["policy"]: p for p in primary["policies"]}
    flags = {m: [r["alert"] for r in audited if r["model_id"] == m] for m in (cand, base)}
    differing = sum(a != b for a, b in zip(flags[cand], flags[base], strict=True))
    probs = {
        m: [float(p["probability"]) for p in preds if p["model_id"] == m] for m in (cand, base)
    }
    q = report["quality"]["models"]
    blocks = [primary, *report["sensitivity"]]
    blocks.sort(key=lambda b: b["miss_cost"] / b["false_alert_cost"])
    sens = [
        {
            "ratio": _ratio(b["false_alert_cost"], b["miss_cost"]),
            "cutoff": b["cutoff"],
            "primary": b is primary,
            "loss": {p["policy"]: p["total_loss"] for p in b["policies"]},
        }
        for b in blocks
    ]
    first_loss = {
        "base": pol[base]["total_loss"],
        "cand": pol[cand]["total_loss"],
        "always": pol["always_alert"]["total_loss"],
        "never": pol["never_alert"]["total_loss"],
    }
    case: dict[str, Any] = {
        "report": report,
        "candidate": cand,
        "baseline": base,
        "n": n,
        "yes": yes,
        "no": n - yes,
        "first_day": report["time_scope"]["first_day"],
        "last_day": report["time_scope"]["last_day"],
        "cutoff": primary["cutoff"],
        "false_cost": primary["false_alert_cost"],
        "miss_cost": primary["miss_cost"],
        "rows": [
            {
                "name": NAMES.get(p, p),
                "policy": p,
                "brier": q[p]["brier"] if p in q else None,
                "alerts": pol[p]["alerts"],
                "false_alerts": pol[p]["false_alerts"],
                "misses": pol[p]["misses"],
                "loss": pol[p]["total_loss"],
            }
            for p in (base, cand, "always_alert", "never_alert")
        ],
        "differing_decisions": differing,
        "same_decisions": differing == 0,
        "alerts": pol[cand]["alerts"],
        "false_alerts": pol[cand]["false_alerts"],
        "prob_range": {m: (min(v), max(v)) for m, v in probs.items()},
        "sensitivity": sens,
        "losses": first_loss,
        "timing_label": report["timing_label"],
        "interval": report["intervals"]["day_block"],
    }
    case["examples"] = _examples(cases, preds, cand, base, sens)
    case["chart"] = Markup(
        _chart(sens, narrow=False) + _chart(sens, narrow=True)
    )  # two layouts, CSS picks one
    case["headline_en"] = headline(case, "en")
    case["headline_de"] = headline(case, "de")
    return case


def _examples(
    cases: list[dict[str, str]],
    preds: list[dict[str, str]],
    cand: str,
    base: str,
    sens: list[dict[str, Any]],
) -> dict[str, Any]:
    """Two disclosed examples at the equal-cost cutoff: the first day (by target date) on which
    the model stays silent where the base rate alerts, once for each outcome."""
    equal = next((s for s in sens if s["ratio"] == "1 : 1"), None)
    if equal is None:
        return {"cutoff": None, "helped": None, "hurt": None}
    cut = equal["cutoff"]
    by = {(p["case_id"], p["model_id"]): float(p["probability"]) for p in preds}
    helped = hurt = None
    for c in sorted(cases, key=lambda c: (c["group_day"], c["case_id"])):
        pc, pb = by[(c["case_id"], cand)], by[(c["case_id"], base)]
        if pc < cut <= pb:  # silent model, alerting base rate
            row = {"day": c["group_day"], "p_model": pc, "p_base": pb, "outcome": int(c["outcome"])}
            if row["outcome"] == 0 and helped is None:
                helped = row
            if row["outcome"] == 1 and hurt is None:
                hurt = row
    return {"cutoff": cut, "helped": helped, "hurt": hurt}


def headline(case: dict[str, Any], lang: str) -> str:
    """One sentence from the numbers, in English or German."""
    n, cut = case["n"], round(100 * case["cutoff"])
    if lang == "de":
        if case["same_decisions"]:
            return (
                f"In {n} historischen Strompreisfällen lösten beide Modelle bei einer "
                f"Alarmschwelle von {cut} % an denselben Tagen Alarm aus. "
                f"{case['false_alerts']} Alarme waren Fehlalarme."
            )
        return (
            f"In {n} historischen Strompreisfällen unterschieden sich die Alarme der beiden "
            f"Modelle an {case['differing_decisions']} Tagen (Alarmschwelle {cut} %)."
        )
    rows = {r["policy"]: r for r in case["rows"]}
    b, c = rows[case["baseline"]]["brier"], rows[case["candidate"]]["brier"]
    if case["same_decisions"]:
        return (
            f"In {n} historical German evening-price cases the base rate had the better Brier "
            f"score ({b:.4f} against {c:.4f}), yet both models triggered an alert on exactly the "
            f"same days at a {cut}% alert threshold; {case['false_alerts']} of those alerts "
            "were false. Lower Brier is better."
        )
    return (
        f"In {n} historical German evening-price cases the two models' alerts differed on "
        f"{case['differing_decisions']} days at a {cut}% alert threshold (Brier {b:.4f} for the "
        f"base rate, {c:.4f} for the model)."
    )


def _chart(sens: list[dict[str, Any]], narrow: bool) -> str:
    """Grouped bars of total loss per policy for each cost ratio; values are written on the bars."""
    w, h = CHART_NARROW if narrow else CHART_WIDE
    left, right, top, bottom = (36, 8, 26, 70) if narrow else (48, 12, 26, 56)
    pw, ph = w - left - right, h - top - bottom
    vmax = max(max(s["loss"][p] for p in CHART_POLICIES) for s in sens) or 1
    vmax = (int(vmax / 5) + 1) * 5
    gap = pw / len(sens)
    bw = min(40, gap / (len(CHART_POLICIES) + 1.2))
    sfx = "n" if narrow else "w"
    out = [
        f'<svg class="audit-chart audit-{"narrow" if narrow else "wide"}" viewBox="0 0 {w} {h}" '
        f'role="img" aria-labelledby="ac-t-{sfx} ac-d-{sfx}">',
        f'<title id="ac-t-{sfx}">Total loss by policy and cost ratio</title>',
        f'<desc id="ac-d-{sfx}">Grouped bars of the total illustrative loss of the base rate, the '
        "fine-tuned model and always alerting, for three ratios of the cost of a missed event to "
        "the cost of a false alert. The same numbers are in the table below.</desc>",
    ]
    for tick in range(0, vmax + 1, 5):
        y = top + ph - ph * tick / vmax
        out.append(f'<line class="grid" x1="{left}" x2="{w - right}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(
            f'<text class="tick" x="{left - 5}" y="{y + 4:.1f}" text-anchor="end">{tick}</text>'
        )
    for gi, s in enumerate(sens):
        gx = left + gap * gi + gap / 2 - bw * len(CHART_POLICIES) / 2
        for bi, pname in enumerate(CHART_POLICIES):
            v = s["loss"][pname]
            bh = ph * v / vmax
            x = gx + bw * bi
            out.append(
                f'<rect class="bar {CHART_CLASS[pname]}" x="{x:.1f}" y="{top + ph - bh:.1f}" '
                f'width="{bw - 3:.1f}" height="{bh:.1f}"><title>{escape(NAMES[pname])}: '
                f"{v:g}</title></rect>"
            )
            out.append(
                f'<text class="tick" x="{x + (bw - 3) / 2:.1f}" y="{top + ph - bh - 4:.1f}" '
                f'text-anchor="middle">{v:g}</text>'
            )
        label = f"{s['ratio']}"
        out.append(
            f'<text class="tick" x="{left + gap * gi + gap / 2:.1f}" y="{h - bottom + 18}" '
            f'text-anchor="middle">{escape(label)}</text>'
        )
    out.append(
        f'<text class="tick" x="{left + pw / 2:.1f}" y="{h - bottom + 36}" text-anchor="middle">'
        "false alert : missed event cost</text>"
    )
    out.append("</svg>")
    return "".join(out)


def lineage(rec: Any, question_id: str) -> dict[str, Any] | None:
    """What the public ledger recorded for one question: ML and persistence forecasts, any skip
    reason of the agents, and the outcome. None when the question is not in the ledger."""
    q = rec.questions.get(question_id)
    if q is None:
        return None
    forecasts = {f.forecaster_id: f for f in rec.forecasts if f.question_id == question_id}
    skips = {s.forecaster_id: s.reason_code for s in rec.skips if s.question_id == question_id}
    res = rec.resolutions.get(question_id)
    if res is None:
        return None
    return {
        "question_id": question_id,
        "text": q.text,
        "batch_date": q.batch_date.isoformat(),
        "target_date": q.target_date.isoformat(),
        "lock": q.lock_time.strftime("%Y-%m-%d %H:%M UTC"),
        "outcome": int(res.outcome),
        "ml": forecasts["ml"].probability if "ml" in forecasts else None,
        "persistence": forecasts["persistence"].probability if "persistence" in forecasts else None,
        "skips": skips,
    }
