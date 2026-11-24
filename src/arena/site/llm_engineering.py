# ruff: noqa: E501
"""The "What I measured about LLMs" page (T325): every figure is read from the committed result files.

Sources: `evals/results/lab-*.json` (the lab experiments), the self-consistency eval file and the
cost table of `docs/project/LAB_BUDGET.md`. Sentences are assembled from those numbers (I5); the only
typed text is the one-line decision per experiment, which contains no figures.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from markupsafe import Markup, escape

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS = ROOT / "evals" / "results"
DEFAULT_BUDGET = ROOT / "docs" / "project" / "LAB_BUDGET.md"
SC_FILE = "eval-20261122T212735.json"

#: One typed line per experiment: what was decided. No figures in it.
DECISIONS = {
    "qlora": "Kept as an experiment only; it runs live as an experimental forecaster, outside the headline.",
    "dpo": "Not used live: it adds nothing over plain fine-tuning.",
    "distill": "Not used live: the cheap student gives up almost all of the teacher's gain.",
    "prompt": "The live prompt is unchanged; a better prompt does not rescue a small model.",
    "routing": "The pre-registered cascade was not built. The simpler ml-first rule is only a hypothesis, pre-registered for fresh days.",
    "selfcons": "Not added to any forecaster: more cost, no gain.",
    "judge": "Used as a ranking only; agreement with a human waits for the owner's labels.",
    "arena": "Shipped: refusals and lookups are rule-based, so nothing can be invented.",
}
NEXT = (
    "Replicate the routing result on fresh live days before any change (pre-registered, evaluated after 24 December).",
    "Calibrate the judge against the owner's 30 human labels and report the agreement honestly.",
    "Try a larger teacher-label set or a larger student only as a new pre-registered experiment.",
)
GROUP = {
    "ml": "s-1",
    "claude_teacher": "s-3",
    "base_rate": "s-ref",
}  # the rest are small open models
GROUP_NAMES = {
    "s-1": "classical ML",
    "s-3": "paid LLM (Claude)",
    "s-ref": "reference",
    "s-5": "small open model",
}


def _load(results_dir: Path, name: str) -> dict[str, Any] | None:
    path = results_dir / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _m(d: dict[str, Any] | None, key: str, field: str = "brier") -> float | None:
    if not d:
        return None
    v = d.get("metrics", {}).get(key)
    return None if v is None or v.get(field) is None else float(v[field])


def budget_costs(path: Path = DEFAULT_BUDGET) -> dict[str, float]:
    """US$ per paid-run family, summed from the LAB_BUDGET table by a keyword of the run name."""
    keys = {
        "judge": "lab-judge", "routing": "lab-routing", "selfcons": "self-consistency",
        "distill": "lab-distill-labels",
    }  # fmt: skip
    out = dict.fromkeys(keys, 0.0)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 6 or not re.fullmatch(r"\d+\.\d+", cells[4]):
            continue
        for fam, kw in keys.items():
            if kw in cells[0]:
                out[fam] += float(cells[4])
    return out


def _pct(x: float) -> str:
    return f"{x:.1f}%"


def _rows(res: Path, cost: dict[str, float]) -> list[dict[str, Any]]:
    q, dpo, ds = (
        _load(res, "lab-qlora-r1.json"),
        _load(res, "lab-dpo-r1.json"),
        _load(res, "lab-distill-r1.json"),
    )
    po, rt = _load(res, "lab-prompt-opt.json"), _load(res, "lab-routing.json")
    jl, ar, sc = (
        _load(res, "lab-judge-llm.json"),
        _load(res, "lab-ask-arena.json"),
        _load(res, SC_FILE),
    )
    rows: list[dict[str, Any]] = []

    def add(key: str, title: str, result: str | None, usd: float | None) -> None:
        if result:
            rows.append(
                {
                    "key": key,
                    "title": title,
                    "result": result,
                    "cost": usd,
                    "decision": DECISIONS[key],
                }
            )

    t = "test_all"
    base, ml, ub, qb = (_m(q, f"{k} / {t}") for k in ("base_rate", "ml", "base_1_5b", "qlora_1_5b"))
    if None not in (base, ml, ub, qb):
        add("qlora", "QLoRA fine-tune of a 1.5B open model",
            f"Brier {qb:.4f}, against {ub:.4f} untuned, {base:.4f} for the base rate and {ml:.4f} for the ML model (276 test questions; lower is better).", 0.0)  # fmt: skip
    d = _m(dpo, f"dpo_1_5b / {t}")
    if d is not None and qb is not None and base is not None:
        add("dpo", "DPO preference tuning on top", f"Brier {d:.4f}, against {qb:.4f} for plain QLoRA and {base:.4f} for the base rate.", 0.0)  # fmt: skip
    st, te = _m(ds, f"distill_1_5b / {t}"), _m(ds, f"claude_teacher / {t}")
    if None not in (st, te, qb, base):
        add("distill", "Distillation from Claude into the 1.5B model",
            f"Student {st:.4f}, teacher (Claude) {te:.4f}, hard-label QLoRA {qb:.4f}, base rate {base:.4f}.", cost.get("distill", 0.0))  # fmt: skip
    pb, pw = _m(po, f"baseline / {t}"), _m(po, f"winner / {t}")
    if None not in (pb, pw, base):
        add("prompt", "Prompt optimisation for the free local model",
            f"Best of the searched prompts {pw:.4f}, against {pb:.4f} for the live prompt; base rate {base:.4f}.", 0.0)  # fmt: skip
    if rt:
        met = rt["metrics"]
        pair = next((v for k, v in met.items() if k.startswith("router (primary")), None)
        ml15 = met.get("curve / ml_only delta 0.15")
        if pair and ml15:
            avoided = 100 * (1 - pair["paid_calls"] / pair["n"])
            add("routing", "Cost routing between cheap and paid forecasters",
                f"The pre-registered rule avoided {_pct(avoided)} of the paid calls. A simpler ml-first rule, chosen after the fact, avoids {_pct(ml15['avoided_pct'])} at Brier {ml15['brier']:.4f} (Claude alone {_m(rt, 'claude (llm_context)'):.4f}).", cost.get("routing", 0.0))  # fmt: skip
    if sc:
        a, b = sc["metrics"].get("llm_context"), sc["metrics"].get("llm_context_sc5")
        if a and b:
            add("selfcons", "Self-consistency (five samples averaged)",
                f"Brier {b['brier']:.4f} against {a['brier']:.4f} for one call, at {b['cost_usd'] / a['cost_usd']:.1f} times the cost.", cost.get("selfcons", 0.0))  # fmt: skip
    if jl:
        k = {
            n: jl["metrics"].get(f"agreement / {n}", {}).get("weighted_kappa")
            for n in ("data_use", "direction", "hedging")
        }
        if all(v is not None for v in k.values()):
            add("judge", "LLM-as-judge on 100 stored rationales",
                f"Two judge models agree at weighted kappa {k['data_use']:.2f} (data use), {k['direction']:.2f} (direction) and {k['hedging']:.2f} (hedging) on 30 items; this is not agreement with a human.", cost.get("judge", 0.0) + float(jl.get("cost_usd") or 0))  # fmt: skip
    if ar:
        m = ar["metrics"]
        ref = m.get("finance and personal refusals", {}).get("correct_refusal_pct")
        inv = m.get("all answers", {}).get("no_invented_pct")
        if ref is not None and inv is not None:
            add("arena", "Ask the Arena: refusals and grounding", f"On the golden questions {ref}% of stock, advice and personal-data questions were refused and {inv}% of answers contained only numbers from the data.", 0.0)  # fmt: skip
    return rows


def _chart(res: Path) -> tuple[list[tuple[str, float, str]], int]:
    q, dpo, ds = (
        _load(res, "lab-qlora-r1.json"),
        _load(res, "lab-dpo-r1.json"),
        _load(res, "lab-distill-r1.json"),
    )
    po = _load(res, "lab-prompt-opt.json")
    t = "test_all"
    arms = [
        ("ML model (gradient boosting)", _m(ds, f"ml / {t}"), "s-1"),
        ("Claude Haiku, with data", _m(ds, f"claude_teacher / {t}"), "s-3"),
        ("Base rate", _m(ds, f"base_rate / {t}"), "s-ref"),
        ("Distilled student (1.5B)", _m(ds, f"distill_1_5b / {t}"), "s-5"),
        ("DPO-tuned (1.5B)", _m(dpo, f"dpo_1_5b / {t}"), "s-5"),
        ("QLoRA-tuned (1.5B)", _m(q, f"qlora_1_5b / {t}"), "s-5"),
        ("Untuned 1.5B", _m(q, f"base_1_5b / {t}"), "s-5"),
        ("Live 4-bit GGUF export", _m(q, f"gguf_q4 / {t}"), "s-5"),
        ("1.5B with the best searched prompt", _m(po, f"winner / {t}"), "s-5"),
    ]
    got = sorted([(n, v, c) for n, v, c in arms if v is not None], key=lambda a: a[1])
    n = int((q or ds or {}).get("metrics", {}).get(f"base_rate / {t}", {}).get("n", 0))
    return got, n


def chart_svg(arms: list[tuple[str, float, str]]) -> Markup:
    """Horizontal bars of the Brier score of each arm on the same test questions (lower is better).

    One narrow layout (viewBox 360 wide, name above each bar) so the text stays at least 12 px when the
    page is shown on a phone; on a desktop the figure is simply capped in width by CSS.
    """
    w, left, right, row, top = 360, 8, 64, 38, 6
    h = top + row * len(arms) + 34
    vmax = max(0.3, max(v for _, v, _ in arms) + 0.02)

    def x(v: float) -> float:
        return left + (w - left - right) * v / vmax

    out = [
        f'<svg class="llm-chart" viewBox="0 0 {w} {h}" role="img" aria-labelledby="llmc-t llmc-d">',
        f'<title id="llmc-t">Brier score of {len(arms)} arms on the same test questions</title>',
        '<desc id="llmc-d">Horizontal bars, lower is better. The dashed line is 0.25, the score of always saying 50%. The same numbers are in the table below.</desc>',
    ]
    for i, (name, v, cls) in enumerate(arms):
        y = top + i * row
        out.append(f'<text class="lc-name" x="{left}" y="{y + 13}">{escape(name)}</text>')
        out.append(
            f'<rect class="lc-bar {cls}" x="{left}" y="{y + 18}" width="{x(v) - left:.1f}" height="14"><title>{escape(name)}: {v:.4f}</title></rect>'
        )
        out.append(f'<text class="lc-val" x="{x(v) + 6:.1f}" y="{y + 30}">{v:.4f}</text>')
    base = top + row * len(arms)
    out.append(
        f'<line class="lc-coin" x1="{x(0.25):.1f}" x2="{x(0.25):.1f}" y1="{top}" y2="{base}"/>'
    )
    out.append(
        f'<text class="lc-tick" x="{x(0.25):.1f}" y="{base + 18}" text-anchor="middle">always 50% = 0.25</text>'
    )
    out.append("</svg>")
    return Markup("".join(out))


def load_page(results_dir: Path | None = None, budget: Path | None = None) -> dict[str, Any] | None:
    """The page data, or None when the result files are not there (the page is then omitted)."""
    res = results_dir or DEFAULT_RESULTS
    rows = _rows(res, budget_costs(budget or DEFAULT_BUDGET))
    arms, n = _chart(res)
    if not rows or len(arms) < 3:
        return None
    total = sum(r["cost"] or 0.0 for r in rows)
    return {
        "rows": rows, "chart": chart_svg(arms), "arms": arms, "n": n, "classes": GROUP_NAMES,
        "total_cost": total, "next": NEXT,
    }  # fmt: skip
