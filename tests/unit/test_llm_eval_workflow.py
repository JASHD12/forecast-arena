"""The eval workflow hands each golden set the replayed `ml` probabilities built for it (T386)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from arena.evals.golden import load

ROOT = Path(__file__).parents[2]
FLOW = (ROOT / ".github/workflows/llm-eval.yml").read_text("utf-8")


def test_each_power_golden_set_maps_to_the_file_built_for_it() -> None:
    cases = dict(re.findall(r"(power-[\w-]+\.jsonl)\)\s+MLPROBS=(\S+)", FLOW))
    cases["power-2026-10.jsonl"] = re.search(r"\*\) MLPROBS=(\S+)", FLOW).group(1)  # default arm
    assert set(cases) == {"power-2026-10.jsonl", "power-2026-11a.jsonl"}
    for golden, probs in cases.items():
        _, sha = load(ROOT / "evals/golden" / golden)
        doc = json.loads((ROOT / probs).read_text("utf-8"))
        assert doc["golden_sha256"] == sha, f"{probs} was not built for {golden}"


def test_no_hardcoded_ml_probs_path_is_left_in_the_run_commands() -> None:
    assert "--ml-probs evals/golden" not in FLOW and FLOW.count("--ml-probs $MLPROBS") == 2
