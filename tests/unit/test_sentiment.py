"""Headline sentiment helpers (T372): pure functions and the load checks, no model file."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from arena.nlp import sentiment as S


def test_scores_from_logits_range_and_sign() -> None:
    logits = np.array([[5.0, 0.0, -5.0], [-5.0, 0.0, 5.0], [0.0, 3.0, 0.0]])
    neg, pos, neu = S.scores_from_logits(logits)
    assert -1 <= neg < -0.9 and 0.9 < pos <= 1 and abs(neu) < 1e-9


def test_scores_from_logits_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError):
        S.scores_from_logits(np.zeros((2, 2)))


def test_score_batches_and_keeps_order() -> None:
    seen: list[int] = []

    def backend(texts):  # type: ignore[no-untyped-def]
        seen.append(len(texts))
        return np.array([[0.0, 0.0, float(len(t))] for t in texts])

    out = S.score(["a", "bb", "ccc", "dddd", "e"], backend, batch_size=2)
    assert seen == [2, 2, 1]
    assert out == [*sorted(out[:4]), out[4]] and len(out) == 5


def test_aggregate_day() -> None:
    a = S.aggregate_day([0.5, -0.5, 0.0, 0.9])
    assert a.n == 4 and a.mean == pytest.approx(0.225)
    assert a.share_positive == 0.5 and a.share_negative == 0.25
    w = S.aggregate_day([1.0, -1.0], weights=[3, 1])
    assert w.weighted_mean == pytest.approx(0.5)


def test_aggregate_empty_day_has_no_filler() -> None:
    a = S.aggregate_day([])
    assert a.n == 0 and a.mean is None and a.share_positive is None


def test_aggregate_rejects_bad_weights() -> None:
    with pytest.raises(ValueError):
        S.aggregate_day([0.1, 0.2], weights=[1.0])
    with pytest.raises(ValueError):
        S.aggregate_day([0.1], weights=[-1.0])


def test_change_vs_trailing_mean() -> None:
    assert S.change_vs_trailing_mean([0.0] * 7 + [0.5]) == pytest.approx(0.5)
    assert S.change_vs_trailing_mean([None] * 7 + [0.5]) is None
    assert S.change_vs_trailing_mean([0.1, None, 0.3, 0.2, 0.4, None, 0.0, None]) is None
    assert S.change_vs_trailing_mean([]) is None


def test_load_backend_requires_matching_files(tmp_path: Path) -> None:
    with pytest.raises(S.SentimentError, match="missing"):
        S.load_backend(tmp_path)
    (tmp_path / S.MANIFEST).write_text(json.dumps({"revision": "other", "sha256": {}}))
    with pytest.raises(S.SentimentError, match="pinned revision"):
        S.load_backend(tmp_path)
    (tmp_path / S.MANIFEST).write_text(
        json.dumps({"revision": S.REVISION, "sha256": {S.ONNX_FILE: "0", S.TOKENIZER_FILE: "0"}})
    )
    (tmp_path / S.ONNX_FILE).write_bytes(b"x")
    (tmp_path / S.TOKENIZER_FILE).write_bytes(b"y")
    with pytest.raises(S.SentimentError, match="hash"):
        S.load_backend(tmp_path)


def test_pinned_constants() -> None:
    assert S.REVISION == "ae0eab9ad336d7d548e0efe394b07c04bcaf6e91"
    assert S.LABELS == ("negative", "neutral", "positive") and S.LICENCE == "Apache-2.0"
