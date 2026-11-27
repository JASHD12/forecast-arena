"""Run the pre-registered backtest of `sentiment-gdelt-r1` and write the lab result (T374).

    python scripts/run_sentiment_backtest.py [--out evals/results/lab-sentiment.json]

Reads the recorded CoinGecko prices (tests/fixtures/coingecko) and GDELT history
(tests/fixtures/gdelt/history). Offline; deterministic (fixed bootstrap seed).
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arena.backtest import sentiment as B
from arena.domains.crypto import COINS, crypto_domain_from_prices
from arena.lab.results import LabResult
from arena.sources.coingecko import parse_daily

ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "lab" / "prereg" / "sentiment.md"
GDELT = ROOT / "tests" / "fixtures" / "gdelt" / "history"
CG = ROOT / "tests" / "fixtures" / "coingecko"


def main() -> None:
    """Build rows, walk forward, summarise, write the LabResult."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "evals" / "results" / "lab-sentiment.json")
    args = ap.parse_args()
    prices = {
        c: parse_daily(json.loads(gzip.decompress((CG / f"{c}_365d.json.gz").read_bytes())))
        for c in COINS
    }
    domain = crypto_domain_from_prices(prices, {c: (f"fixture://{c}", "c" * 64) for c in COINS})
    last = max(max(p) for p in prices.values())
    news = B.load_news(GDELT)
    rows = B.build_rows(domain, news, last)
    scored = B.walk_forward(rows)
    s = B.summarise(rows, scored)
    chunks = sorted(p.name for p in GDELT.glob("*_timeline*.json"))
    result = LabResult(
        experiment="sentiment",
        title="News tone (GDELT) as a crypto forecaster: sentiment-gdelt-r1 against ml",
        created_at=datetime.now(UTC).isoformat(),
        why="Sentiment from news and social media is a common feature in forecasting products; "
        "this is the pre-registered test of whether it adds anything for crypto. (gdelt-doc-api)",
        prereg_sha256=B.sha256_file(PREREG),
        dataset_sha256={
            "gdelt_manifest": B.sha256_file(GDELT / "manifest.json"),
            **{f"coingecko_{c}": B.sha256_file(CG / f"{c}_365d.json.gz") for c in COINS},
        },
        artefacts={"gdelt_chunks": f"{len(chunks)} of 50 recorded"},
        metrics=s["metrics"],
        paired=s["paired"],
        notes=[
            "Backtest (I4): never part of a live score. Walk-forward from 2026-03-12, refit every "
            "7 days, no outcome used before it was known. Paired day-block bootstrap intervals.",
            *s["notes"],
        ],
        limits=[
            "CoinGecko's demo history is 365 days, so there is no held-out year (stated in the "
            "pre-registration); the test period is the last part of one year.",
            "GDELT counts per day are small for these queries (single or double digits for most "
            "days), so the tone is a noisy feature.",
            f"{len(chunks)} of 50 GDELT history chunks were recorded; days in missing chunks have "
            "no features and are not scored for any arm.",
            "No claim about prediction of price direction beyond this period, and no advice.",
        ],
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(result.model_dump_json(indent=2) + "\n", "utf-8")
    print(
        json.dumps({"metrics": s["metrics"], "paired": s["paired"], "notes": s["notes"]}, indent=1)
    )


if __name__ == "__main__":
    main()
