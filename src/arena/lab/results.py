"""Result files of the experiments lab (SPEC 17): schema, loading and the budget total.

Every lab result is an evaluation, never part of the live record (rule L1). Result files live in
`evals/results/lab-<experiment>.json`; the LLM evals page skips them, the Lab page shows them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

BUDGET_LIMIT_USD = 2.00


class LabResult(BaseModel):
    """One experiment's result, as stored."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["evaluation"] = "evaluation"
    experiment: str
    title: str
    created_at: str
    why: str = Field(description="One line: why companies use this technique (with a source id).")
    prereg_sha256: str | None = None
    dataset_sha256: dict[str, str] = Field(default_factory=dict)
    artefacts: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, dict[str, float | int | str | None]] = Field(default_factory=dict)
    paired: list[dict[str, Any]] = Field(default_factory=list)
    cost_usd: float = 0.0
    notes: list[str] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list, description="What the result does not show.")
    card: str | None = None


#: Experiments that are planned and not yet run (shown as such, never with numbers).
PLANNED: tuple[tuple[str, str], ...] = (
    (
        "Second LLM judge (a different model) compared with the first (LLM against LLM, not human)",
        "approved 2026-11-23; one small paid run (about US$0.2, 30 items) follows the merge",
    ),
    (
        "Agreement of the LLM judge with human labels",
        "waits for the owner's 30 labels; until then the judge scores are an uncalibrated ranking",
    ),
    (
        "Cost routing with the simpler ml-first rule on fresh days",
        "a proposal only (found after the fact in the routing study); needs a new pre-registration",
    ),
    (
        "In-browser model tier for Ask the Arena",
        "optional; needs the owner's OK for a download of about 300 MB",
    ),
)


def load_lab_results(results_dir: Path | None) -> list[LabResult]:
    """Committed lab results, newest first; an invalid file raises (never hidden)."""
    if results_dir is None or not results_dir.is_dir():
        return []
    out = [
        LabResult.model_validate(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted(results_dir.glob("lab-*.json"))
    ]
    return sorted(out, key=lambda r: r.created_at, reverse=True)


def total_cost(results: list[LabResult]) -> float:
    """Sum of the paid-call cost of all lab results, in US dollars."""
    return round(sum(r.cost_usd for r in results), 6)


def check_budget(results: list[LabResult], limit: float = BUDGET_LIMIT_USD) -> float:
    """Return the total; raise if it is above the lab limit (rule L5)."""
    total = total_cost(results)
    if total > limit + 1e-9:
        raise ValueError(f"lab spend {total:.2f} USD is above the limit of {limit:.2f} USD")
    return total


#: Metric columns the Lab page can show, in order, with their headings.
COLUMNS: dict[str, str] = {
    "n": "Questions",
    "ndcg5": "nDCG@5",
    "mrr": "MRR",
    "p_at_5": "Precision@5",
    "brier": "Brier",
    "log_score": "Log score",
    "ece": "ECE",
    "flagged": "Flagged",
    "detected_pct": "Detected %",
    "false_positive_pct": "False positives %",
    "numbers": "Numbers checked",
    "months": "Months",
    "raw80": "80% band, raw",
    "conformal80": "80% band, conformal",
    "raw90": "90% band, raw",
    "conformal90": "90% band, conformal",
    "answerable": "Answerable questions",
    "hit_pct": "Hit %",
    "false_refusal_pct": "False refusals %",
    "no_invented_pct": "No invented numbers %",
    "weighted_kappa": "Weighted kappa",
    "exact_match_pct": "Exact match %",
    "out_of_scope": "Out of scope",
    "correct_refusal_pct": "Correct refusals %",
    "not_in_prompt_pct": "Numbers not in the prompt %",
    "rationales_with_not_in_prompt_pct": "Rationales with such a number %",
    "latency_ms_p50": "Latency p50 (ms)",
    "size_mb": "Size (MB)",
    "cost_usd_per_1k": "US$ per 1,000",
}


def lab_cards(results: list[LabResult]) -> list[dict[str, Any]]:
    """Result dictionaries for the page, each with the metric columns it actually has."""
    out = []
    for r in results:
        d = r.model_dump()
        d["cols"] = [c for c in COLUMNS if any(c in m for m in r.metrics.values())]
        out.append(d)
    return out


def card_markdown(r: LabResult) -> str:
    """The experiment card, generated from the result file (rule L7); every figure is copied."""
    cols = [c for c in COLUMNS if any(c in m for m in r.metrics.values())]
    lines = [
        f"# {r.title}",
        "",
        "**EVALUATION: an experiment of the lab, not the live record (SPEC 17).**",
        "",
        f"Result file: `evals/results/lab-{r.experiment}.json`, created {r.created_at}.",
        "",
        f"Why companies use it: {r.why}",
        "",
    ]
    if r.metrics:
        lines += ["| Variant | " + " | ".join(COLUMNS[c] for c in cols) + " |"]
        lines += ["|---|" + "---|" * len(cols)]
        for name, m in r.metrics.items():
            lines.append(f"| {name} | " + " | ".join(str(m.get(c, "-")) for c in cols) + " |")
        lines.append("")
    for p in r.paired:
        sig = "interval excludes zero" if p["lo"] > 0 or p["hi"] < 0 else "interval includes zero"
        lines.append(
            f"- {p['a']} minus {p['b']}: Brier difference {p['diff']:+.4f}, 95% interval "
            f"[{p['lo']:+.4f}, {p['hi']:+.4f}] over {p['n']} questions ({sig})."
        )
    lines += [""] + [f"- {n}" for n in r.notes]
    if r.limits:
        lines += ["", "## What this does and does not show", ""] + [f"- {x}" for x in r.limits]
    lines += ["", f"Paid-call cost: US${r.cost_usd:.2f}.", ""]
    return "\n".join(lines)
