#!/usr/bin/env python3
"""Evaluate "Ask the Arena" offline (T314): build the fixture site, run the golden questions
through the compiled orchestrator with Node, write the lab result and its card.

    python scripts/chat_eval.py            # writes the lab result and its card
    python scripts/chat_eval.py --print    # only print the measured numbers

The questions are `evals/golden/chat-v1.jsonl` plus one lookup per fixture question (generated from
the pack). It needs Node; no network, no model, no cost.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from arena.lab.results import LabResult, card_markdown  # noqa: E402


def measure(pack: Path) -> dict:
    """Run the Node evaluator over `pack`; returns its JSON."""
    out = subprocess.run(
        [
            "node", str(ROOT / "tools/chat-eval/run.js"),
            str(ROOT / "src/arena/site/static/chat.js"), str(pack),
            str(ROOT / "evals/golden/chat-v1.jsonl"),
        ],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return json.loads(out.stdout)


def fixture_pack(tmp: Path) -> Path:
    """Build the offline fixture site and return its chat pack."""
    site = tmp / "site"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_e2e_site.py"), str(site)],
        check=True, capture_output=True,
    )  # fmt: skip
    return site / "chat" / "pack.json"


def to_result(m: dict) -> LabResult:
    """The lab result from the measured numbers (every figure is copied, I5)."""
    metrics: dict[str, dict[str, float | int | str | None]] = {}
    for cat, v in m["category_pct"].items():
        metrics[f"category: {cat}"] = {"n": v["n"], "hit_pct": v["pct"]}
    metrics["finance and personal refusals"] = {"correct_refusal_pct": m["refusal_pct"]}
    metrics["benign questions"] = {"false_refusal_pct": m["false_refusal_pct"]}
    metrics["all answers"] = {"n": m["answers"], "no_invented_pct": m["no_invented_numbers_pct"]}
    t = m["tiers"]
    return LabResult(
        experiment="ask-arena",
        title="Ask the Arena: tiered chat over the published record",
        created_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        why="Retrieval-grounded assistants with refusals and tiered routing are the standard "
        "pattern for answering questions over a company's own data without inventing facts.",
        metrics=metrics,
        notes=[
            f"{m['answers']} questions on the offline fixture pack ({m['pack']['questions']} "
            f"questions, {m['pack']['docs']} document chunks, {m['pack']['bytes']} bytes).",
            f"Answers by tier: lookup {t['0']}, documents {t['1']}, declined or refused {t['-1']}.",
            f"Latency in Node: median {m['latency_ms']['p50']} ms, 95th percentile "
            f"{m['latency_ms']['p95']} ms.",
            "Missed questions: "
            + (
                "; ".join(
                    f"{f['category']}: {f.get('q', '')}"
                    for f in m["failures"]
                    if f["category"] not in ("lookup", "result", "invented_numbers")
                )
                or "none"
            )
            + ".",
        ],
        limits=[
            "The questions are written by the project owner's agent, so they may not match how "
            "visitors phrase things; the rates are not a measure of real-world accuracy.",
            "'No invented numbers' checks that every number in an answer occurs in the pack or "
            "the question (probabilities as whole percentages); it does not check meaning.",
            "The forecaster-choice rule is a hypothesis from the routing study; this evaluation "
            "does not test whether it picks the better forecaster.",
            "The fixture pack has only one topic; the live pack has five.",
        ],
        card="docs/lab/ask-arena.md",
    )


def main() -> int:
    """Measure; with no `--print`, write the result and card."""
    with tempfile.TemporaryDirectory() as t:
        m = measure(fixture_pack(Path(t)))
    brief = {k: v for k, v in m.items() if k != "failures"}
    print(json.dumps(brief, indent=1))
    if "--print" in sys.argv:
        return 0
    r = to_result(m)
    (ROOT / "evals/results/lab-ask-arena.json").write_text(
        json.dumps(r.model_dump(), indent=1) + "\n", encoding="utf-8"
    )
    (ROOT / "docs/lab/ask-arena.md").write_text(card_markdown(r), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
