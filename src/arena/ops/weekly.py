"""The weekly job (SPEC 12): retrain, compare, promote by rule, model card, run summary.

Promotion rule (documented on the model cards and in docs/project/DECISIONS.md):
1. Window = the 28 batch days ending `LAG_DAYS` before today (their outcomes are known).
2. A candidate is trained with its cut-off before the window and scored on the window's
   real questions through the production question, context and resolver code. The
   current (promoted) model is scored on the same questions. The current model may have
   seen part of the window, which biases the comparison in its favour (conservative).
3. If the candidate's Brier score is not worse than the current model's, the same recipe
   is refitted with the latest outcomes, stored in the registry with its card, and
   promoted with the numbers in the promotion record. With no current model, the first
   candidate is promoted.

Each run is logged with MLflow to a SQLite file under `mlruns/` (git-ignored; no server)
when MLflow is installed, and a JSON summary is written to the ledger under
`models/weekly/` so the history is public and append-only.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from arena.clock import Clock
from arena.domains.base import Domain
from arena.domains.power import PowerDomain
from arena.forecasters import registry
from arena.ledger import Ledger
from arena.ledger.manifest import run_manifest
from arena.models import Resolution
from arena.ops.drift import power_drift
from arena.ops.explain import (
    power_conformal,
    power_importance,
    power_quantile_diagnostics,
    power_shap,
)
from arena.ops.jobs import _maybe_dry
from arena.scoring.core import brier

WINDOW_DAYS = 28
LAG_DAYS = 3
MORNING = time(5, 30)
FAR = datetime.max.replace(tzinfo=UTC)

Trainer = Callable[[date], Any]  # cut-off date -> fitted model with .version/.probability
#: Per domain either one trainer or several named candidate families (champion/challenger).
TrainerSpec = Trainer | Mapping[str, Trainer]


def _params(model: Any) -> dict[str, Any]:
    """Tuned hyperparameters of a fitted model (e.g. Optuna's best trial), JSON-safe."""
    raw = getattr(model, "params", None) or {}
    return {
        str(k): (v if isinstance(v, int | float | str | bool) else str(v))
        for k, v in sorted(raw.items())
    }


def candidate_families(spec: TrainerSpec) -> dict[str, Trainer]:
    """Named candidate trainers; a single trainer is the family "default"."""
    if isinstance(spec, Mapping):
        return dict(sorted(spec.items()))
    return {"default": spec}


@dataclass
class Decision:
    """What the weekly job decided for one domain."""

    domain: str
    window_first: date
    window_last: date
    n: int = 0
    candidate_version: str | None = None
    current_version: str | None = None
    brier_candidate: float | None = None
    brier_current: float | None = None
    promoted: str | None = None
    reason: str = ""
    best_family: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WeeklyResult:
    """All decisions of one run."""

    day: date
    decisions: list[Decision] = field(default_factory=list)
    drift: list[dict[str, Any]] = field(default_factory=list)
    importance: list[dict[str, Any]] = field(default_factory=list)
    shap: list[dict[str, Any]] = field(default_factory=list)
    conformal: list[dict[str, Any]] = field(default_factory=list)
    quantiles: list[dict[str, Any]] = field(default_factory=list)

    def lines(self) -> list[str]:
        """Printable summary."""
        out = []
        for d in self.decisions:
            bc = "-" if d.brier_candidate is None else f"{d.brier_candidate:.4f}"
            bu = "-" if d.brier_current is None else f"{d.brier_current:.4f}"
            out.append(
                f"{d.domain}: window {d.window_first}..{d.window_last}, n={d.n}, "
                f"candidate {bc} vs current {bu}: {d.reason}"
            )
            for c in d.candidates:
                b = "-" if c["brier"] is None else f"{c['brier']:.4f}"
                out.append(
                    f"  {d.domain}/{c['family']}: {b}" + (f" ({c['error']})" if c["error"] else "")
                )
        return out


def window(today: date) -> tuple[date, date]:
    """The evaluation window of batch days."""
    last = today - timedelta(days=LAG_DAYS)
    return last - timedelta(days=WINDOW_DAYS - 1), last


def evaluate(
    domain: Domain, models: Mapping[str, Any], first: date, last: date
) -> dict[str, tuple[float, int]]:
    """Brier of each model on the window's resolved questions (same questions for all)."""
    ps: dict[str, list[float]] = {k: [] for k in models}
    ys: list[int] = []
    b = first
    while b <= last:
        asof = datetime.combine(b, MORNING, tzinfo=UTC)
        for q in domain.generate_questions(b, asof):
            r = domain.resolve(q, FAR)
            if not isinstance(r, Resolution):
                continue
            ctx = domain.context(q, asof)
            try:
                probs = {k: float(m.probability(q, ctx)) for k, m in models.items()}
            except (ValueError, KeyError):
                continue
            for k, p in probs.items():
                ps[k].append(p)
            ys.append(r.outcome)
        b += timedelta(days=1)
    if not ys:
        return {}
    return {k: (brier(v, ys), len(ys)) for k, v in ps.items()}


def weekly(
    ledger: Ledger,
    clock: Clock,
    domains: Mapping[str, Domain],
    trainers: Mapping[str, TrainerSpec],
    *,
    cards: Mapping[str, Callable[[Decision], str]] | None = None,
    dry_run: bool = False,
    mlruns: Path | None = None,
    drift: bool = True,
) -> WeeklyResult:
    """Run the weekly retraining for every domain that has a trainer."""
    today = clock.now().date()
    res = WeeklyResult(today)
    first, last = window(today)
    with (
        _maybe_dry(ledger, dry_run) as led,
        run_manifest(led, "weekly", today, clock, dry_run=dry_run) as rec,
    ):
        for name, spec in sorted(trainers.items()):
            families = candidate_families(spec)
            d = Decision(name, first, last)
            res.decisions.append(d)
            dom = domains.get(name)
            if dom is None:
                d.reason = "domain not loaded"
                continue
            fitted: dict[str, Any] = {}
            for fam, trainer in families.items():
                try:
                    fitted[fam] = trainer(first - timedelta(days=1))
                except Exception as exc:
                    msg = f"training failed: {type(exc).__name__}: {exc}"[:300]
                    d.candidates.append(
                        {"family": fam, "version": None, "brier": None, "n": 0, "error": msg}
                    )
                    rec.warn(f"weekly/{name}/{fam}: {msg}")
            if not fitted:
                d.reason = "training failed for every candidate"
                continue
            current = registry.load_current(led, [name]).get(name)
            d.current_version = current.version if current is not None else None
            models = {f"cand:{f}": m for f, m in fitted.items()}
            if current is not None:
                models["current"] = current
            scores = evaluate(dom, models, first, last)
            if not scores:
                d.candidates += [
                    {
                        "family": f,
                        "version": m.version,
                        "brier": None,
                        "n": 0,
                        "error": None,
                        "params": _params(m),
                    }
                    for f, m in fitted.items()
                ]
                d.reason = "no resolved questions in the window; nothing promoted"
                continue
            for f, m in fitted.items():
                b, n = scores[f"cand:{f}"]
                d.candidates.append(
                    {
                        "family": f,
                        "version": m.version,
                        "brier": round(b, 6),
                        "n": n,
                        "error": None,
                        "params": _params(m),
                    }
                )
            best = min(fitted, key=lambda f: (scores[f"cand:{f}"][0], f))
            d.best_family = best
            d.candidate_version = fitted[best].version
            d.n = scores[f"cand:{best}"][1]
            d.brier_candidate = scores[f"cand:{best}"][0]
            d.brier_current = scores["current"][0] if "current" in scores else None
            if d.brier_current is not None and d.brier_candidate > d.brier_current:
                d.reason = f"best candidate ({best}) worse than current; kept current"
                continue
            final = families[best](today - timedelta(days=LAG_DAYS))
            card = cards[name](d) if cards and name in cards else None
            if final.version not in registry.versions(led, name):
                registry.save_model(
                    led,
                    name,
                    final,
                    created_at=clock.now(),
                    card=card,
                    meta={"evaluation": asdict(d)},
                )
            if final.version == d.current_version:
                d.reason = "refit identical to current; nothing to promote"
                continue
            why = (
                "first model"
                if d.brier_current is None
                else f"candidate {d.brier_candidate:.4f} <= current {d.brier_current:.4f}"
            )
            registry.promote(
                led,
                name,
                final.version,
                at=clock.now(),
                reason=f"{why} ({best}) on {d.n} questions, {first}..{last}",
            )
            d.promoted = final.version
            d.reason = f"promoted {final.version} ({why}; family {best})"
            rec.count(f"promoted_{name}")
        if "power" in domains and "power" in trainers and drift:
            try:
                model = registry.load_current(led, ["power"]).get("power")
                if model is not None:
                    html = None if mlruns is None else mlruns / f"drift-{today.isoformat()}.html"
                    pdom = domains["power"]
                    if isinstance(pdom, PowerDomain):
                        res.drift = power_drift(pdom, model, first, last, html)
            except Exception as exc:  # the drift report never blocks the weekly job
                rec.warn(f"weekly/drift: {type(exc).__name__}: {exc}"[:300])
            try:
                model = registry.load_current(led, ["power"]).get("power")
                pdom = domains["power"]
                if model is not None and isinstance(pdom, PowerDomain):
                    res.importance = power_importance(pdom, model, first, last)
                    res.quantiles = power_quantile_diagnostics(pdom, model, first, last)
                    res.shap = power_shap(pdom, model, first, last)
                    cal = (first - timedelta(days=WINDOW_DAYS), first - timedelta(days=1))
                    res.conformal = power_conformal(pdom, model, cal, (first, last))
            except Exception as exc:  # explainability never blocks the weekly job
                rec.warn(f"weekly/importance: {type(exc).__name__}: {exc}"[:300])
        summary = {
            "day": today.isoformat(),
            "dry_run": dry_run,
            "decisions": [asdict(x) for x in res.decisions],
            "drift": res.drift,
            "importance": {"power": res.importance},
            "shap": {"power": res.shap},
            "conformal": {"power": res.conformal},
            "quantile_diagnostics": {"power": res.quantiles},
        }
        rel = f"models/weekly/{today.isoformat()}-summary.json"
        if not led.exists(rel):
            led.write_raw(
                rel, (json.dumps(summary, sort_keys=True, indent=1, default=str) + "\n").encode()
            )
        log_mlflow(res, mlruns)
    return res


def log_mlflow(res: WeeklyResult, mlruns: Path | None) -> str | None:
    """Log the run to a SQLite-backed MLflow store, if MLflow is installed."""
    if mlruns is None:
        return None
    try:
        import mlflow
    except ImportError:
        return None
    mlruns.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri("sqlite:///" + str((mlruns / "mlflow.db").resolve()))
    mlflow.set_experiment("weekly")
    with mlflow.start_run(run_name=f"weekly-{res.day.isoformat()}") as run:
        for d in res.decisions:
            mlflow.log_param(f"{d.domain}.candidate", d.candidate_version)
            mlflow.log_param(f"{d.domain}.current", d.current_version)
            mlflow.set_tag(f"{d.domain}.decision", d.reason[:250])
            if d.brier_candidate is not None:
                mlflow.log_metric(f"{d.domain}.brier_candidate", d.brier_candidate)
            if d.brier_current is not None:
                mlflow.log_metric(f"{d.domain}.brier_current", d.brier_current)
            mlflow.log_metric(f"{d.domain}.n", d.n)
        return str(run.info.run_id)


def summaries(ledger: Ledger) -> list[dict[str, Any]]:
    """All published weekly summaries, newest first (for the experiments page)."""
    out = []
    for rel in sorted(ledger.list_files("models/weekly"), reverse=True):
        if rel.endswith("-summary.json"):
            out.append(json.loads(ledger.read_bytes(rel)))
    return out
