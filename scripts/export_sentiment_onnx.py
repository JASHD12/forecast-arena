"""Export the pinned sentiment model to ONNX and check parity with PyTorch (T372).

    python scripts/export_sentiment_onnx.py OUT_DIR [--parity 200]

Downloads ``REPO`` at ``REVISION`` (Apache-2.0) from the Hugging Face Hub, writes
``model.onnx``, ``tokenizer.json`` and ``manifest.json`` (revision and SHA-256 of both files) into
OUT_DIR, then scores generated headlines with PyTorch and ONNX Runtime and fails if the scores
differ by more than 1e-4. Needs ``requirements/sentiment-export.txt``; never run by ``make check``.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from arena.nlp import sentiment as S

TOLERANCE = 1e-4

_SUBJECTS = ["Bitcoin", "Ethereum", "Solana", "XRP", "BNB", "The crypto market", "Regulators"]
_PHRASES = [
    "rallies to a new monthly high as buyers return",
    "falls sharply after a large exchange outage",
    "is flat while traders wait for the central bank",
    "faces a lawsuit over disputed token sales",
    "gains after a successful network upgrade",
    "slides as miners sell holdings",
    "attracts record inflows into spot funds",
    "stays range-bound on thin volume",
]


def generated_headlines(n: int, seed: int = 0) -> list[str]:
    """`n` synthetic headlines (no real article text is used for the parity check)."""
    rng = random.Random(seed)
    return [f"{rng.choice(_SUBJECTS)} {rng.choice(_PHRASES)}" for _ in range(n)]


def export(out_dir: Path) -> None:
    """Write model.onnx, tokenizer.json and manifest.json."""
    import torch
    from huggingface_hub import hf_hub_download
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    out_dir.mkdir(parents=True, exist_ok=True)
    model = AutoModelForSequenceClassification.from_pretrained(S.REPO, revision=S.REVISION)
    model.eval()
    tok = AutoTokenizer.from_pretrained(S.REPO, revision=S.REVISION)
    batch = tok(["Bitcoin rises", "Ether falls"], return_tensors="pt", padding=True)
    torch.onnx.export(
        model,
        (batch["input_ids"], batch["attention_mask"]),
        str(out_dir / S.ONNX_FILE),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "seq"},
            "attention_mask": {0: "batch", 1: "seq"},
            "logits": {0: "batch"},
        },
        opset_version=17,
        dynamo=False,
    )
    tok_file = hf_hub_download(S.REPO, "tokenizer.json", revision=S.REVISION)
    (out_dir / S.TOKENIZER_FILE).write_bytes(Path(tok_file).read_bytes())
    manifest = {
        "repo": S.REPO,
        "revision": S.REVISION,
        "licence": S.LICENCE,
        "labels": list(S.LABELS),
        "sha256": {name: S.sha256_file(out_dir / name) for name in (S.ONNX_FILE, S.TOKENIZER_FILE)},
    }
    (out_dir / S.MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", "utf-8")


def parity(out_dir: Path, n: int) -> float:
    """Largest absolute score difference between PyTorch and ONNX on `n` generated headlines."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    texts = generated_headlines(n)
    model = AutoModelForSequenceClassification.from_pretrained(S.REPO, revision=S.REVISION)
    model.eval()
    tok = AutoTokenizer.from_pretrained(S.REPO, revision=S.REVISION)
    ref: list[float] = []
    with torch.no_grad():
        for i in range(0, n, 32):
            enc = tok(
                texts[i : i + 32],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=S.MAX_TOKENS,
            )
            ref.extend(S.scores_from_logits(model(**enc).logits.numpy()))
    onnx_scores = S.score(texts, S.load_backend(out_dir))
    return float(np.max(np.abs(np.array(ref) - np.array(onnx_scores))))


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("--parity", type=int, default=200)
    args = ap.parse_args()
    export(args.out_dir)
    diff = parity(args.out_dir, args.parity)
    print(f"max |score difference| over {args.parity} headlines: {diff:.2e}")
    manifest = json.loads((args.out_dir / S.MANIFEST).read_text("utf-8"))
    print(json.dumps(manifest["sha256"], indent=2))
    if diff > TOLERANCE:
        raise SystemExit(f"parity failed: {diff:.2e} > {TOLERANCE}")


if __name__ == "__main__":
    main()
