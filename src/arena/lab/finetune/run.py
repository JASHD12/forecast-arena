"""One experiment variant end to end: zero-shot scores, LoRA training, tuned scores, files.

The notebook calls this with real models on a GPU; the unit tests call it with a tiny
random model. Output files per variant (all in `out_dir`): `scores_<name>.jsonl` (one line
per scored row, base and tuned), `train_log_<name>.json`, `adapter_<name>/`, and a summary
dict returned to the caller.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from arena.lab import dataset as ds
from arena.lab.finetune import format as fmt
from arena.lab.finetune import train as tr

SCORED = ("val", "test_oct", "test_nov")


@dataclass(frozen=True)
class Spec:
    """A variant: its name and the base model it adapts."""

    name: str  # tuned variant, e.g. "qlora_1_5b"
    base_id: str
    four_bit: bool = False
    base_name: str = ""  # the untuned model scored the same way, e.g. "base_1_5b"


def _score_all(
    model: Any, enc: Mapping[str, Sequence[fmt.Encoded]], kw: dict[str, Any], fp16: bool
) -> dict[str, list[float]]:
    return {s: tr.margins(model, enc[s], fp16=fp16, **kw) for s in SCORED}


def _calibrated(
    margins: Mapping[str, Sequence[float]], enc: Mapping[str, Sequence[fmt.Encoded]]
) -> tuple[dict[str, list[float]], tuple[float, float]]:
    a, b = tr.fit_platt(margins["val"], [e.label for e in enc["val"]])
    return {s: [tr.apply_platt(m, a, b) for m in margins[s]] for s in SCORED}, (a, b)


def _lines(
    name: str,
    enc: Mapping[str, Sequence[fmt.Encoded]],
    margins: Mapping[str, Sequence[float]],
    probs: Mapping[str, Sequence[float]],
) -> list[str]:
    out = []
    for s in SCORED:
        for e, m, p in zip(enc[s], margins[s], probs[s], strict=True):
            row = {"variant": name, "split": s, "id": e.id, "margin": m, "p": p, "outcome": e.label}
            out.append(json.dumps(row, sort_keys=True))
    return out


def run_variant(
    spec: Spec,
    rows: Mapping[str, Sequence[ds.Row]],
    tokenizer: fmt.Tokenizer,
    load_model: Callable[[], Any],
    add_lora_fn: Callable[[Any], Any],
    out_dir: Path,
    cfg: tr.TrainConfig,
    *,
    device: torch.device,
    train_rows: int = 2000,
    max_len: int = 2560,
    eval_batch: int = 4,
    on_log: Callable[[dict[str, float]], None] | None = None,
) -> dict[str, Any]:
    """Zero-shot scores, LoRA training and tuned scores for one variant; writes the files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    yes_id, no_id = fmt.answer_token_ids(tokenizer)
    pad = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
    kw: dict[str, Any] = {
        "pad_id": pad, "yes_id": yes_id, "no_id": no_id, "device": device, "batch_size": eval_batch,
    }  # fmt: skip
    tr_rows = ds.subsample(list(rows["train"]), train_rows, seed=cfg.seed)
    enc: dict[str, list[fmt.Encoded]] = {}
    dropped: dict[str, int] = {}
    for split, rs in {**rows, "train": tr_rows}.items():
        enc[split], dropped[split] = fmt.encode_rows(tokenizer, rs, max_len)
    if any(not enc[s] for s in SCORED):
        raise ValueError("a scored split is empty after dropping long rows")
    train_kw = {k: v for k, v in kw.items() if k != "batch_size"}

    t0 = time.monotonic()
    model = load_model()
    base_margins = _score_all(model, enc, kw, cfg.fp16)
    base_probs, base_platt = _calibrated(base_margins, enc)
    t_base = time.monotonic() - t0

    model = add_lora_fn(model)
    t1 = time.monotonic()
    log = tr.train(model, enc["train"], cfg, on_log=on_log, **train_kw)
    t_train = time.monotonic() - t1
    model.save_pretrained(str(out_dir / f"adapter_{spec.name}"))
    tuned_margins = _score_all(model, enc, kw, cfg.fp16)
    tuned_probs, tuned_platt = _calibrated(tuned_margins, enc)

    lines = _lines(spec.base_name or f"base_{spec.name}", enc, base_margins, base_probs)
    lines += _lines(spec.name, enc, tuned_margins, tuned_probs)
    (out_dir / f"scores_{spec.name}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / f"train_log_{spec.name}.json").write_text(
        json.dumps(log, indent=1), encoding="utf-8"
    )

    def brier_of(probs: Mapping[str, Sequence[float]], split: str) -> float:
        return tr.brier(probs[split], [e.label for e in enc[split]])

    return {
        "name": spec.name,
        "base_id": spec.base_id,
        "four_bit": spec.four_bit,
        "rows": {s: len(v) for s, v in enc.items()},
        "dropped_too_long": dropped,
        "train_loss_first": log[0]["loss"] if log else None,
        "train_loss_last": log[-1]["loss"] if log else None,
        "seconds_zero_shot_scoring": round(t_base, 1),
        "seconds_training": round(t_train, 1),
        "platt_base": list(base_platt),
        "platt_tuned": list(tuned_platt),
        "brier": {
            "base": {s: brier_of(base_probs, s) for s in SCORED},
            "tuned": {s: brier_of(tuned_probs, s) for s in SCORED},
        },
    }


def file_hashes(root: Path) -> dict[str, str]:
    """SHA-256 of every file under `root` (relative paths), for the run summary."""
    import hashlib

    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }
