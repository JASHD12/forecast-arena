"""The eval workflow hands each golden set the replayed `ml` probabilities built for it (T386)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from arena.evals.golden import load

ROOT = Path(__file__).parents[2]
FLOW = (ROOT / ".github/workflows/llm-eval.yml").read_text("utf-8")


def test_each_power_golden_set_maps_to_the_file_built_for_it() -> None:
    cases = dict(re.findall(r"(\w[\w-]+\.jsonl)\)\s+MLPROBS=(\S+)", FLOW))
    cases["power-2026-10.jsonl"] = re.search(r"\*\) MLPROBS=(\S+)", FLOW).group(1)  # default arm
    assert set(cases) == {
        "power-2026-10.jsonl",
        "power-2026-11a.jsonl",
        "replay-weather-attention-2026-11-25.jsonl",
    }
    for golden, probs in cases.items():
        _, sha = load(ROOT / "evals/golden" / golden)
        doc = json.loads((ROOT / probs).read_text("utf-8"))
        assert doc["golden_sha256"] == sha, f"{probs} was not built for {golden}"


def test_no_hardcoded_ml_probs_path_is_left_in_the_run_commands() -> None:
    assert (
        "--ml-probs evals/golden" not in FLOW and FLOW.count("--ml-probs $MLPROBS") == 3
    )  # + the Tier C branch


def test_tier_c_runs_the_replay_set_per_topic_with_the_live_ml_forecasts() -> None:
    assert "replay-weather-attention-2026-11-25.jsonl" in FLOW.split("options:")[1][:300]
    assert "--per-topic $PER_TOPIC" in FLOW and "PER_TOPIC: ${{ inputs.per_topic }}" in FLOW
    assert "--limit $LIMIT" in FLOW  # the default path is unchanged
    assert '--limit "$LIMIT"' not in FLOW
