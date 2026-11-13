"""PyTorch challenger for the power `ml` forecaster (T113, owner-approved roadmap).

A small multi-layer perceptron predicts all 13 quantile levels of a daily price statistic
at once (one output per level) and is trained with the summed pinball loss. Inputs and
target are standardised with training-set statistics; training is full-batch Adam on the
CPU with a fixed seed and deterministic algorithms, so a refit is reproducible. Predicted
quantiles are sorted (rearrangement) so they never cross.

Features, calibration and question logic are the champion's (`ml_power.train` with this
fitter), so only the learner differs. The network competes in the weekly job (T111) and is
published as a backtest model card whatever its result.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from arena.domains.power import PowerDomain
from arena.forecasters.ml_power import QUANTILES, PowerModel, train

FAMILY = "power-mlpq"
HIDDEN = 64
EPOCHS = 400
LR = 1e-3
WEIGHT_DECAY = 1e-4


@dataclass
class QuantileNet:
    """A fitted network plus its scaling; `predict` returns sorted quantiles."""

    net: Any
    x_mean: np.ndarray
    x_std: np.ndarray
    y_mean: float
    y_std: float

    def predict_all(self, x: np.ndarray) -> np.ndarray:
        """(n, len(QUANTILES)) predictions in the target's units, sorted per row."""
        import torch

        xs = (np.asarray(x, dtype=np.float32) - self.x_mean) / self.x_std
        with torch.no_grad():
            out = self.net(torch.from_numpy(xs.astype(np.float32))).numpy()
        return np.sort(out * self.y_std + self.y_mean, axis=1)


@dataclass
class QuantileHead:
    """One quantile level of a shared network, with the scikit-learn `predict` API that
    `PowerModel.quantiles` uses."""

    shared: QuantileNet
    index: int

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Predictions of this quantile level."""
        return self.shared.predict_all(x)[:, self.index]


def _pinball(pred: Any, y: Any, taus: Any) -> Any:
    d = y.unsqueeze(1) - pred
    return (taus * d).maximum((taus - 1) * d).mean()


def fit_quantiles_torch(
    x: np.ndarray, y: np.ndarray, *, epochs: int = EPOCHS, seed: int = 0
) -> list[QuantileHead]:
    """Train one network for all levels in QUANTILES; return one head per level."""
    import torch
    from torch import nn

    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(1)
    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    x_mean, x_std = x.mean(axis=0), x.std(axis=0)
    x_std = np.where(x_std > 0, x_std, 1.0).astype(np.float32)
    y_mean, y_std = float(y.mean()), float(y.std() or 1.0)
    xt = torch.from_numpy((x - x_mean) / x_std)
    yt = torch.from_numpy((y - y_mean) / y_std)
    taus = torch.tensor(QUANTILES, dtype=torch.float32)
    net = nn.Sequential(
        nn.Linear(x.shape[1], HIDDEN),
        nn.ReLU(),
        nn.Linear(HIDDEN, HIDDEN),
        nn.ReLU(),
        nn.Linear(HIDDEN, len(QUANTILES)),
    )
    opt = torch.optim.Adam(net.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    net.train()
    for _ in range(epochs):
        opt.zero_grad()
        loss = _pinball(net(xt), yt, taus)
        loss.backward()
        opt.step()
    net.eval()
    shared = QuantileNet(net, x_mean, x_std, y_mean, y_std)
    return [QuantileHead(shared, i) for i in range(len(QUANTILES))]


def train_torch(
    domain: PowerDomain, train_end: date, *, folds: int = 2, epochs: int = EPOCHS, seed: int = 0
) -> PowerModel:
    """The power model with the quantile network as learner."""
    return train(
        domain,
        train_end,
        folds=folds,
        fitter=lambda xx, yy: fit_quantiles_torch(xx, yy, epochs=epochs, seed=seed),
        family=FAMILY,
        params={"hidden": HIDDEN, "epochs": epochs, "lr": LR, "weight_decay": WEIGHT_DECAY},
    )
