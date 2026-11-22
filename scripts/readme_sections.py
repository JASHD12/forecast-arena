"""Generate the README's results and skills sections (T142) from committed sources:
`python scripts/readme_sections.py` rewrites them, `--check` fails if they are stale.

- Results: the per-forecaster tables of the committed backtest model cards
  (docs/models/*.md), labelled as backtests; never live numbers typed by hand (I5).
- Skills: the skill -> code table of the 'For recruiters' page (src/arena/site/recruiters.py).
- Highlights (T184): five bullets whose figures are parsed from the model cards and the
  committed LLM eval results, so the README never carries a hand-typed number (I5).
- Stack: one line of the skill names from the same table.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arena.site.recruiters import PROOFS  # noqa: E402

CARDS = (
    ("power", "Electricity: champion vs baselines"),
    ("power-lgbm", "Electricity: LightGBM challenger"),
    ("power-ts", "Electricity: time-series benchmarks"),
)


def _first_table(md: str) -> str:
    lines, out, on = md.splitlines(), [], False
    for ln in lines:
        if ln.startswith("| Forecaster |"):
            on = True
        if on:
            if not ln.startswith("|"):
                break
            out.append(ln)
    return "\n".join(out)


def results() -> str:
    parts = [
        "All numbers below are **backtests**: past days replayed through the production "
        "code, not the live record. Lower Brier is better; always saying 50% scores "
        "0.25. Generated from the model cards in `docs/models/`."
    ]
    for stem, title in CARDS:
        md = (ROOT / "docs" / "models" / f"{stem}.md").read_text(encoding="utf-8")
        span = re.search(r"Batches (\S+) to (\S+) \((\d+) batch days\)", md)
        when = f" ({span.group(1)} to {span.group(2)}, {span.group(3)} days)" if span else ""
        parts.append(f"**{title}**{when}\n\n{_first_table(md)}")
    return "\n\n".join(parts)


def _card(stem: str) -> str:
    return (ROOT / "docs" / "models" / f"{stem}.md").read_text(encoding="utf-8")


def _brier(md: str, fid: str) -> str:
    m = re.search(rf"^\| {re.escape(fid)} \| \d+ \| ([0-9.]+) \|", md, re.M)
    if not m:
        raise SystemExit(f"no Brier row for {fid}")
    return m.group(1)


def _diff(md: str, label: str) -> tuple[str, str, bool]:
    m = re.search(rf"^\| {re.escape(label)} \| ([-+0-9.]+) \| (\[[^\]]+\]) \| (yes|no)", md, re.M)
    if not m:
        raise SystemExit(f"no comparison row {label!r}")
    return m.group(1), m.group(2), m.group(3) == "yes"


def highlights() -> str:
    power, lgbm, mlp, ts = (_card(c) for c in ("power", "power-lgbm", "power-mlp", "power-ts"))
    span = re.search(r"\((\d+) batch days\)", power)
    days = span.group(1) if span else "?"
    d, ci, _ = _diff(power, "ml - base_rate")
    ld, lci, lok = _diff(lgbm, "ml_lgbm - ml")
    md, mci, mok = _diff(mlp, "ml_mlp - ml")
    ts_rows = {
        fid: _brier(ts, fid) for fid in ("ts_chronos2", "ts_chronos", "ts_sarimax", "ts_ets")
    }
    glob = _card("power-global")
    gd, gci, gok = _diff(glob, "ml_glgbm - ml")
    lab = _lab_bullets()
    runs = [
        json.loads(f.read_text(encoding="utf-8"))
        for f in sorted((ROOT / "evals" / "results").glob("eval-*.json"))
    ]
    runs = [r for r in runs if not any(v.endswith("|so") for v in r["versions"].values())]
    first, last = runs[0], runs[-1]
    pct = lambda r: f"{100 * r['metrics']['llm_plain']['json_valid_first_try']:.0f}%"  # noqa: E731
    lines = [
        f"- **A classical model that clearly beats the base rate** (backtest, {days} days of "
        f"German electricity): Brier {_brier(power, 'ml')} vs {_brier(power, 'base_rate')}, "
        f"paired difference {d} {ci}. Calibrated gradient-boosted quantile regression.",
        f"- **Honest champion/challenger:** an Optuna-tuned LightGBM challenger improved Brier by "
        f"{ld} {lci} ({'supported' if lok else 'not supported'}); a PyTorch network "
        f"({md} {mci}, {'supported' if mok else 'interval includes zero'}), four "
        f"time-series models (Chronos-2 {ts_rows['ts_chronos2']}, Chronos-Bolt "
        f"{ts_rows['ts_chronos']}, SARIMAX {ts_rows['ts_sarimax']}, ETS {ts_rows['ts_ets']}) and a "
        f"global LightGBM ({gd} {gci}, {'supported' if gok else 'interval includes zero'}) "
        "did not beat the champion, and say so.",
        f"- **LLM engineering with evals:** a frozen golden set caught a silent output-cap "
        f"truncation; first-try valid JSON went from {pct(first)} to {pct(last)}. Tool-using "
        "agent, LangGraph agent, RAG over past questions, tracing, hard daily cost caps.",
        "- **Forecasts locked before the truth:** an append-only, hash-chained ledger on a git "
        "branch; `arena ledger verify --git` lets anyone check that no forecast was written "
        "after its question locked. Failures are recorded as skips, never filled in.",
        "- **Runs itself:** scheduled GitHub Actions jobs, CI-gated promotion to a stable "
        "branch, health checks with incident issues, Docker, Kubernetes (kind), dbt and "
        'Airflow validated in CI. Live record: "too early to tell" until the statistics '
        "can decide.",
        *lab,
    ]
    return "\n".join(lines)


def _lab_bullets() -> list[str]:
    """Bullets about the experiments lab, every figure read from the committed result files."""
    res = ROOT / "evals" / "results"
    ft = json.loads((res / "lab-qlora-r1.json").read_text(encoding="utf-8"))
    pair = {(p["a"], p["b"]): p for p in ft["paired"] if p["split"] == "test_all"}

    def fmt(a: str, b: str) -> str:
        p = pair[(a, b)]
        return f"{p['diff']:+.4f} [{p['lo']:+.4f}, {p['hi']:+.4f}]"

    conf = json.loads((res / "lab-conformal.json").read_text(encoding="utf-8"))["metrics"]["mean"]
    docs = json.loads((res / "lab-docs-assistant.json").read_text(encoding="utf-8"))
    dm = docs["metrics"]["docs_assistant"]
    return [
        "- **LLM fine-tuning, measured honestly:** a QLoRA fine-tune of Qwen2.5-1.5B on replayed "
        f"questions beat its untuned self ({fmt('qlora_1_5b', 'base_1_5b')}) but not the base "
        f"rate ({fmt('qlora_1_5b', 'base_rate')}) and not the ML model "
        f"({fmt('qlora_1_5b', 'ml')}); pre-registered, time-split, negative result published "
        "(paired Brier differences, 46 test days). The shipped 4-bit GGUF kept almost none of "
        f"that gain (Brier {fmt('gguf_q4', 'base_1_5b')} against the untuned model, "
        f"{fmt('gguf_q4', 'base_rate')} against the base rate): it runs live as an experiment "
        "and the loss from quantisation is itself a finding.",
        f"- **Uncertainty and serving:** conformal price bands raise 80% coverage from "
        f"{100 * conf['raw80']:.1f}% to {100 * conf['conformal80']:.1f}% over {conf['months']} "
        "months; LightGBM models are exported to ONNX with parity tests and served behind a "
        "REST endpoint; a cited, offline docs assistant answers "
        f"{dm['hit_pct']:.0f}% of a hand-written question set and refuses "
        f"{dm['correct_refusal_pct']:.0f}% of the out-of-scope ones.",
    ]


def headline() -> str:
    """The README's 'Result so far' block (P3): one backtest result, its caveat, live status."""
    power = _card("power")
    span = re.search(r"\((\d+) batch days\)", power)
    n = re.search(r"^\| ml \| (\d+) \|", power, re.M)
    days = int(span.group(1)) if span else 0
    d, ci, ok = _diff(power, "ml - persistence")
    per_day = round(int(n.group(1)) / days) if n and days else 0
    return (
        f"**Result so far (backtest, not the live record):** over {days} days of German "
        f"day-ahead electricity, the gradient-boosted model scores Brier {_brier(power, 'ml')} "
        f'against {_brier(power, "persistence")} for "same as last time" and '
        f"{_brier(power, 'base_rate')} for the base rate (lower is better; always saying 50% "
        f"scores 0.25). Paired difference to persistence: {d} {ci}"
        f"{', supported' if ok else ', interval includes zero'}. "
        f"Caveat: the {n.group(1) if n else '?'} questions come from only {days} independent "
        f"days (about {per_day} correlated questions per day), so intervals resample "
        "whole days.\n\n"
        "**Live record:** in a rehearsal phase since the first batch (2026-11-13); the official "
        "record starts after five clean days in a row and not before a date fixed in advance. "
        "Whether LLM agents beat the classical model is **too early to tell**; the "
        "[Status page](https://jashd12.github.io/forecast-arena/status.html) shows the "
        "current counts."
    )


