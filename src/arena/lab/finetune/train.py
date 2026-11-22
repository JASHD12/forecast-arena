"""Training and scoring of the YES/NO answer token (CPU-testable; the notebook runs it on a GPU)."""

from __future__ import annotations

import math
import random
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import torch
from sklearn.linear_model import LogisticRegression

from arena.lab.finetune.format import Encoded


@dataclass(frozen=True)
class TrainConfig:
    """Fixed hyper-parameters (pre-registered in lab/prereg/qlora-forecast.md)."""

    lr: float = 2e-4
    epochs: int = 1
    batch_size: int = 2
    grad_accum: int = 8
    warmup_frac: float = 0.03
    max_grad_norm: float = 1.0
    seed: int = 0
    fp16: bool = False
    log_every: int = 10


def collate(batch: Sequence[Encoded], pad_id: int, device: torch.device) -> dict[str, torch.Tensor]:
    """Left-pad a batch; positions are counted from the first real token."""
    width = max(len(e.ids) for e in batch)
    ids = torch.full((len(batch), width), pad_id, dtype=torch.long)
    mask = torch.zeros((len(batch), width), dtype=torch.long)
    for i, e in enumerate(batch):
        ids[i, width - len(e.ids) :] = torch.tensor(e.ids)
        mask[i, width - len(e.ids) :] = 1
    pos = (mask.cumsum(-1) - 1).clamp(min=0)
    labels = torch.tensor([e.label for e in batch], dtype=torch.float32)
    return {
        "input_ids": ids.to(device),
        "attention_mask": mask.to(device),
        "position_ids": pos.to(device),
        "labels": labels.to(device),
    }


def dpo_loss(m: torch.Tensor, ref: torch.Tensor, labels: torch.Tensor, beta: float) -> torch.Tensor:
    """Direct Preference Optimisation (Rafailov et al., 2023) for a one-token YES/NO answer.

    The preferred answer is the one that matches the outcome (YES when `labels` is 1, else NO).
    With a single answer token, `log pi(YES|x) - log pi(NO|x)` is exactly the logit margin (the
    softmax normaliser cancels), so the DPO objective
    `-log sigmoid(beta * [(log pi_w - log pi_ref_w) - (log pi_l - log pi_ref_l)])`
    becomes `-log sigmoid(beta * s * (m - m_ref))` with `s = +1` for YES and `-1` for NO."""
    sign = 2.0 * labels - 1.0
    return -torch.nn.functional.logsigmoid(beta * sign * (m - ref)).mean()


def margin(model: Any, batch: dict[str, torch.Tensor], yes_id: int, no_id: int) -> torch.Tensor:
    """logit(YES) - logit(NO) at the start of the answer, for each row (only the last position)."""
    out = model(
        input_ids=batch["input_ids"],
        attention_mask=batch["attention_mask"],
        position_ids=batch["position_ids"],
        logits_to_keep=1,
    )
    logits = out.logits[:, -1, :].float()
    return logits[:, yes_id] - logits[:, no_id]


