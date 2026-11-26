#!/usr/bin/env python3
# ruff: noqa: E501
"""Fill the generated tables of the forecasting skills (T352) from stored backtest rows.

Every number in a skill comes from here (integrity rule I5), computed from backtest runs whose last day
is on or before 2026-10-31, i.e. before the live record (I8). The runs live in `backtests/` (git-ignored,
local only), so this script runs where they exist; CI only checks that the markers and the provenance
lines are present (`tests/unit/test_agent_skills.py`).

    python scripts/skill_tables.py           # write the tables into the SKILL.md files
    python scripts/skill_tables.py --check   # exit 1 if a table is stale (needs the backtests)
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from arena.agent.skills import CUTOFF  # noqa: E402

SKILLS = ROOT / "src" / "arena" / "agent" / "skills"
RUNS = {
    "power": ("electricity-day-ahead", "power_rates", "power-2025-11-01-2026-10-31-20261112T1356"),
    "markets": ("fx-ecb-moves", "markets_rates", "markets-2024-11-01-2026-10-31-20261112T1423"),
}
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_TARGET = re.compile(r"-(\d{4}-\d{2}-\d{2})-v\d+$")


def rows(run: str) -> list[dict]:
    """One row per question (the base_rate rows carry every question's outcome)."""
    d = ROOT / "backtests" / run
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    if meta["last"] > CUTOFF:
        raise SystemExit(f"{run} ends {meta['last']}, after the cut-off {CUTOFF}")
    out = []
    for line in (d / "forecasts.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["forecaster_id"] != "base_rate":
            continue
        m = _TARGET.search(r["question_id"])
        r["target"] = date.fromisoformat(m.group(1)) if m else date.fromisoformat(r["batch_date"])
        if r["target"] <= date.fromisoformat(CUTOFF):  # the last batch asks about the next days
            out.append(r)
    return out


def _persistence(series: list[tuple[date, int]]) -> float:
    s = sorted(series)
    same = [a[1] == b[1] for a, b in pairwise(s)]
    return sum(same) / len(same) if same else float("nan")


def power_table(rs: list[dict], run: str) -> str:
    by_t: dict[str, list[dict]] = defaultdict(list)
    for r in rs:
        by_t[r["template"]].append(r)
    first, last = min(r["target"] for r in rs), max(r["target"] for r in rs)
    lines = [
        f"Source: backtest run `{run}`, target days {first} to {last}, computed by `scripts/skill_tables.py`.",
        "",
        "| Template | Questions | Share YES | Same outcome as the day before |",
        "|---|---|---|---|",
    ]
    for t in sorted(by_t):
        v = by_t[t]
        yes = sum(r["outcome"] for r in v) / len(v)
        p = _persistence([(r["target"], r["outcome"]) for r in v])
        lines.append(f"| {t} | {len(v)} | {yes:.2f} | {p:.2f} |")
    lines += [
        "",
        "Share YES by weekday of the target day:",
        "",
        "| Template | " + " | ".join(WEEKDAYS) + " |",
    ]
    lines.append("|---|" + "---|" * 7)
    for t in sorted(by_t):
        cells = []
        for wd in range(7):
            v = [r["outcome"] for r in by_t[t] if r["target"].weekday() == wd]
            cells.append(f"{sum(v) / len(v):.2f}" if v else "-")
        lines.append(f"| {t} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def markets_table(rs: list[dict], run: str) -> str:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rs:
        groups[(r["template"], r["entity"])].append(r)
    first, last = min(r["target"] for r in rs), max(r["target"] for r in rs)
    lines = [
        f"Source: backtest run `{run}`, target days {first} to {last}, computed by `scripts/skill_tables.py`.",
        "",
        "| Template | Pair | Questions | Share YES | Same outcome as the day before |",
        "|---|---|---|---|---|",
    ]
    for t, e in sorted(groups):
        v = groups[(t, e)]
        yes = sum(r["outcome"] for r in v) / len(v)
        p = _persistence([(r["target"], r["outcome"]) for r in v])
        lines.append(f"| {t} | {e} | {len(v)} | {yes:.2f} | {p:.2f} |")
    return "\n".join(lines)


BUILDERS = {"power": power_table, "markets": markets_table}


def fill(text: str, name: str, table: str) -> str:
    """Replace what sits between the markers of block `name`."""
    pat = re.compile(rf"(<!-- generated:{name} -->\n).*?(\n?<!-- /generated:{name} -->)", re.S)
    if not pat.search(text):
        raise SystemExit(f"markers for {name} not found")
    return pat.sub(lambda m: m.group(1) + table + "\n" + m.group(2).lstrip("\n"), text)


def main() -> int:
    """Write the tables, or with --check compare them."""
    stale = False
    for domain, (skill, block, run) in RUNS.items():
        if not (ROOT / "backtests" / run).is_dir():
            print(
                f"backtest run {run} not found (it is local only); skipping {skill}",
                file=sys.stderr,
            )
            if "--check" in sys.argv:
                continue
            return 2
        table = BUILDERS[domain](rows(run), run)
        path = SKILLS / skill / "SKILL.md"
        old = path.read_text(encoding="utf-8")
        new = fill(old, block, table)
        if "--check" in sys.argv:
            if new != old:
                print(f"{skill}: generated table is stale; run python scripts/skill_tables.py")
                stale = True
        else:
            path.write_text(new, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
