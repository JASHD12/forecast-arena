"""Generate the README's results and skills sections (T142) from committed sources:
`python scripts/readme_sections.py` rewrites them, `--check` fails if they are stale.

- Results: the per-forecaster tables of the committed backtest model cards
  (docs/models/*.md), labelled as backtests; never live numbers typed by hand (I5).
- Skills: the skill -> code table of the 'For recruiters' page (src/arena/site/recruiters.py).
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arena.site.recruiters import PROOFS  # noqa: E402

CARDS = (("power", "Electricity: champion vs baselines"),
         ("power-lgbm", "Electricity: LightGBM challenger"),
         ("power-ts", "Electricity: time-series benchmarks"))  # fmt: skip


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
    parts = ["All numbers below are **backtests**: past days replayed through the production "
             "code, not the live record. Lower Brier is better; always saying 50% scores "
             "0.25. Generated from the model cards in `docs/models/`."]  # fmt: skip
    for stem, title in CARDS:
        md = (ROOT / "docs" / "models" / f"{stem}.md").read_text(encoding="utf-8")
        span = re.search(r"Batches (\S+) to (\S+) \((\d+) batch days\)", md)
        when = f" ({span.group(1)} to {span.group(2)}, {span.group(3)} days)" if span else ""
        parts.append(f"**{title}**{when}\n\n{_first_table(md)}")
    return "\n\n".join(parts)


def skills() -> str:
    rows = ["| Skill | In this project | Code |", "|---|---|---|"]
    for skill, what, _, paths in PROOFS:
        code = "<br>".join(f"`{p}`" for p in paths)
        rows.append(f"| {skill} | {what} | {code} |")
    return "\n".join(rows)


def render(readme: str) -> str:
    for name, body in (("results", results()), ("skills", skills())):
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
