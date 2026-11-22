"""Parity of the 4-bit GGUF against the Colab scores of the same adapter (H-FT3, T245).

The Colab run scored every split with the 4-bit bitsandbytes model plus adapter. The GGUF is the
merged model quantised to Q4_K_M and run by llama.cpp. Both should give almost the same logit
margin and the same calibrated probability; the pre-registration allows the Brier score to get
worse by less than 0.005. This module compares margins and Brier on a subset of rows.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from arena.lab.ft_runtime import calibrated


def colab_margins(scores_path: Path, variant: str = "qlora_1_5b") -> dict[str, dict[str, Any]]:
    """{item id: {margin, outcome, split}} of one variant from the Colab scores file."""
    out: dict[str, dict[str, Any]] = {}
    for line in scores_path.read_text(encoding="utf-8").splitlines():
        d = json.loads(line)
        if d["variant"] == variant:
            out[d["id"]] = {"margin": d["margin"], "outcome": d["outcome"], "split": d["split"]}
    return out


def brier(p: Sequence[float], y: Sequence[int]) -> float:
    """Mean squared error of probabilities."""
    return float(np.mean([(a - b) ** 2 for a, b in zip(p, y, strict=True)]))


def compare(
    gguf: Mapping[str, float],
    colab: Mapping[str, Mapping[str, Any]],
    platt: tuple[float, float],
) -> dict[str, float | int]:
    """Margin differences and Brier of both runs on the ids the GGUF scored."""
    ids = [i for i in gguf if i in colab]
    if not ids:
        raise ValueError("no common items")
    y = [int(colab[i]["outcome"]) for i in ids]
    mg = np.array([gguf[i] for i in ids])
    mc = np.array([float(colab[i]["margin"]) for i in ids])
    pg = [calibrated(float(m), platt) for m in mg]
    pc = [calibrated(float(m), platt) for m in mc]
    corr = float(np.corrcoef(mg, mc)[0, 1]) if len(ids) > 2 else math.nan
    return {
        "n": len(ids),
        "margin_mean_abs_diff": round(float(np.mean(np.abs(mg - mc))), 4),
        "margin_max_abs_diff": round(float(np.max(np.abs(mg - mc))), 4),
        "margin_correlation": round(corr, 4),
        "brier_gguf": round(brier(pg, y), 4),
        "brier_colab": round(brier(pc, y), 4),
        "brier_loss": round(brier(pg, y) - brier(pc, y), 4),
    }
