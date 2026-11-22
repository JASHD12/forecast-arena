"""Phase 16: the replay and study functions run end to end on small synthetic data."""

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from arena.scoring.core import Scored


def scored_history(n_days: int = 14) -> list[Scored]:
    rng = np.random.default_rng(1)
    out = []
    for d in range(n_days):
        day = date(2026, 11, 1) + timedelta(days=d)
        for k in range(6):
            y = int(rng.random() < 0.5)
            qid = f"power-{day}-{k}"
            good = float(np.clip(0.5 + (y - 0.5) * 0.7 + rng.normal(0, 0.05), 0.02, 0.98))
            out += [
                Scored(qid, "ml", "v", "power", day, good, y),
                Scored(qid, "base_rate", "v", "power", day, 0.5, y),
            ]
            if k % 2:
                out.append(Scored(qid, "llm_context", "v", "power", day, float(rng.random()), y))
    return out


def test_bandit_replay_and_summary() -> None:
    from arena.lab import bandit_study as bs

    rep = bs.replay(scored_history())
    assert len(rep["y"]) > 40 and {"hedge", "equal_mean", "thompson", "ml"} <= set(rep["arms"])
    metrics, paired = bs.summarise(rep)
    assert metrics["hedge"]["n"] == metrics["equal_mean"]["n"]
    assert metrics["best_expert_in_hindsight"]["brier"] == min(
        m["brier"] for k, m in metrics.items() if k in ("ml", "base_rate", "llm_context")
    )
    assert {(p["a"], p["b"]) for p in paired} >= {("hedge", "equal_mean"), ("hedge", "ml")}
    # the replay never lets a day's own outcomes train that day's weights
    first_day = min(rep["days"])
    assert first_day == "2026-11-01"


def prices(n_days: int, seed: int = 0) -> dict[date, list[float]]:
    rng = np.random.default_rng(seed)
    out = {}
    for i in range(n_days):
        day = date(2026, 1, 1) + timedelta(days=i)
        hours = {date(2026, 3, 29): 23, date(2026, 10, 25): 25}.get(day, 24)  # Berlin DST days
        wave = 40 + 25 * np.sin(np.arange(hours) / 24 * 2 * np.pi * (1 + i % 2))
        out[day] = [float(x) for x in wave + rng.normal(0, 3, hours)]
    return out


def test_anomaly_study_reports_false_alarms_and_detection_per_fault() -> None:
    from arena.lab import anomaly_study as st

    daily = prices(150)
    res = st.run(
        daily, (date(2026, 2, 1), date(2026, 3, 31)), (date(2026, 4, 1), date(2026, 5, 20)), step=10
    )
    assert res["n_windows"] >= 4 and set(res["metrics"]) == {"isolation_forest", "robust_z"}
    row = res["metrics"]["robust_z"]
    assert {f"{f}_detected_pct" for f in st.FAULTS} <= set(row) and 0 <= row[
        "false_alarm_pct"
    ] <= 100
    assert row["unit_error_detected_pct"] > 50  # prices divided by 1000 are easy for a z-score


def test_regime_study_runs_and_reports_a_paired_interval() -> None:
    from arena.lab import regimes as rg

    daily = prices(200, seed=3)
    res = rg.run(
        daily, (date(2026, 1, 1), date(2026, 5, 31)), (date(2026, 6, 1), date(2026, 7, 10))
    )
    assert res["info"]["k"] in (2, 3, 4, 5, 6)
    assert set(res["metrics"]) == {"without_regime", "with_regime"}
    p = res["paired"]
    assert p["lo"] <= p["diff"] <= p["hi"] and p["n"] > 20
    assert sum(res["regime_share_pct"]) == pytest.approx(100, abs=0.5)


class FakeS3:
    """The five calls `upload_dir` makes, on a dict (no boto3 needed)."""

    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict]] = {}

    def get_paginator(self, name: str):
        outer = self

        class P:
            def paginate(self, Bucket: str, Prefix: str):
                import hashlib

                yield {
                    "Contents": [
                        {
                            "Key": k,
                            "ETag": f'"{hashlib.md5(v[0], usedforsecurity=False).hexdigest()}"',
                        }
                        for k, v in outer.objects.items()
                        if k.startswith(Prefix)
                    ]
                }

        return P()

    def put_object(self, Bucket: str, Key: str, Body: bytes, **meta) -> None:
        self.objects[Key] = (Body, meta)

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.objects.pop(Key, None)


def test_upload_dir_logic_without_boto3(tmp_path: Path) -> None:
    from arena.cloud.s3 import CACHE_HTML, CACHE_OTHER, upload_dir

    (tmp_path / "a").mkdir()
    (tmp_path / "index.html").write_text("<p>x</p>")
    (tmp_path / "a" / "b.css").write_text("b{}")
    s3 = FakeS3()
    rep = upload_dir(s3, "bucket", tmp_path, "site")
    assert sorted(rep.uploaded) == ["site/a/b.css", "site/index.html"]
    assert s3.objects["site/index.html"][1]["CacheControl"] == CACHE_HTML
    assert s3.objects["site/a/b.css"][1]["ContentType"] == "text/css"
    assert s3.objects["site/a/b.css"][1]["CacheControl"] == CACHE_OTHER
    (tmp_path / "index.html").write_text("<p>changed</p>")
    (tmp_path / "a" / "b.css").unlink()
    again = upload_dir(s3, "bucket", tmp_path, "site", prune=True)
    assert again.uploaded == ["site/index.html"] and again.deleted == ["site/a/b.css"]
    dry = upload_dir(s3, "bucket", tmp_path, "site", dry_run=True)
    assert dry.skipped == ["site/index.html"] and set(s3.objects) == {"site/index.html"}
    with pytest.raises(ValueError):
        upload_dir(s3, "bucket", tmp_path / "missing")
