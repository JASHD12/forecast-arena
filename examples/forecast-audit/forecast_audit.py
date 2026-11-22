"""Forecast audit: compare binary forecasts and the alert decisions they trigger, case by case.

Standard library only (Python 3.12): no packages, no network, no keys. Two CSV files go in, a JSON
report, an audited-cases CSV and a static HTML page come out. The contract is in SCHEMA.md.

The question it answers: "If I use my model's probabilities to send alerts, does that improve
decisions over a baseline, including the days my model has no on-time prediction?"

Rules (all stated in the report as well):
- A prediction is *on time* only if `issued_at` is strictly before the case's `lock_at`.
- Quality (Brier) is compared on identical cases: resolved, and on time for both models.
- An alert is sent when `p >= false_alert_cost / (false_alert_cost + miss_cost)` (ties alert).
- A late, skipped or absent prediction falls back to the `--on-missing` policy; the number of
  fallbacks is reported next to every loss.
- Invalid input stops with exit code 2 and a field/row message; nothing is written.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import random
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"
TOOL_VERSION = "0.1.0"
CASE_COLUMNS = ("case_id", "group_day", "lock_at", "outcome_state", "outcome")
PREDICTION_COLUMNS = ("case_id", "model_id", "status", "probability", "issued_at", "reason")
OUTCOME_STATES = ("resolved", "pending", "void")
STATUSES = ("forecast", "skipped")
TIMING_LABELS = ("declared", "replayed", "ledger-verified")
CLIP = (0.01, 0.99)  # the Arena scoring convention (src/arena/scoring/core.py)
SENSITIVITY_RATIOS = (1, 9)
MIN_DAYS_FOR_INTERVAL = 30
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261122


class InvalidInput(Exception):
    """One or more problems in the input files; `problems` holds one message per problem."""

    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


# ---- reading -------------------------------------------------------------------------------------


def _timestamp(value: str) -> datetime | None:
    """A timezone-aware ISO 8601 timestamp, or None (a naive time is refused: it has no meaning)."""
    try:
        t = datetime.fromisoformat(value)
    except ValueError:
        return None
    return t if t.tzinfo is not None and t.utcoffset() is not None else None


def _read_csv(
    path: Path, columns: tuple[str, ...], name: str, problems: list[str]
) -> list[dict[str, str]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        problems.append(f"{name}: cannot read {path} ({exc.strerror})")
        return []
    reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
    missing = [c for c in columns if c not in (reader.fieldnames or [])]
    if missing:
        problems.append(f"{name}: missing column(s) {', '.join(missing)}")
        return []
    rows = []
    for row in reader:
        rows.append({k: (v or "").strip() for k, v in row.items() if k is not None})
    return rows


def file_sha256(path: Path) -> str:
    """SHA-256 of an input file, recorded in the report."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cases(path: Path, problems: list[str]) -> dict[str, dict[str, Any]]:
    """The expected cases, keyed by `case_id`."""
    cases: dict[str, dict[str, Any]] = {}
    for n, row in enumerate(_read_csv(path, CASE_COLUMNS, "cases.csv", problems), start=2):
        where = f"cases.csv row {n}"
        cid = row["case_id"]
        if not cid:
            problems.append(f"{where}: field case_id is empty")
            continue
        if cid in cases:
            problems.append(f"{where}: field case_id {cid!r} is a duplicate")
            continue
        try:
            day = date.fromisoformat(row["group_day"])
        except ValueError:
            problems.append(f"{where}: field group_day {row['group_day']!r} is not YYYY-MM-DD")
            continue
        lock = _timestamp(row["lock_at"])
        if lock is None:
            problems.append(
                f"{where}: field lock_at {row['lock_at']!r} is not an ISO 8601 time "
                "with a UTC offset"
            )
            continue
        state = row["outcome_state"]
        if state not in OUTCOME_STATES:
            problems.append(
                f"{where}: field outcome_state {state!r} must be one of {', '.join(OUTCOME_STATES)}"
            )
            continue
        outcome: int | None = None
        if state == "resolved":
            if row["outcome"] not in ("0", "1"):
                problems.append(
                    f"{where}: field outcome {row['outcome']!r} must be 0 or 1 for a resolved case"
                )
                continue
            outcome = int(row["outcome"])
        elif row["outcome"]:
            problems.append(f"{where}: field outcome must be empty while outcome_state is {state}")
            continue
        cases[cid] = {
            "case_id": cid,
            "day": day,
            "lock_at": lock,
            "state": state,
            "outcome": outcome,
        }
    return cases


