"""ONNX export and runtime for the LightGBM power models (T277).

Serving parity: the same quantile regressors, saved as ONNX files plus a small JSON manifest, so a
container can answer `POST /predict/power` with ONNX Runtime and without LightGBM or joblib. Only
the LightGBM families (`power-lgbq`, `power-glgbq`) are exported: `skl2onnx` 1.20 cannot convert
scikit-learn's HistGradientBoosting with quantile loss (checked 2026-11-21: the converter's tree
node cannot be built), so the live champion `power-gbq` stays on joblib.

Float32 trees differ from the float64 originals by about 1e-6, so parity is asserted to 1e-4.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from arena.forecasters.ml_power import QUANTILES, STATS, PowerModel, cdf_at, features

PARITY_TOLERANCE = 1e-4


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_model(model: PowerModel, out_dir: Path) -> dict[str, Any]:
    """Write one ONNX file per distinct LightGBM and `manifest.json`; returns the manifest."""
    from onnxmltools import convert_lightgbm
    from onnxmltools.convert.common.data_types import FloatTensorType

    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[int, str] = {}  # id(lightgbm model) -> file name (the global model is shared)
    stats: dict[str, list[dict[str, Any]]] = {}
    for stat, levels in model.models.items():
        rows = []
        for level in levels:
            booster = getattr(level, "model", level)  # StatView wraps the shared model
            if id(booster) not in files:
                width = int(booster.n_features_in_)
                onx = convert_lightgbm(
                    booster,
                    initial_types=[("X", FloatTensorType([None, width]))],
                    target_opset=15,
                )
                name = f"q{len(files):02d}.onnx"
                (out_dir / name).write_bytes(onx.SerializeToString())
                files[id(booster)] = name
            rows.append(
                {
                    "file": files[id(booster)],
                    "stat_index": getattr(level, "stat_index", None),
                    "n_stats": getattr(level, "n_stats", 0),
                    "mean": getattr(level, "mean", 0.0),
                    "std": getattr(level, "std", 1.0),
                }
            )
        stats[stat] = rows
    calib = model.calib
    manifest = {
        "version": model.version,
        "train_end": model.train_end.isoformat(),
        "quantiles": list(QUANTILES),
        "stats": stats,
        "calibration": None
        if calib is None
        else {"coef": float(calib.coef_[0][0]), "intercept": float(calib.intercept_[0])},
        "sha256": {n: _sha(out_dir / n) for n in sorted(set(files.values()))},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True))
    return manifest


class OnnxPowerModel:
    """Quantiles and calibrated probabilities from the exported files, ONNX Runtime only."""

    def __init__(self, directory: Path) -> None:
        import onnxruntime as ort

        self.manifest = json.loads((directory / "manifest.json").read_text())
        for name, digest in self.manifest["sha256"].items():
            if _sha(directory / name) != digest:
                raise ValueError(f"{name}: hash differs from the manifest")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        self._sessions = {
            n: ort.InferenceSession(str(directory / n), opts, providers=["CPUExecutionProvider"])
            for n in self.manifest["sha256"]
        }

    @property
    def version(self) -> str:
        return str(self.manifest["version"])

    def quantiles(self, stat: str, x: Sequence[float]) -> list[float]:
        """Predicted quantiles of a statistic from its feature vector."""
        out = []
        for level in self.manifest["stats"][stat]:
            row = np.asarray(x, dtype=np.float64)
            if level["stat_index"] is not None:
                onehot = np.zeros(level["n_stats"])
                onehot[level["stat_index"]] = 1.0
                row = np.concatenate([row, onehot])
            sess = self._sessions[level["file"]]
            z = float(sess.run(None, {"X": row.astype(np.float32)[None, :]})[0].ravel()[0])
            out.append(z * level["std"] + level["mean"])
        return out

    def probability(
        self,
        stat: str,
        daily: list[dict[str, Any]],
        target: date,
        threshold: float,
        comparator: str,
    ) -> dict[str, Any]:
        """Calibrated P(YES) for 'stat on target day is above/below threshold'."""
        if stat not in STATS:
            raise ValueError(f"unknown statistic {stat!r}")
        qs = self.quantiles(stat, features(daily, target))
        f = cdf_at(qs, threshold)
        raw = f if comparator == "lt" else 1 - f
        c = self.manifest["calibration"]
        p = raw
        if c is not None:
            p1 = min(max(raw, 1e-4), 1 - 1e-4)
            z = c["coef"] * math.log(p1 / (1 - p1)) + c["intercept"]
            p = 1 / (1 + math.exp(-z))
        return {
            "probability": p,
            "raw": raw,
            "quantiles": dict(zip(map(str, QUANTILES), qs, strict=True)),
            "version": self.version,
        }
