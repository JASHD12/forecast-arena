"""Price-regime clustering as a feature for tomorrow's mean price (T294, unsupervised learning).

K-means on the shape of each day's 24 hourly prices (standardised within the day) finds recurring
daily patterns, for example a midday solar dip or a flat day. `k` is chosen by silhouette on the
training years only. The experiment asks whether the regime of the last known day helps a quantile
model that already has the champion's 37 features: pinball loss of the 10%, 50% and 90% quantiles of
the next day's mean price, with and without the regime as one-hot features, on a later year, with a
paired day-block interval. It is a backtest-only study; the live champion is not touched.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import silhouette_score

from arena.forecasters.ml_power import training_rows
from arena.scoring import stats

QUANTILES = (0.1, 0.5, 0.9)


def profile(prices: list[float]) -> np.ndarray:
    """The 24-hour shape of a day: prices standardised within the day (23 or 25 hours resampled)."""
    x = np.asarray(prices, float)
    grid = np.linspace(0, len(x) - 1, 24)
    x = np.interp(grid, np.arange(len(x)), x)
    sd = x.std()
    return (x - x.mean()) / (sd if sd > 0 else 1.0)


def fit_regimes(
    daily: dict[date, list[float]], first: date, last: date, ks: tuple[int, ...] = (2, 3, 4, 5, 6)
) -> tuple[KMeans, dict[str, Any]]:
    """K-means on training-period profiles; k with the best silhouette."""
    days = [d for d in sorted(daily) if first <= d <= last]
    x = np.array([profile(daily[d]) for d in days])
    best, info = None, {}
    for k in ks:
        km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(x)
        sil = float(silhouette_score(x, km.labels_, sample_size=min(len(x), 1500), random_state=0))
        info[k] = round(sil, 4)
        if best is None or sil > info[best.n_clusters]:
            best = km
    assert best is not None
    return best, {"silhouette_by_k": info, "k": int(best.n_clusters)}


def labels(km: KMeans, daily: dict[date, list[float]]) -> dict[date, int]:
    """Regime label of every day."""
    days = sorted(daily)
    pred = km.predict(np.array([profile(daily[d]) for d in days]))
    return {d: int(c) for d, c in zip(days, pred, strict=True)}


def _onehot(targets: list[date], lab: dict[date, int], k: int) -> np.ndarray:
    out = np.zeros((len(targets), k))
    for i, t in enumerate(targets):
        out[i, lab[t - timedelta(days=1)]] = 1.0  # the regime of the last known day
    return out


def pinball(y: np.ndarray, q: np.ndarray, tau: float) -> np.ndarray:
    """Per-observation pinball loss."""
    d = y - q
    return np.maximum(tau * d, (tau - 1) * d)


def run(
    daily: dict[date, list[float]], train: tuple[date, date], test: tuple[date, date]
) -> dict[str, Any]:
    """Pinball loss of the next day's mean price with and without the regime feature."""
    km, info = fit_regimes(daily, *train)
    lab = labels(km, daily)
    k = info["k"]
    xtr, ytr, ttr = training_rows(daily, train[0] + timedelta(days=30), train[1])
    xte, yte, tte = training_rows(daily, *test)
    y_train, y_test = ytr["mean"], yte["mean"]
    variants = {
        "without_regime": (xtr, xte),
        "with_regime": (
            np.hstack([xtr, _onehot(ttr, lab, k)]),
            np.hstack([xte, _onehot(tte, lab, k)]),
        ),
    }
    loss: dict[str, np.ndarray] = {}
    for name, (a, b) in variants.items():
        total = np.zeros(len(y_test))
        for tau in QUANTILES:
            m = HistGradientBoostingRegressor(
                loss="quantile", quantile=tau, max_iter=150, random_state=0
            ).fit(a, y_train)
            total += pinball(y_test, m.predict(b), tau)
        loss[name] = total / len(QUANTILES)
    diff = loss["with_regime"] - loss["without_regime"]
    iv = stats.day_block_bootstrap([d.isoformat() for d in tte], diff.tolist())
    shares = np.bincount([lab[d] for d in sorted(daily) if train[0] <= d <= train[1]], minlength=k)
    return {
        "info": info,
        "metrics": {
            name: {"n": len(v), "pinball": round(float(np.mean(v)), 3)} for name, v in loss.items()
        },
        "paired": {"diff": iv.estimate, "lo": iv.low, "hi": iv.high, "n": iv.n, "days": iv.days},
        "regime_share_pct": [round(100 * float(s) / shares.sum(), 1) for s in shares],
    }
