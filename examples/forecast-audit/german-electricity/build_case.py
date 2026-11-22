#!/usr/bin/env python3
"""Rebuild the German electricity example from the repository's frozen records.

Project-side script (it reads files of this repository; the shipped CSVs need none of it). It
joins the 46 evening-price questions of the two frozen golden sets (1 Oct - 15 Nov 2026 batch
days) with two probability sources that already exist in the repository:

- `base_rate`: the leak-free base rate stored with every golden question;
- `fine_tuned_gguf`: the stored GGUF logit margins (`lab/artefacts/llm_local_ft.margins.json`)
  turned into probabilities with the pinned Platt map (`lab/artefacts/llm_local_ft.json`),
  clipped to [0.01, 0.99] like the scoring code.

Only derived, binary information is written: the case calendar, the outcome and the two
probabilities. No hourly prices are redistributed. Timing is a REPLAY: each probability is stamped
with the question's as-of time (05:30 UTC, before the 09:30 UTC lock), which is what the frozen
record says the forecaster could see; it is not a ledger-verified live time.

    python examples/forecast-audit/german-electricity/build_case.py          # rewrite the files
    python examples/forecast-audit/german-electricity/build_case.py --check  # fail if they differ
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))

import forecast_audit as fa  # noqa: E402

GOLDEN = ("evals/golden/power-2026-10.jsonl", "evals/golden/power-2026-11a.jsonl")
MARGINS = "lab/artefacts/llm_local_ft.margins.json"
PIN = "lab/artefacts/llm_local_ft.json"
CANDIDATE, BASELINE = "fine_tuned_gguf", "base_rate"
FALSE_ALERT_COST, MISS_COST = 1.0, 4.0
ATTRIBUTION = "Bundesnetzagentur | SMARD.de"
TERMS_URL = "https://www.smard.de/home/datennutzung"
SOURCE_REVISION = "4f370c93ebbb2e77b1f6460123fc838eb5747b56"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def platt(margin: float, a: float, b: float) -> float:
    """Calibrated probability, clipped like `arena.scoring.core` (tested against it)."""
    return fa.clipped(1 / (1 + math.exp(-(a * margin + b))))


def build_rows() -> tuple[list[list[str]], list[list[str]], int]:
    """(case rows, prediction rows, golden rows read) for the evening questions."""
    margins = json.loads((ROOT / MARGINS).read_text(encoding="utf-8"))
    a, b = json.loads((ROOT / PIN).read_text(encoding="utf-8"))["platt"]
    cases: list[list[str]] = []
    preds: list[list[str]] = []
    seen = 0
    for rel in GOLDEN:
        for line in (ROOT / rel).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            q = row["question"]
            if (q["domain"], q["template"], q["entity"]) != ("power", "evening_gt", "DE_LU"):
                continue
            seen += 1
            qid = q["question_id"]
            lock = q["lock_time"].replace("Z", "+00:00")
            cases.append([qid, q["target_date"], lock, "resolved", str(int(row["outcome"]))])
            issued = row["asof"]
            preds.append([qid, BASELINE, "forecast", f"{row['base_rate']:.6f}", issued, ""])
            preds.append(
                [qid, CANDIDATE, "forecast", f"{platt(margins[qid], a, b):.6f}", issued, ""]
            )
    cases.sort(key=lambda r: (r[1], r[0]))
    preds.sort(key=lambda r: (r[0], r[1]))
    return cases, preds, seen


def _csv(header: str, rows: list[list[str]]) -> str:
    return header + "\n" + "".join(",".join(r) + "\n" for r in rows)


def build(out: Path) -> dict[str, str]:
    """Write the CSVs, expected report and manifest into `out`; return the file texts."""
    cases, preds, _ = build_rows()
    out.mkdir(parents=True, exist_ok=True)
    texts = {
        "cases.csv": _csv(",".join(fa.CASE_COLUMNS), cases),
        "predictions.csv": _csv(",".join(fa.PREDICTION_COLUMNS), preds),
    }
    for name, text in texts.items():
        (out / name).write_text(text, encoding="utf-8")
    report, rows, inputs = fa.run(
        out / "cases.csv", out / "predictions.csv", CANDIDATE, BASELINE,
        FALSE_ALERT_COST, MISS_COST, "no-alert", "replayed",
    )  # fmt: skip
    fa.write_outputs(out / "expected", report, rows, inputs)
    texts["expected/report.json"] = (out / "expected" / "report.json").read_text(encoding="utf-8")
    for name in ("cases-audited.csv", "report.html"):
        texts[f"expected/{name}"] = (out / "expected" / name).read_text(encoding="utf-8")
    manifest = {
        "name": "forecast-audit German electricity example",
        "schema_version": fa.SCHEMA_VERSION,
        "timing_label": "replayed",
        "source_revision": SOURCE_REVISION,
        "scope": "46 DE_LU evening-price questions, batch days 2026-10-01 to 2026-11-15; "
        "29 YES, 17 NO",
        "event": "mean of the three hourly day-ahead prices 17:00-20:00 Europe/Berlin on the "
        "target day is above that question's published price threshold",
        "inputs_in_repository": [
            {"path": p, "sha256": _sha(ROOT / p)} for p in (*GOLDEN, MARGINS, PIN)
        ],
        "shipped_files": {
            name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in texts.items()
        },
        "transformations": [
            "kept evening_gt / DE_LU questions only",
            "group_day = target (delivery) day; lock_at = the question's lock time",
            "base_rate = the leak-free base rate stored with the golden question",
            "fine_tuned_gguf = Platt(stored GGUF margin), clipped to [0.01, 0.99]",
            "issued_at = the question's as-of time (a replay stamp, not a live time)",
            "no hourly prices are shipped; only binary outcomes and probabilities",
        ],
        "data_source": {
            "name": "SMARD day-ahead wholesale prices, DE/LU",
            "attribution": ATTRIBUTION,
            "terms_url": TERMS_URL,
            "terms_checked": "2026-11-22: CC BY 4.0 with this attribution; the page also states "
            "that the licensing of wholesale prices is under review (HEDWIG procedure), so only "
            "derived binary events and probabilities are shipped",
        },
        "licences": {"code": "MIT (repository LICENSE)", "data": "see DATA_LICENSE.md"},
        "cost_units": {"false_alert": FALSE_ALERT_COST, "miss": MISS_COST},
    }
    text = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    (out / "MANIFEST.json").write_text(text, encoding="utf-8")
    texts["MANIFEST.json"] = text
    return texts


def main() -> int:
    """Rewrite the shipped files, or with --check compare a fresh build to them."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if the shipped files differ")
    args = ap.parse_args()
    if not args.check:
        build(HERE)
        print(f"wrote {HERE}")
        return 0
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fresh = build(Path(tmp))
    stale = [n for n, t in fresh.items() if (HERE / n).read_text(encoding="utf-8") != t]
    if stale:
        print("stale files:", ", ".join(stale), file=sys.stderr)
        return 1
    print("shipped files are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
