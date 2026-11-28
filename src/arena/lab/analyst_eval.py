"""Lab result of `agent_analyst` and the calibrated `llm_context` (T381, T382).

Pre-registered in `lab/prereg/analyst-and-calibration.md` before any paid run and before the map
was fitted. One result from three stored eval files: the November run (arms `agent_analyst` and raw
`llm_context`), the October run (raw `llm_context`, a second test of the map) and the earlier
November run whose `agent` arm is reused (same golden file, hash checked). The calibrated arm is
the raw answers through the fixed logit map (`forecasters/llm_context_cal.py`), computed here
offline, no tokens. `ml` is the replayed probabilities of `evals/golden/ml-probs-*.json`
(walk-forward replay, not the live model). Every number is computed from the stored files (I5).
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arena.forecasters.llm_context_cal import CalMap
from arena.lab.results import LabResult
from arena.scoring.core import brier, log_score
from arena.scoring.stats import expected_calibration_error, paired_brier_difference

PREREG = "lab/prereg/analyst-and-calibration.md"
SKILLS_R1_COST_PER_1K = "agent_skills / eval"  # metric row of lab-agent-skills.json (H-A3)


def _rows(res: Mapping[str, Any], arm: str) -> dict[str, dict[str, Any]]:
    return {
        r["question_id"]: r
        for r in res["rows"]
        if r["variant"] == arm and r["probability"] is not None
    }


def _arm_metrics(res: Mapping[str, Any], arm: str) -> dict[str, float | int | str | None]:
    m = res["metrics"][arm]
    n = m["n"]
    per_q = None if not m.get("cost_usd") else float(m["cost_usd"]) / n
    ans = m["answered"]
    return {
        "n": ans,
        "asked": n,
        "brier": round(m["brier"], 4),
        "log_score": round(m["log_score"], 4),
        "ece": None if m.get("ece") is None else round(m["ece"], 4),
        "cost_usd_per_1k": None if per_q is None else round(1000 * per_q, 4),
        "cost_usd_per_1k_answered": (
            None
            if not m.get("cost_usd") or not ans
            else round(1000 * float(m["cost_usd"]) / ans, 4)
        ),
    }


def _scored(
    arms: Mapping[str, Mapping[str, float]], rows: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    """Brier, log score and ECE of probability maps keyed by question id, on shared questions."""
    qids = sorted(set.intersection(*(set(p) for p in arms.values())))
    y = [rows[q]["outcome"] for q in qids]
    return {
        "qids": qids,
        "y": y,
        "days": [rows[q]["day"] for q in qids],
        "p": {a: [p[q] for q in qids] for a, p in arms.items()},
    }


def _pair(s: Mapping[str, Any], a: str, b: str, split: str) -> dict[str, Any]:
    d = paired_brier_difference(s["days"], s["p"][a], s["p"][b], s["y"])
    return {
        "a": a,
        "b": b,
        "split": split,
        "diff": round(d.estimate, 4),
        "lo": round(d.low, 4),
        "hi": round(d.high, 4),
        "n": d.n,
        "days": d.days,
    }


def _plain_row(p: Sequence[float], y: Sequence[int]) -> dict[str, float | int | str | None]:
    return {
        "n": len(y),
        "brier": round(brier(p, y), 4),
        "log_score": round(log_score(p, y), 4),
        "ece": round(expected_calibration_error(p, y), 4),
    }


def _check_golden(ml: Mapping[str, Any], res: Mapping[str, Any]) -> dict[str, float]:
    if ml["golden_sha256"] != res["golden_sha256"]:
        raise ValueError("the replayed ml probabilities were built for another golden file")
    return {k: float(v) for k, v in ml["probabilities"].items()}


def build(
    nov: Mapping[str, Any],
    oct_: Mapping[str, Any],
    reference: Mapping[str, Any],
    ml_nov: Mapping[str, Any],
    ml_oct: Mapping[str, Any],
    cal: CalMap,
    skills_r1_cost_per_1k_answered: float,
    *,
    prereg_path: Path = Path(PREREG),
) -> LabResult:
    """The `LabResult` of the analyst and calibration experiment."""
    if nov["golden_sha256"] != reference["golden_sha256"]:
        raise ValueError("the reference run used another golden file")
    ml_n, ml_o = _check_golden(ml_nov, nov), _check_golden(ml_oct, oct_)
    rows_n = _rows(nov, "llm_context")
    rows_o = _rows(oct_, "llm_context")
    analyst = _rows(nov, "agent_analyst")
    agent = _rows(reference, "agent")
    raw_n = {q: r["probability"] for q, r in rows_n.items()}
    raw_o = {q: r["probability"] for q, r in rows_o.items()}
    cal_n = {q: cal.apply(p) for q, p in raw_n.items()}
    cal_o = {q: cal.apply(p) for q, p in raw_o.items()}
    s_n = _scored(
        {
            "agent_analyst": {q: r["probability"] for q, r in analyst.items()},
            "llm_context": raw_n,
            "llm_context_cal": cal_n,
            "ml": ml_n,
            "agent": {q: r["probability"] for q, r in agent.items()},
        },
        rows_n,
    )
    s_o = _scored({"llm_context": raw_o, "llm_context_cal": cal_o, "ml": ml_o}, rows_o)
    metrics: dict[str, dict[str, float | int | str | None]] = {
        "agent_analyst / November": _arm_metrics(nov, "agent_analyst"),
        "llm_context (raw) / November": _arm_metrics(nov, "llm_context"),
        "llm_context_cal (map, no tokens) / November": _plain_row(
            s_n["p"]["llm_context_cal"], s_n["y"]
        ),
        "ml (replayed) / November": _plain_row(s_n["p"]["ml"], s_n["y"]),
        "agent (reused run) / November": _plain_row(s_n["p"]["agent"], s_n["y"]),
        "base_rate / November": {
            "n": nov["metrics"]["llm_context"]["answered"],
            "brier": round(nov["metrics"]["llm_context"]["base_rate_brier_same_items"], 4),
        },
        "llm_context (raw) / October": _arm_metrics(oct_, "llm_context"),
        "llm_context_cal (map, no tokens) / October": _plain_row(
            s_o["p"]["llm_context_cal"], s_o["y"]
        ),
        "ml (replayed) / October": _plain_row(s_o["p"]["ml"], s_o["y"]),
        "base_rate / October": {
            "n": oct_["metrics"]["llm_context"]["answered"],
            "brier": round(oct_["metrics"]["llm_context"]["base_rate_brier_same_items"], 4),
        },
    }
    paired = [
        _pair(s_n, "agent_analyst", "ml", "November"),
        _pair(s_n, "agent_analyst", "agent", "November"),
        _pair(s_n, "agent_analyst", "llm_context", "November"),
        _pair(s_n, "llm_context_cal", "llm_context", "November"),
        _pair(s_o, "llm_context_cal", "llm_context", "October"),
    ]
    cost = round(
        sum(m.get("cost_usd") or 0.0 for res in (nov, oct_) for m in res["metrics"].values()), 6
    )
    return LabResult(
        experiment="analyst-and-calibration",
        title="agent_analyst (starts from the ml forecast) and a calibrated llm_context",
        created_at=nov["created_at"],
        why="Starting an LLM from the classical model's forecast and recalibrating a hedging "
        "model's probabilities are the two cheapest ways companies try to make an LLM "
        "forecaster competitive. (anthropic-evals)",
        prereg_sha256=hashlib.sha256(prereg_path.read_bytes()).hexdigest(),
        dataset_sha256={
            "november": nov["golden_sha256"],
            "october": oct_["golden_sha256"],
            "ml_probs_november": hashlib.sha256(
                Path("evals/golden/ml-probs-power-11a.json").read_bytes()
            ).hexdigest(),
            "ml_probs_october": hashlib.sha256(
                Path("evals/golden/ml-probs-power.json").read_bytes()
            ).hexdigest(),
            "calibration_labels": cal.labels_sha256,
            "calibration_train": cal.train_sha256,
        },
        artefacts={
            "eval_run_november": nov["run_id"],
            "eval_run_october": oct_["run_id"],
            "agent_arm_reused_from": reference["run_id"],
            "calibration_map": f"a={cal.a}, b={cal.b}, n_train={cal.n_train}",
            "skills_r1_cost_per_1k_answered": f"{skills_r1_cost_per_1k_answered}",
        },
        metrics=metrics,
        paired=paired,
        cost_usd=cost,
        notes=[
            f"November: run {nov['run_id']} of llm-eval.yml on {nov['golden']} "
            f"({nov['n_items']} questions); October: run {oct_['run_id']} on {oct_['golden']} "
            f"({oct_['n_items']} questions). The agent arm is reused from run "
            f"{reference['run_id']} (same golden file, hash checked).",
            "`ml` is the replayed walk-forward probability of the production power model "
            "(`evals/golden/ml-probs-*.json`), not the live forecaster. `llm_context_cal` is the "
            "raw answers through the fixed map fitted once on lab training questions of 2019 to "
            "June 2026; none of the November or October questions is in that training set.",
            f"Versions: agent_analyst `{nov['versions']['agent_analyst']}`; "
            f"llm_context `{nov['versions']['llm_context']}`.",
            "Paired differences are Brier(first) minus Brier(second) with day-block 95% "
            "intervals on the questions both answered; negative means the first is better.",
        ],
        limits=[
            "Electricity only (the one topic a replay can reproduce), 90 and 186 questions from "
            "15 and 31 days; the six questions of a day are correlated, so intervals are "
            "day-block intervals.",
            "One run, one sample of the model's answers; a repeat could differ. The November set "
            "had been used before for other arms (three comparisons here, no multiplicity "
            "correction).",
            "Replayed `ml`, not the live model; weather, Wikipedia, currencies and crypto are "
            "judged only on live days.",
        ],
        card="docs/lab/analyst-and-calibration.md",
    )


def verdicts(r: LabResult) -> list[dict[str, Any]]:
    """The pre-registered rules applied to the stored numbers: name, passed, sentence."""

    def pair(a: str, b: str, split: str) -> dict[str, Any]:
        return next(p for p in r.paired if (p["a"], p["b"], p["split"]) == (a, b, split))

    def interval(p: Mapping[str, Any]) -> str:
        return f"{p['diff']:+.4f} (95% day-block interval {p['lo']:+.4f} to {p['hi']:+.4f})"

    out: list[dict[str, Any]] = []
    p = pair("agent_analyst", "ml", "November")
    out.append(
        {
            "rule": "H-A1",
            "passed": not p["lo"] > 0,
            "text": f"agent_analyst minus ml {interval(p)}; the rule needs the interval not "
            "entirely above zero" + ("; it is entirely below zero." if p["hi"] < 0 else "."),
        }
    )
    p = pair("agent_analyst", "agent", "November")
    out.append(
        {
            "rule": "H-A2",
            "passed": bool(p["hi"] < 0),
            "text": f"agent_analyst minus agent {interval(p)}; the rule needs the whole "
            "interval below zero.",
        }
    )
    a = r.metrics["agent_analyst / November"]["cost_usd_per_1k_answered"]
    ref = float(r.artefacts["skills_r1_cost_per_1k_answered"])
    out.append(
        {
            "rule": "H-A3",
            "passed": a is not None and float(a) < ref,
            "text": f"agent_analyst costs US$ {a} per 1,000 answered questions against {ref} "
            "for agent_skills r1.",
        }
    )
    p = pair("llm_context_cal", "llm_context", "November")
    out.append(
        {
            "rule": "H-C1",
            "passed": bool(p["hi"] < 0),
            "text": f"llm_context_cal minus llm_context {interval(p)}; the rule needs the "
            "whole interval below zero.",
        }
    )
    p = pair("llm_context_cal", "llm_context", "October")
    out.append(
        {
            "rule": "H-C1 (second test, October)",
            "passed": bool(p["hi"] < 0),
            "text": f"llm_context_cal minus llm_context on the October questions {interval(p)}.",
        }
    )
    return out
