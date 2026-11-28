"""One model card per forecaster, in one format, and a data sheet (T392).

    python scripts/model_cards.py            # rewrite docs/model-cards/
    python scripts/model_cards.py --check    # fail if a file is stale

Generated from the catalog (`arena.forecasters.catalog`: kind, flags, information set), the
committed standings snapshot (`docs/data/standings.json`, with 95% intervals) and the source
modules (names, licences). Sections of every card: intended use, data, metrics with intervals,
limits, monitoring. No number is typed by hand (I5); a forecaster outside the headline set says
so instead of showing one.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arena.forecasters.catalog import CATALOG, Entry  # noqa: E402
from arena.sources import (  # noqa: E402
    brightsky,
    coingecko,
    ecb,
    gdelt_tone,
    smard,
    wikimedia,
)

OUT = ROOT / "docs" / "model-cards"
TOPIC_NAMES = {
    "power": "Electricity",
    "weather": "Weather",
    "attention": "Wikipedia",
    "markets": "Currencies",
    "crypto": "Crypto",
}

INTENDED = {
    "baseline": "A reference every other forecaster must beat; never a candidate for decisions.",
    "ml": "A classical statistical model forecasting yes/no questions about tomorrow for a public "
    "research benchmark. Not for trading, energy purchasing or any decision about people.",
    "ai": "A language-model forecaster in a public research benchmark of tomorrow's yes/no "
    "questions. Its probabilities are experiments, not advice; its text may be wrong.",
    "combiner": "A forecaster built only from the other forecasters' probabilities.",
    "human": "The human reference: whatever the panel members submit.",
}
LIMITS = {
    "baseline": "It learns only the past frequency of the answer; it cannot react to news or data.",
    "ml": "It sees only the as-of numbers in its context (no news, no outages); fixed or fitted "
    "error models can be too wide or too narrow; direction questions on prices are held at 50%.",
    "ai": "It can hedge toward the base rate, can be wrong with confidence, and costs tokens. "
    "A replay of its behaviour cannot reproduce every tool (news, retrieval).",
    "combiner": "It cannot be better than its members on average and inherits their blind spots.",
    "human": "Small, self-selected and not monitored by the system.",
}
MONITORING = {
    "baseline": "Part of the daily health check roster; a missing forecast raises an incident.",
    "ml": "Weekly champion/challenger decision with a recorded reason (`docs/models/`), "
    "version changelog on the Methods page, health check roster.",
    "ai": "Daily token cap (tested to equal the workflows), recorded skips with reasons, tool-call "
    "and latency tables on the LLM page, health check roster.",
    "combiner": "It writes nothing until enough resolved forecasts exist (SPEC 8); health roster.",
    "human": "Intake is checked at build time; entries are validated before use.",
}


def _standings() -> dict:
    return json.loads((ROOT / "docs" / "data" / "standings.json").read_text(encoding="utf-8"))


def _fmt(r: dict) -> str:
    vs = r["vs_base"]
    diff = "reference" if vs is None else f"{vs['diff']:+.4f} [{vs['lo']:+.4f}, {vs['hi']:+.4f}]"
    return f"| {r['n']} | {r['brier']:.3f} | [{r['lo']:.3f}, {r['hi']:.3f}] | {diff} |"


def metrics(e: Entry, snap: dict) -> str:
    """The metrics section: official overall, then per topic over all days."""
    lines = []
    head = (
        "| Questions | Brier | 95% interval | Brier difference to the base rate |\n"
        "|---|---|---|---|"
    )
    rows = {r["id"]: r for r in snap["official"]["rows"]}
    if e.id in rows:
        b = snap["official"]
        lab = f" ({b['label']})" if b["label"] else ""
        lines += [
            f"**Official record since {snap['official_start']}, {b['questions']} common questions "
            f"over {snap['official_days']} days{lab}.** Lower Brier is better; always saying 50% "
            f"scores 0.250.",
            "",
            head,
            _fmt(rows[e.id]),
            "",
        ]
        lines += [
            "**By topic (rehearsal and official days together):**",
            "",
            "| Topic | Questions | Brier | 95% interval | Brier difference to the base rate |",
        ]
        lines.append("|---|---|---|---|---|")
        for topic, name in TOPIC_NAMES.items():
            board = snap["topics_all_days"].get(topic)
            row = (
                None if board is None else next((r for r in board["rows"] if r["id"] == e.id), None)
            )
            if row:
                lines.append(f"| {name} {_fmt(row)}")
        lines.append("")
    else:
        lines.append(
            "Not part of the headline set (`base_rate`, `ml`, `llm_context`, `agent`), so the "
            "snapshot has no live number for it. See the Lab page and `docs/lab/` for its "
            "pre-registered evaluation, if it has one."
        )
    return "\n".join(lines)


def card(e: Entry, snap: dict) -> str:
    """One model card."""
    status = (
        "retired (history kept)"
        if e.retired
        else "experimental, outside the headline board"
        if e.experimental
        else "live"
    )
    flag = f"`ARENA_{e.flag.upper()}`" if e.flag else "always on"
    sees, answers = e.info if e.info else ("see `docs/SPEC.md` section 8", "see the Methods page")
    return "\n".join(
        [
            f"# Model card: {e.name} (`{e.id}`)",
            "",
            "Generated by `scripts/model_cards.py` from the catalog, the standings snapshot and "
            "the source modules. Research project, not advice.",
            "",
            f"- **Kind:** {e.kind}{', labelled AI' if e.ai else ''}",
            f"- **Status:** {status}; switch: {flag}",
            "",
            "## Intended use",
            "",
            INTENDED[e.kind],
            "",
            "## Data",
            "",
            f"**What it sees:** {sees}.",
            "",
            f"**Which questions it answers:** {answers}.",
            "",
            "Every input goes through the as-of gateway, so it sees only data published before the "
            "forecast time (integrity rule I3). Sources and licences: "
            "[DATA_SHEET.md](DATA_SHEET.md).",
            "",
            "## Metrics",
            "",
            metrics(e, snap),
            "",
            "## Limits",
            "",
            LIMITS[e.kind],
            "",
            "## Monitoring",
            "",
            MONITORING[e.kind],
            "",
        ]
    )


def data_sheet() -> str:
    """The data sheet: every source with its attribution and licence, from the source modules."""
    rows = [
        ("Electricity day-ahead prices", smard.ATTRIBUTION, smard.LICENCE),
        ("Weather observations and forecasts", brightsky.ATTRIBUTION, brightsky.LICENCE),
        ("Wikipedia page views", wikimedia.ATTRIBUTION, "see docs/SOURCES.md"),
        ("Exchange rates", " ".join(str(ecb.ATTRIBUTION).split()), "free use, cite the ECB"),
        ("Crypto prices", coingecko.ATTRIBUTION, coingecko.LICENCE),
        ("News tone and headlines", gdelt_tone.ATTRIBUTION, gdelt_tone.LICENCE),
    ]
    lines = [
        "# Data sheet",
        "",
        "Generated by `scripts/model_cards.py`. What the benchmark uses, under which terms. "
        "All data are public; the benchmark stores aggregates and values, never article text, "
        "and no personal data (Wikipedia articles about people are excluded, SPEC 7.3). "
        "Verified facts and dates are in `docs/SOURCES.md`.",
        "",
        "| Data | Attribution | Licence or terms |",
        "|---|---|---|",
        *(f"| {a} | {b} | {c} |" for a, b, c in rows),
        "",
        "Questions are generated by code from this data each evening and locked at 09:30 UTC; "
        "outcomes come from the same sources, with a grace period before a question is voided.",
        "",
    ]
    return "\n".join(lines)


def build() -> dict[str, str]:
    """{file name: content} for every card, the data sheet and the index."""
    snap = _standings()
    files = {f"{e.id}.md": card(e, snap) for e in CATALOG}
    files["DATA_SHEET.md"] = data_sheet()
    idx = [
        "# Model cards",
        "",
        "One card per forecaster in one format (intended use, data, metrics with intervals, "
        "limits, monitoring), plus a [data sheet](DATA_SHEET.md). Generated by "
        "`scripts/model_cards.py`; the older backtest cards of the champion models are in "
        "[`docs/models/`](../models/).",
        "",
        "| Forecaster | Kind | Status |",
        "|---|---|---|",
    ]
    for e in CATALOG:
        st = "retired" if e.retired else "experimental" if e.experimental else "live"
        idx.append(f"| [{e.name}]({e.id}.md) | {e.kind} | {st} |")
    files["README.md"] = "\n".join(idx) + "\n"
    return files


def main() -> int:
    """CLI entry point."""
    files = build()
    if "--check" in sys.argv:
        stale = [
            n
            for n, t in files.items()
            if not (OUT / n).is_file() or (OUT / n).read_text("utf-8") != t
        ]
        extra = sorted(p.name for p in OUT.glob("*.md") if p.name not in files)
        if stale or extra:
            print(f"model cards are stale ({stale + extra}): run python scripts/model_cards.py")
            return 1
        print("model cards up to date")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (OUT / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} files to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
