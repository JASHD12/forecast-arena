"""Fit the `llm_context_cal` map once on the lab training answers (T382).

    python scripts/fit_llm_context_cal.py [--out lab/artefacts/llm_context_cal.json]

Inputs: Claude Haiku's `llm_context` probabilities for 1,198 training-split questions
(`lab/data/distill-labels-v1.json`, probability only) and their outcomes from
`lab/data/forecast-sft/train.jsonl.gz`. Fixed by `lab/prereg/analyst-and-calibration.md` before
this ran. Offline and deterministic; live outcomes are never read.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arena.forecasters.llm_context_cal import fit_map

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / "lab" / "data" / "distill-labels-v1.json"
TRAIN = ROOT / "lab" / "data" / "forecast-sft" / "train.jsonl.gz"


def sha256(path: Path) -> str:
    """Hex SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Fit and write the artefact."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "lab" / "artefacts" / "llm_context_cal.json")
    args = ap.parse_args()
    labels = json.loads(LABELS.read_text("utf-8"))
    outcome = {}
    with gzip.open(TRAIN, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            outcome[r["id"]] = int(r["outcome"])
    pairs = [
        (p, outcome[i])
        for i, p in zip(labels["ids"], labels["p"], strict=True)
        if p is not None and i in outcome
    ]
    missing = sum(
        1
        for i, p in zip(labels["ids"], labels["p"], strict=True)
        if p is not None and i not in outcome
    )
    if missing:
        raise SystemExit(f"{missing} labelled ids have no training outcome")
    cal = fit_map([p for p, _ in pairs], [y for _, y in pairs], sha256(LABELS), sha256(TRAIN))
    raw_brier = sum((p - y) ** 2 for p, y in pairs) / len(pairs)
    cal_brier = sum((cal.apply(p) - y) ** 2 for p, y in pairs) / len(pairs)
    doc = {
        "kind": "calibration map of llm_context (power, training split only)",
        "map": "p' = sigmoid(a * logit(p) + b); p clipped to [0.01, 0.99]",
        "a": round(cal.a, 6),
        "b": round(cal.b, 6),
        "n_train": cal.n_train,
        "labelled_ids_in_file": sum(1 for p in labels["p"] if p is not None),
        "labels_sha256": cal.labels_sha256,
        "train_sha256": cal.train_sha256,
        "teacher": labels["teacher"],
        "in_sample_brier_raw": round(raw_brier, 4),
        "in_sample_brier_calibrated": round(cal_brier, 4),
        "version": cal.version,
        "note": "in-sample numbers only describe the fit; the test is the pre-registered one",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1) + "\n", "utf-8")
    print(json.dumps(doc, indent=1))


if __name__ == "__main__":
    main()
