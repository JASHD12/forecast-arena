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
    ts_rows = {fid: _brier(ts, fid) for fid in ("ts_chronos", "ts_sarimax", "ts_ets")}
    evals = sorted((ROOT / "evals" / "results").glob("eval-*.json"))
    first, last = (json.loads(f.read_text(encoding="utf-8")) for f in (evals[0], evals[-1]))
    pct = lambda r: f"{100 * r['metrics']['llm_plain']['json_valid_first_try']:.0f}%"  # noqa: E731
    lines = [
        f"- **A classical model that clearly beats the base rate** (backtest, {days} days of "
        f"German electricity): Brier {_brier(power, 'ml')} vs {_brier(power, 'base_rate')}, "
        f"paired difference {d} {ci}. Calibrated gradient-boosted quantile regression.",
        f"- **Honest champion/challenger:** an Optuna-tuned LightGBM challenger improved Brier by "
        f"{ld} {lci} ({'supported' if lok else 'not supported'}); a PyTorch network "
        f"({md} {mci}, {'supported' if mok else 'interval includes zero'}) and three "
        f"time-series models (Chronos-Bolt {ts_rows['ts_chronos']}, SARIMAX "
        f"{ts_rows['ts_sarimax']}, ETS {ts_rows['ts_ets']}) did not beat the champion, and say so.",
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
    ]
    return "\n".join(lines)


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
        ("highlights", highlights()),
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