def lab() -> str:
    """The Experiments lab table: committed results with their cards, then what is pending."""
    from arena.lab.results import PLANNED, load_lab_results

    rows = ["| Technique | Status | Card |", "|---|---|---|"]
    for r in sorted(load_lab_results(ROOT / "evals" / "results"), key=lambda r: r.title):
        rows.append(f"| {r.title} | evaluated (not a live score) | [{r.card}]({r.card}) |")
    for title, state in PLANNED:
        rows.append(f"| {title} | {state} | - |")
    rows.append("")
    rows.append(
        "Live experimental forecasters: the QLoRA-tuned model (running since the first morning "
        "after 2026-11-22, with its fixed pre-registered expectations), an agent with hybrid "
        "retrieval and guards, and a cascade router (both still switched off until their launch "
        "checks). None of them enters the headline board. Details: "
        "[Lab page](https://jashd12.github.io/"
        "forecast-arena/lab.html), [explainer](docs/explainers/06-experiments-lab.md)."
    )
    return "\n".join(rows)


def stack() -> str:
    return "**Stack:** " + " · ".join(skill for skill, _, _, _ in PROOFS)


def skills() -> str:
    rows = ["| Skill | In this project | Code |", "|---|---|---|"]
    for skill, what, _, paths in PROOFS:
        code = "<br>".join(f"`{p}`" for p in paths)
        rows.append(f"| {skill} | {what} | {code} |")
    return "\n".join(rows)


def render(readme: str) -> str:
    blocks = (
        ("headline", headline()),
        ("highlights", highlights()),
        ("lab", lab()),
        ("stack", stack()),
        ("results", results()),
        ("skills", skills()),
    )
    for name, body in blocks:
        start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
        pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
        if not pat.search(readme):
            raise SystemExit(f"README is missing the {start} ... {end} markers")
        readme = pat.sub(lambda _m, b=body, s=start, e=end: f"{s}\n{b}\n{e}", readme)
    return readme


if __name__ == "__main__":
    path = ROOT / "README.md"
    old = path.read_text(encoding="utf-8")
    new = render(old)
    if "--check" in sys.argv:
        if new != old:
            print("README sections are stale: run python scripts/readme_sections.py")
            sys.exit(1)
        print("README sections up to date")
    else:
        path.write_text(new, encoding="utf-8")
        print("README sections written")
