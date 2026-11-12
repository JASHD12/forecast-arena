"""Attention backtest: base_rate and persistence (both 0.5 here) vs `ml`."""

from __future__ import annotations

from datetime import date, timedelta

from arena.backtest.harness import BacktestResult, walk_forward
from arena.domains.attention import AttentionDomain
from arena.forecasters.baselines import BaseRate, Persistence
from arena.forecasters.ml import MLForecaster
from arena.forecasters.ml_attention import AttentionModel, train

#: At batch B the newest training reference day is R = B-5: its label needs the list of
#: R+3 = B-2, the latest list published by the morning of B (X+2 00:00 UTC rule).
LABEL_LAG = 5

NOTES = (
    "ml = gradient-boosted classifier on the article's 7-day top-list trajectory, K, project "
    "and weekday; Platt calibration on out-of-fold predictions; retrained every 28 days on "
    "the previous 60 reference days whose labels were published by the batch morning.",
    "base_rate and persistence are per article (SPEC 8.1/8.2); articles rarely repeat, so "
    "both answer 0.5 here.",
    "Training labels come from top lists only (rows whose label the lists cannot decide are "
    "dropped); questions are resolved with the real per-article API.",
    "The backtest domain does not apply the 'not used in the previous 3 batches' exclusion.",
)


def run(
    domain: AttentionDomain,
    first: date,
    last: date,
    *,
    run_id: str,
    retrain_days: int = 28,
    train_days: int = 60,
) -> BacktestResult:
    """Walk-forward over batches first..last (no warm-up needed: baselines answer 0.5)."""
    state: dict[str, AttentionModel] = {}

    def refresh(domain_name: str, day: date) -> AttentionModel | None:
        if domain_name != "attention":
            return None
        cur = state.get("m")
        if cur is None or (day - cur.train_end).days > retrain_days + LABEL_LAG:
            last_ref = day - timedelta(days=LABEL_LAG)
            state["m"] = train(domain, last_ref - timedelta(days=train_days), last_ref)
            return state["m"]
        return None

    return walk_forward(
        run_id,
        domain,
        lambda h: [BaseRate(h), Persistence(h), MLForecaster({}, refresh)],
        first,
        last,
    )
