"""Headline sentiment with a small open model on the CPU (T372, SPEC 7.6).

Model: ``mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis`` (Apache-2.0, 82M
parameters; labels 0 negative, 1 neutral, 2 positive), pinned in docs/SOURCES.md (2026-11-27).
It runs as an ONNX file with ``onnxruntime`` and the ``tokenizers`` library; PyTorch and
``transformers`` are needed only by ``scripts/export_sentiment_onnx.py``.

A text becomes one number in [-1, 1]: P(positive) - P(negative). The texts are scored in memory
and discarded; only scores and daily aggregates leave this module, so nothing here stores an
article title, a post or a user name (S7, S12). The aggregates can be written into the morning
context and read as of the forecast time (I3).
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

REPO = "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis"
REVISION = "ae0eab9ad336d7d548e0efe394b07c04bcaf6e91"
MODEL_ID = f"distilroberta-fin-sentiment@{REVISION[:7]}"
LICENCE = "Apache-2.0"
#: Output order of the classifier (config.json id2label).
LABELS = ("negative", "neutral", "positive")
MAX_TOKENS = 128
MANIFEST = "manifest.json"
ONNX_FILE = "model.onnx"
TOKENIZER_FILE = "tokenizer.json"

#: logits (n, 3) for a batch of texts; injectable so tests need no model file.
Backend = Callable[[Sequence[str]], np.ndarray]


class SentimentError(Exception):
    """The model files are missing or do not match the pinned hashes."""


def sha256_file(path: Path) -> str:
    """Hex SHA-256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def softmax(logits: np.ndarray) -> np.ndarray:
    """Row-wise softmax."""
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def scores_from_logits(logits: np.ndarray) -> list[float]:
    """P(positive) - P(negative) for each row of (n, 3) logits, in [-1, 1]."""
    arr = np.asarray(logits, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != len(LABELS):
        raise ValueError(f"expected logits of shape (n, {len(LABELS)}), got {arr.shape}")
    p = softmax(arr)
    return [float(x) for x in p[:, 2] - p[:, 0]]


def load_backend(model_dir: Path) -> Backend:
    """An ONNX Runtime backend from `model_dir`, after checking the files' hashes.

    The directory holds ``model.onnx``, ``tokenizer.json`` and ``manifest.json`` (written by
    ``scripts/export_sentiment_onnx.py``, which records the SHA-256 of both files).
    """
    manifest_path = model_dir / MANIFEST
    if not manifest_path.is_file():
        raise SentimentError(f"{manifest_path} is missing; run scripts/export_sentiment_onnx.py")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    if manifest.get("revision") != REVISION:
        raise SentimentError("the exported model is not the pinned revision")
    for name in (ONNX_FILE, TOKENIZER_FILE):
        path = model_dir / name
        if not path.is_file() or sha256_file(path) != manifest["sha256"].get(name):
            raise SentimentError(f"{name} is missing or does not match the manifest hash")

    import onnxruntime as ort
    from tokenizers import Tokenizer

    tok = Tokenizer.from_file(str(model_dir / TOKENIZER_FILE))
    tok.enable_truncation(max_length=MAX_TOKENS)
    tok.enable_padding(pad_id=tok.token_to_id("<pad>") or 1, pad_token="<pad>")
    session = ort.InferenceSession(str(model_dir / ONNX_FILE), providers=["CPUExecutionProvider"])

    def run(texts: Sequence[str]) -> np.ndarray:
        enc = tok.encode_batch(list(texts))
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        out: Any = session.run(None, {"input_ids": ids, "attention_mask": mask})[0]
        return np.asarray(out, dtype=float)

    return run


def score(texts: Sequence[str], backend: Backend, batch_size: int = 32) -> list[float]:
    """Sentiment of each text in [-1, 1]. The texts are not kept."""
    out: list[float] = []
    for i in range(0, len(texts), batch_size):
        out.extend(scores_from_logits(backend(texts[i : i + batch_size])))
    return out


@dataclass(frozen=True)
class DayAggregate:
    """Aggregates of one coin's headline scores for one UTC day (no texts)."""

    n: int
    mean: float | None
    weighted_mean: float | None
    share_positive: float | None
    share_negative: float | None

    def as_dict(self) -> dict[str, float | int | None]:
        """JSON-friendly form for the morning context."""
        return {
            "n": self.n,
            "mean": self.mean,
            "weighted_mean": self.weighted_mean,
            "share_positive": self.share_positive,
            "share_negative": self.share_negative,
        }


def aggregate_day(
    scores: Sequence[float], weights: Sequence[float] | None = None, threshold: float = 0.2
) -> DayAggregate:
    """Mean, weighted mean and the shares above `threshold` / below `-threshold`.

    `weights` (for example article prominence) must be non-negative; without them the weighted
    mean equals the mean. An empty day gives `n = 0` and no values (never a filler, I6).
    """
    n = len(scores)
    if n == 0:
        return DayAggregate(0, None, None, None, None)
    w = [1.0] * n if weights is None else [float(x) for x in weights]
    if len(w) != n or any(x < 0 for x in w) or not math.isfinite(sum(w)):
        raise ValueError("weights must be non-negative, one per score")
    total = sum(w)
    weighted = sum(s * x for s, x in zip(scores, w, strict=True)) / total if total > 0 else None
    return DayAggregate(
        n,
        sum(scores) / n,
        weighted,
        sum(1 for s in scores if s > threshold) / n,
        sum(1 for s in scores if s < -threshold) / n,
    )


def change_vs_trailing_mean(values: Sequence[float | None], window: int = 7) -> float | None:
    """The last value minus the mean of the `window` values before it (None if unknown).

    `values` is oldest first. Missing days (None) are skipped; at least half the window must
    be present, otherwise the change is unknown.
    """
    if not values or values[-1] is None:
        return None
    prior = [v for v in values[-window - 1 : -1] if v is not None]
    if len(prior) * 2 < window:
        return None
    return float(values[-1]) - sum(prior) / len(prior)