def train(
    model: Any,
    data: Sequence[Encoded],
    cfg: TrainConfig,
    *,
    pad_id: int,
    yes_id: int,
    no_id: int,
    device: torch.device,
    on_log: Callable[[dict[str, float]], None] | None = None,
    ref_margins: Mapping[str, float] | None = None,
    beta: float = 0.1,
) -> list[dict[str, float]]:
    """One pass over the data; returns the loss log.

    The loss is binary cross-entropy on the YES/NO logit difference, or, when `ref_margins`
    (the frozen reference model's margin per row id) is given, the DPO loss with that reference."""
    from transformers import get_cosine_schedule_with_warmup

    rng = random.Random(cfg.seed)
    torch.manual_seed(cfg.seed)
    params = [p for p in model.parameters() if p.requires_grad]
    if not params:
        raise ValueError("no trainable parameters")
    opt = torch.optim.AdamW(params, lr=cfg.lr, weight_decay=0.0)
    steps_per_epoch = math.ceil(len(data) / (cfg.batch_size * cfg.grad_accum))
    total = max(1, steps_per_epoch * cfg.epochs)
    sched = get_cosine_schedule_with_warmup(opt, max(1, round(cfg.warmup_frac * total)), total)
    use_amp = cfg.fp16 and device.type == "cuda"
    scaler = torch.amp.GradScaler(enabled=use_amp)
    model.train()
    log: list[dict[str, float]] = []
    step, t0 = 0, time.monotonic()
    running: list[float] = []
    for _ in range(cfg.epochs):
        order = list(range(len(data)))
        rng.shuffle(order)
        batches = [order[i : i + cfg.batch_size] for i in range(0, len(order), cfg.batch_size)]
        for k, idx in enumerate(batches):
            b = collate([data[i] for i in idx], pad_id, device)
            with torch.autocast(device.type, dtype=torch.float16, enabled=use_amp):
                m = margin(model, b, yes_id, no_id)
            if ref_margins is not None:
                ref = torch.tensor(
                    [ref_margins[data[i].id] for i in idx], dtype=m.dtype, device=m.device
                )
                loss = dpo_loss(m.float(), ref.float(), b["labels"], beta)
            else:
                loss = torch.nn.functional.binary_cross_entropy_with_logits(m, b["labels"])
            scaler.scale(loss / cfg.grad_accum).backward()
            running.append(float(loss.detach()))
            if (k + 1) % cfg.grad_accum == 0 or k == len(batches) - 1:
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(params, cfg.max_grad_norm)
                scaler.step(opt)
                scaler.update()
                opt.zero_grad(set_to_none=True)
                sched.step()
                step += 1
                if step % cfg.log_every == 0 or step == total:
                    rec = {
                        "step": float(step),
                        "loss": sum(running) / len(running),
                        "lr": sched.get_last_lr()[0],
                        "seconds": time.monotonic() - t0,
                    }
                    running = []
                    log.append(rec)
                    if on_log is not None:
                        on_log(rec)
    return log


@torch.no_grad()
def margins(
    model: Any,
    data: Sequence[Encoded],
    *,
    pad_id: int,
    yes_id: int,
    no_id: int,
    device: torch.device,
    batch_size: int = 4,
    fp16: bool = False,
) -> list[float]:
    """logit(YES) - logit(NO) for every row, in input order (rows sorted by length inside)."""
    model.eval()
    order = sorted(range(len(data)), key=lambda i: len(data[i].ids))
    out = [0.0] * len(data)
    for i in range(0, len(order), batch_size):
        idx = order[i : i + batch_size]
        b = collate([data[j] for j in idx], pad_id, device)
        with torch.autocast(
            device.type, dtype=torch.float16, enabled=fp16 and device.type == "cuda"
        ):
            m = margin(model, b, yes_id, no_id)
        for j, v in zip(idx, m.tolist(), strict=True):
            out[j] = v
    return out


def sigmoid(x: float) -> float:
    """Numerically safe logistic function."""
    return 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))


def fit_platt(margins_val: Sequence[float], outcomes: Sequence[float]) -> tuple[float, float]:
    """Platt map P = sigmoid(a * margin + b), fitted on validation data only."""
    if len(set(outcomes)) < 2:
        raise ValueError("calibration needs both outcomes")
    clf = LogisticRegression(C=1e6, max_iter=1000)
    clf.fit([[m] for m in margins_val], list(outcomes))
    return float(clf.coef_[0][0]), float(clf.intercept_[0])


def apply_platt(margin_value: float, a: float, b: float) -> float:
    """Calibrated P(YES), clipped to [0.01, 0.99] like the scoring code."""
    return min(0.99, max(0.01, sigmoid(a * margin_value + b)))


def brier(probs: Sequence[float], outcomes: Sequence[float]) -> float:
    """Mean squared error of probabilities (lower is better)."""
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes, strict=True)) / len(probs)