def load_predictions(
    path: Path, cases: dict[str, dict[str, Any]], problems: list[str]
) -> dict[tuple[str, str], dict[str, Any]]:
    """The submitted predictions, keyed by (`case_id`, `model_id`)."""
    preds: dict[tuple[str, str], dict[str, Any]] = {}
    for n, row in enumerate(
        _read_csv(path, PREDICTION_COLUMNS, "predictions.csv", problems), start=2
    ):
        where = f"predictions.csv row {n}"
        cid, mid = row["case_id"], row["model_id"]
        if not mid:
            problems.append(f"{where}: field model_id is empty")
            continue
        if cid not in cases:
            problems.append(f"{where}: field case_id {cid!r} is not in cases.csv")
            continue
        if (cid, mid) in preds:
            problems.append(f"{where}: ({cid!r}, {mid!r}) appears twice")
            continue
        status = row["status"]
        if status not in STATUSES:
            problems.append(
                f"{where}: field status {status!r} must be one of {', '.join(STATUSES)}"
            )
            continue
        if status == "skipped":
            if not row["reason"]:
                problems.append(f"{where}: a skipped prediction needs a reason")
                continue
            preds[(cid, mid)] = {
                "status": "skipped",
                "reason": row["reason"],
                "p": None,
                "issued": None,
            }
            continue
        try:
            p = float(row["probability"])
        except ValueError:
            problems.append(f"{where}: field probability {row['probability']!r} is not a number")
            continue
        if not math.isfinite(p) or not 0.0 <= p <= 1.0:
            problems.append(
                f"{where}: field probability {row['probability']!r} must be finite and in [0, 1]"
            )
            continue
        issued = _timestamp(row["issued_at"])
        if issued is None:
            problems.append(
                f"{where}: field issued_at {row['issued_at']!r} is not an ISO 8601 time "
                "with a UTC offset"
            )
            continue
        preds[(cid, mid)] = {
            "status": "forecast",
            "reason": row["reason"],
            "p": p,
            "issued": issued,
        }
    return preds


# ---- calculation ---------------------------------------------------------------------------------


def clipped(p: float) -> float:
    """Probability clipped like the Arena scoring code, so a certain wrong answer is finite."""
    return min(CLIP[1], max(CLIP[0], p))


def pair_state(pred: dict[str, Any] | None, case: dict[str, Any]) -> str:
    """on_time | late | skipped | absent for one (case, model)."""
    if pred is None:
        return "absent"
    if pred["status"] == "skipped":
        return "skipped"
    return "on_time" if pred["issued"] < case["lock_at"] else "late"


def brier(ps: list[float], ys: list[int], clip: bool = False) -> float | None:
    """Mean squared error of probabilities; None for an empty set."""
    if not ps:
        return None
    return sum(((clipped(p) if clip else p) - y) ** 2 for p, y in zip(ps, ys, strict=True)) / len(
        ps
    )


def alert_cutoff(false_alert_cost: float, miss_cost: float) -> float:
    """Alert when p >= this value (the cost-minimising rule when correct actions cost nothing)."""
    return false_alert_cost / (false_alert_cost + miss_cost)


