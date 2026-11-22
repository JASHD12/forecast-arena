"""Lineage of the fine-tuned model: one JSON record that ties every hash together (T248, rule L4).

The pin file (`lab/artefacts/llm_local_ft.json`) says which GGUF runs live. The lineage record
says where it came from: base model and revision, the dataset hashes, the pre-registration, the
Colab code commit and package versions, the adapter, the quantisation tool, every calibration map
in order, and where the evaluation is. `check` compares the record with the pin and the result
file, so a pin change without a lineage line (or the other way round) fails a unit test.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arena.lab.artefacts import FtArtefact

LINEAGE_PATH = Path("docs/lab/runs/qlora-r1.json")


def build(
    art: FtArtefact,
    summary: Mapping[str, Any],
    calibrations: Sequence[Mapping[str, Any]],
    result_path: str,
) -> dict[str, Any]:
    """The lineage record from the pin, the Colab run summary and the calibration history."""
    variant = summary["variants"]["qlora_1_5b"]
    return {
        "name": art.name,
        "base_model": art.base_model,
        "base_revision": art.base_revision,
        "recipe": {
            "method": "QLoRA (4-bit NF4, LoRA r16), one YES/NO token, loss on the answer only",
            "train_rows": summary["train_rows"],
            "gpu": summary["gpu"],
            "seconds_training": variant["seconds_training"],
            "train_loss_first": round(variant["train_loss_first"], 4),
            "train_loss_last": round(variant["train_loss_last"], 4),
        },
        "code_commit": summary["code_commit"],
        "colab_finished_utc": summary["finished_utc"],
        "packages_colab": dict(summary["packages"]),
        "dataset_sha256": dict(summary["dataset_sha256"]),
        "prereg_sha256": art.prereg_sha256,
        "adapter_sha256": art.adapter_sha256,
        "gguf": {
            "sha256": art.sha256,
            "url": art.url,
            "quantisation": "Q4_K_M",
            "llama_cpp_commit": summary["gguf"]["llama_cpp_commit"],
        },
        "yes_id": art.yes_id,
        "no_id": art.no_id,
        "calibrations": [dict(c) for c in calibrations],
        "live_platt": list(art.platt),
        "evaluation": result_path,
    }


def check(record: Mapping[str, Any], art: FtArtefact, result: Mapping[str, Any]) -> list[str]:
    """Problems found when comparing the record with the pin and the result file (empty if fine)."""
    problems: list[str] = []
    if record["gguf"]["sha256"] != art.sha256:
        problems.append("lineage GGUF hash differs from the pin file")
    if record["adapter_sha256"] != art.adapter_sha256:
        problems.append("lineage adapter hash differs from the pin file")
    if record["prereg_sha256"] != art.prereg_sha256:
        problems.append("lineage pre-registration hash differs from the pin file")
    if record["base_revision"] != art.base_revision:
        problems.append("lineage base revision differs from the pin file")
    if tuple(record["live_platt"]) != tuple(art.platt):
        problems.append("lineage live Platt map differs from the pin file")
    if not record["calibrations"] or tuple(record["calibrations"][-1]["platt"]) != tuple(art.platt):
        problems.append("the last calibration in the lineage is not the pinned map")
    arts = result.get("artefacts", {})
    if arts.get("gguf") != art.sha256 or arts.get("adapter") != art.adapter_sha256:
        problems.append("evaluation result was made for different artefacts")
    return problems


def write(record: Mapping[str, Any], path: Path = LINEAGE_PATH) -> None:
    """Write the record as stable, sorted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