def case_loss(alert: bool, outcome: int, false_alert_cost: float, miss_cost: float) -> float:
    """Loss of one decision: an unnecessary alert costs `false_alert_cost`, a miss `miss_cost`."""
    if alert and outcome == 0:
        return false_alert_cost
    if not alert and outcome == 1:
        return miss_cost
    return 0.0


def _decisions(
    cases: dict[str, dict[str, Any]],
    preds: dict[tuple[str, str], dict[str, Any]],
    model: str,
    baseline: str,
    cutoff: float,
    on_missing: str,
) -> dict[str, tuple[bool, bool]]:
    """{case_id: (alert, used_fallback)} for every resolved case under one model's policy."""
    out: dict[str, tuple[bool, bool]] = {}
    for cid, c in cases.items():
        if c["state"] != "resolved":
            continue
        if pair_state(preds.get((cid, model)), c) == "on_time":
            out[cid] = (preds[(cid, model)]["p"] >= cutoff, False)
            continue
        if on_missing == "alert":
            alert = True
        elif on_missing == "baseline" and pair_state(preds.get((cid, baseline)), c) == "on_time":
            alert = preds[(cid, baseline)]["p"] >= cutoff
        else:
            alert = False
        out[cid] = (alert, True)
    return out


def _policy_row(
    name: str,
    decisions: dict[str, tuple[bool, bool]],
    cases: dict[str, dict[str, Any]],
    fa: float,
    miss: float,
) -> dict[str, Any]:
    losses: dict[str, float] = {}
    false_alerts = misses = alerts = fallbacks = 0
    for cid, (alert, fell_back) in decisions.items():
        y = cases[cid]["outcome"]
        alerts += alert
        false_alerts += alert and y == 0
        misses += (not alert) and y == 1
        fallbacks += fell_back
        losses[cid] = case_loss(alert, y, fa, miss)
    by_day: dict[date, float] = defaultdict(float)
    for cid, loss in losses.items():
        by_day[cases[cid]["day"]] += loss
    n = len(losses)
    total = sum(losses.values())
    return {
        "policy": name,
        "cases": n,
        "days": len(by_day),
        "alerts": alerts,
        "false_alerts": false_alerts,
        "misses": misses,
        "fallback_used": fallbacks,
        "total_loss": total,
        "loss_per_case": None if n == 0 else total / n,
        "mean_daily_total_loss": None if not by_day else sum(by_day.values()) / len(by_day),
    }


def _bootstrap(diff_by_day: dict[date, float], block: int) -> dict[str, Any]:
    """Moving-block bootstrap of the mean daily loss difference (candidate - baseline)."""
    days = sorted(diff_by_day)
    if len(days) < MIN_DAYS_FOR_INTERVAL:
        return {
            "estimated": False,
            "reason": f"fewer than {MIN_DAYS_FOR_INTERVAL} resolved days ({len(days)})",
        }
    values = [diff_by_day[d] for d in days]
    rng = random.Random(BOOTSTRAP_SEED)
    starts = len(values) - block + 1
    means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample: list[float] = []
        while len(sample) < len(values):
            s = rng.randrange(starts)
            sample.extend(values[s : s + block])
        sample = sample[: len(values)]
        means.append(sum(sample) / len(sample))
    means.sort()
    return {
        "estimated": True,
        "block_days": block,
        "mean_difference": sum(values) / len(values),
        "low": means[int(0.025 * BOOTSTRAP_RESAMPLES)],
        "high": means[int(0.975 * BOOTSTRAP_RESAMPLES) - 1],
        "days": len(values),
        "note": "negative favours the candidate; days are serially correlated, "
        "so blocks are resampled",
    }


def audit(
    cases: dict[str, dict[str, Any]],
    preds: dict[tuple[str, str], dict[str, Any]],
    candidate: str,
    baseline: str,
    false_alert_cost: float,
    miss_cost: float,
    on_missing: str = "no-alert",
    timing_label: str = "declared",
    roster_known: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The report (JSON-ready) and the audited (case, model) rows."""
    models = sorted({m for _, m in preds} | {candidate, baseline})
    cutoff = alert_cutoff(false_alert_cost, miss_cost)
    days = sorted({c["day"] for c in cases.values()})
    states = {s: sum(c["state"] == s for c in cases.values()) for s in OUTCOME_STATES}

    coverage: dict[str, Any] = {}
    for m in models:
        counts = {"on_time": 0, "late": 0, "skipped": 0, "absent": 0}
        for cid, c in cases.items():
            counts[pair_state(preds.get((cid, m)), c)] += 1
        if not roster_known:
            counts["absent"] = None  # type: ignore[assignment]  # nobody knows what was expected
        coverage[m] = {"scheduled": len(cases) if roster_known else None, **counts}

    shared = [
        cid
        for cid, c in cases.items()
        if c["state"] == "resolved"
        and pair_state(preds.get((cid, candidate)), c) == "on_time"
        and pair_state(preds.get((cid, baseline)), c) == "on_time"
    ]
    ys = [cases[cid]["outcome"] for cid in shared]
    quality: dict[str, Any] = {"shared_cases": len(shared), "models": {}}
    for m in (candidate, baseline):
        ps = [preds[(cid, m)]["p"] for cid in shared]
        quality["models"][m] = {
            "brier": brier(ps, ys),
            "brier_clipped": brier(ps, ys, clip=True),
        }
    own: dict[str, Any] = {}
    for m in models:
        ids = [
            cid
            for cid, c in cases.items()
            if c["state"] == "resolved" and pair_state(preds.get((cid, m)), c) == "on_time"
        ]
        own[m] = {
            "cases": len(ids),
            "brier": brier(
                [preds[(cid, m)]["p"] for cid in ids], [cases[cid]["outcome"] for cid in ids]
            ),
        }
    quality["own_cases_not_comparable"] = own

    def decision(fa: float, miss: float) -> dict[str, Any]:
        cut = alert_cutoff(fa, miss)
        resolved = [cid for cid, c in cases.items() if c["state"] == "resolved"]
        rows = []
        for m in (candidate, baseline):
            rows.append(
                _policy_row(
                    m, _decisions(cases, preds, m, baseline, cut, on_missing), cases, fa, miss
                )
            )
        rows.append(
            _policy_row("always_alert", {cid: (True, False) for cid in resolved}, cases, fa, miss)
        )
        rows.append(
            _policy_row("never_alert", {cid: (False, False) for cid in resolved}, cases, fa, miss)
        )
        return {
            "false_alert_cost": fa,
            "miss_cost": miss,
            "cutoff": cut,
            "policies": rows,
        }

    primary = decision(false_alert_cost, miss_cost)
    sensitivity = []
    for ratio in SENSITIVITY_RATIOS:
        if ratio * false_alert_cost != miss_cost:
            sensitivity.append(decision(false_alert_cost, ratio * false_alert_cost))

    dec_c = _decisions(cases, preds, candidate, baseline, cutoff, on_missing)
    dec_b = _decisions(cases, preds, baseline, baseline, cutoff, on_missing)
    diff: dict[date, float] = defaultdict(float)
    for cid in dec_c:
        y = cases[cid]["outcome"]
        d = case_loss(dec_c[cid][0], y, false_alert_cost, miss_cost) - case_loss(
            dec_b[cid][0], y, false_alert_cost, miss_cost
        )
        diff[cases[cid]["day"]] += d
    intervals = {"day_block": _bootstrap(diff, 1)}
    if len(diff) >= 2 * MIN_DAYS_FOR_INTERVAL:
        intervals["moving_week"] = _bootstrap(diff, 7)

    rows_out: list[dict[str, Any]] = []
    for cid, c in cases.items():
        for m in (candidate, baseline):
            pred = preds.get((cid, m))
            st = pair_state(pred, c)
            other = baseline if m == candidate else candidate
            other_ok = pair_state(preds.get((cid, other)), c) == "on_time"
            if c["state"] != "resolved":
                q_reason, d_reason = f"case {c['state']}", f"case {c['state']}"
                in_q = in_d = "no"
            else:
                in_d = "yes"
                d_reason = (
                    "resolved" if st == "on_time" else f"prediction {st}: fallback {on_missing}"
                )
                if st != "on_time":
                    in_q, q_reason = "no", f"prediction {st}"
                elif not other_ok:
                    in_q, q_reason = "no", "other model has no on-time prediction"
                else:
                    in_q, q_reason = "yes", "shared on-time resolved case"
            alert = loss = ""
            if c["state"] == "resolved":
                a = (dec_c if m == candidate else dec_b)[cid][0]
                alert = "yes" if a else "no"
                loss = f"{case_loss(a, c['outcome'], false_alert_cost, miss_cost):g}"
            rows_out.append(
                {
                    "case_id": cid,
                    "group_day": c["day"].isoformat(),
                    "model_id": m,
                    "outcome_state": c["state"],
                    "outcome": "" if c["outcome"] is None else c["outcome"],
                    "prediction_state": st,
                    "probability": "" if not pred or pred["p"] is None else f"{pred['p']:g}",
                    "included_in_quality": in_q,
                    "quality_reason": q_reason,
                    "included_in_decision": in_d,
                    "decision_reason": d_reason,
                    "alert": alert,
                    "loss": loss,
                }
            )

    report = {
        "schema_version": SCHEMA_VERSION,
        "tool_version": TOOL_VERSION,
        "timing_label": timing_label,
        "timing_note": {
            "declared": "issue times are as supplied in the file; the file cannot prove them",
            "replayed": "a historical replay: probabilities were computed after the fact from data "
            "available at the as-of time",
            "ledger-verified": "issue times were checked against a sealed public ledger",
        }[timing_label],
        "time_scope": {
            "first_day": days[0].isoformat() if days else None,
            "last_day": days[-1].isoformat() if days else None,
            "days": len(days),
            "cases": len(cases),
        },
        "roster": "known" if roster_known else "unknown",
        "case_states": states,
        "models": models,
        "candidate": candidate,
        "baseline": baseline,
        "rule": {
            "on_time": "issued_at strictly before lock_at (equality is late)",
            "alert": "p >= false_alert_cost / (false_alert_cost + miss_cost); ties alert",
            "on_missing": on_missing,
            "brier_clip": list(CLIP),
        },
        "units": "arbitrary loss units: an unnecessary alert costs false_alert_cost, "
        "a miss miss_cost, "
        "correct actions cost 0",
        "coverage": coverage,
        "quality": quality,
        "decision": primary,
        "sensitivity": sensitivity,
        "intervals": intervals,
    }
    return report, rows_out


# ---- writing -------------------------------------------------------------------------------------


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None:
        return "undefined"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def _table(caption: str, head: list[str], body: list[list[Any]]) -> str:
    th = "".join(f"<th scope='col'>{html.escape(h)}</th>" for h in head)
    rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(_fmt(c))}</td>" for c in r) + "</tr>" for r in body
    )
    return (
        f"<table><caption>{html.escape(caption)}</caption><thead><tr>{th}</tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def render_html(report: dict[str, Any], inputs: dict[str, str]) -> str:
    """A static, accessible page; every value from the input files is escaped."""
    c, b = report["candidate"], report["baseline"]
    dec = report["decision"]
    q = report["quality"]
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Forecast audit report</title>",
        "<style>body{font:16px/1.5 system-ui,sans-serif;max-width:60rem;margin:1rem auto;"
        "padding:0 1rem}"
        "table{border-collapse:collapse;margin:1rem 0;width:100%}"
        "caption{text-align:left;font-weight:600;padding:.25rem 0}"
        "th,td{border:1px solid #8888;padding:.3rem .5rem;text-align:left}"
        "@media (max-width:40rem){table{display:block;overflow-x:auto}}</style></head><body><main>",
        f"<h1>Forecast audit: {html.escape(c)} against {html.escape(b)}</h1>",
        f"<p><strong>Timing label: {html.escape(report['timing_label'])}.</strong> "
        f"{html.escape(report['timing_note'])}.</p>",
        f"<p>{report['time_scope']['cases']} cases on {report['time_scope']['days']} days "
        f"({html.escape(str(report['time_scope']['first_day']))} to "
        f"{html.escape(str(report['time_scope']['last_day']))}); "
        f"roster {html.escape(report['roster'])}. "
        f"Cutoff: alert when probability is at least {dec['cutoff']:.4f} "
        f"(false alert costs {dec['false_alert_cost']:g}, a miss {dec['miss_cost']:g}; "
        f"missing predictions: {html.escape(report['rule']['on_missing'])}).</p>",
        "<h2>1. Timeliness and coverage</h2>",
        _table(
            "Predictions per model",
            ["model", "scheduled", "on time", "late", "skipped", "absent"],
            [
                [m, v["scheduled"], v["on_time"], v["late"], v["skipped"], v["absent"]]
                for m, v in report["coverage"].items()
            ],
        ),
        f"<p>Cases: {report['case_states']['resolved']} resolved, "
        f"{report['case_states']['pending']} "
        f"pending, {report['case_states']['void']} void "
        "(pending and void cases are not scored).</p>",
        "<h2>2. Probability quality (identical cases only)</h2>",
        f"<p>Shared on-time resolved cases: {q['shared_cases']}. Lower Brier is better.</p>",
        _table(
            "Brier score on the shared cases",
            ["model", "Brier (raw)", "Brier (clipped to 0.01..0.99)"],
            [[m, v["brier"], v["brier_clipped"]] for m, v in q["models"].items()],
        ),
        "<h2>3. Decision performance</h2>",
        _table(
            "Alerts and loss over all resolved cases",
            [
                "policy",
                "cases",
                "alerts",
                "false alerts",
                "misses",
                "fallbacks used",
                "total loss",
                "loss per case",
                "mean daily total loss",
            ],
            [
                [
                    p["policy"],
                    p["cases"],
                    p["alerts"],
                    p["false_alerts"],
                    p["misses"],
                    p["fallback_used"],
                    p["total_loss"],
                    p["loss_per_case"],
                    p["mean_daily_total_loss"],
                ]
                for p in dec["policies"]
            ],
        ),
    ]
    for s in report["sensitivity"]:
        parts.append(
            _table(
                f"Sensitivity: false alert {s['false_alert_cost']:g}, miss {s['miss_cost']:g} "
                f"(cutoff {s['cutoff']:.4f})",
                ["policy", "alerts", "false alerts", "misses", "total loss", "loss per case"],
                [
                    [
                        p["policy"],
                        p["alerts"],
                        p["false_alerts"],
                        p["misses"],
                        p["total_loss"],
                        p["loss_per_case"],
                    ]
                    for p in s["policies"]
                ],
            )
        )
    for name, iv in report["intervals"].items():
        if iv["estimated"]:
            parts.append(
                f"<p>{html.escape(name)} bootstrap of the mean daily loss difference "
                f"({html.escape(c)} minus {html.escape(b)}): {iv['mean_difference']:.4f}, "
                f"95% interval {iv['low']:.4f} to {iv['high']:.4f} over {iv['days']} days.</p>"
            )
        else:
            parts.append(
                f"<p>{html.escape(name)} interval not estimated: {html.escape(iv['reason'])}.</p>"
            )
    parts.append(
        "<h2>Inputs</h2><p>"
        + "; ".join(f"{html.escape(k)} SHA-256 {html.escape(v)}" for k, v in inputs.items())
        + f". Tool version {TOOL_VERSION}, schema {SCHEMA_VERSION}.</p>"
    )
    parts.append("</main></body></html>")
    return "".join(parts)


def write_outputs(
    out: Path, report: dict[str, Any], rows: list[dict[str, Any]], inputs: dict[str, str]
) -> None:
    """Write report.json, cases-audited.csv and report.html (after a successful audit only)."""
    out.mkdir(parents=True, exist_ok=True)
    report = {**report, "inputs": inputs}
    (out / "report.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (out / "cases-audited.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=list(rows[0]) if rows else ["case_id"], lineterminator="\n"
        )
        w.writeheader()
        w.writerows(rows)
    (out / "report.html").write_text(render_html(report, inputs), encoding="utf-8")


# ---- command line --------------------------------------------------------------------------------


def run(
    cases_path: Path,
    predictions_path: Path,
    candidate: str,
    baseline: str,
    false_alert_cost: float,
    miss_cost: float,
    on_missing: str = "no-alert",
    timing_label: str = "declared",
    roster_known: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    """Read, validate and audit; raises `InvalidInput` listing every problem found."""
    problems: list[str] = []
    if not (math.isfinite(false_alert_cost) and false_alert_cost > 0):
        problems.append("--false-alert-cost must be a positive number")
    if not (math.isfinite(miss_cost) and miss_cost > 0):
        problems.append("--miss-cost must be a positive number")
    cases = load_cases(cases_path, problems)
    preds = load_predictions(predictions_path, cases, problems)
    known = {m for _, m in preds}
    for role, m in (("candidate", candidate), ("baseline", baseline)):
        if m not in known and not problems:
            problems.append(
                f"{role} model {m!r} has no row in predictions.csv "
                f"(models: {', '.join(sorted(known))})"
            )
    if not cases and not problems:
        problems.append("cases.csv has no rows")
    if problems:
        raise InvalidInput(problems)
    inputs = {
        "cases.csv": file_sha256(cases_path),
        "predictions.csv": file_sha256(predictions_path),
    }
    report, rows = audit(
        cases,
        preds,
        candidate,
        baseline,
        false_alert_cost,
        miss_cost,
        on_missing,
        timing_label,
        roster_known,
    )
    return report, rows, inputs


def main(argv: list[str] | None = None) -> int:
    """Command line entry point; exit 0 on success, 2 on invalid input."""
    ap = argparse.ArgumentParser(prog="report.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--cases", type=Path, required=True)
    ap.add_argument("--predictions", type=Path, required=True)
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--false-alert-cost", type=float, default=1.0)
    ap.add_argument("--miss-cost", type=float, default=4.0)
    ap.add_argument("--on-missing", choices=("no-alert", "alert", "baseline"), default="no-alert")
    ap.add_argument("--timing-label", choices=TIMING_LABELS, default="declared")
    ap.add_argument("--roster", choices=("known", "unknown"), default="known")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        report, rows, inputs = run(
            args.cases,
            args.predictions,
            args.candidate,
            args.baseline,
            args.false_alert_cost,
            args.miss_cost,
            args.on_missing,
            args.timing_label,
            args.roster == "known",
        )
    except InvalidInput as exc:
        for p in exc.problems:
            print(f"error: {p}", file=sys.stderr)
        print(f"error: {len(exc.problems)} problem(s); no report written", file=sys.stderr)
        return 2
    write_outputs(args.out, report, rows, inputs)
    dec = {p["policy"]: p for p in report["decision"]["policies"]}
    print(f"cases {report['time_scope']['cases']}, shared {report['quality']['shared_cases']}")
    for name in (args.candidate, args.baseline, "always_alert", "never_alert"):
        p = dec[name]
        print(
            f"{name}: loss per case {_fmt(p['loss_per_case'], 4)}, alerts {p['alerts']}, "
            f"misses {p['misses']}"
        )
    print(f"report written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
