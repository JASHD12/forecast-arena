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
import math
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
    error: str | None = None
    evaluation_question_ids: list[str] = field(default_factory=list)


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

    @property
    def ok(self) -> bool:
        """Every requested domain completed a valid comparison and decision."""
        return bool(self.decisions) and not any(d.error for d in self.decisions)

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
    domain: Domain,
    models: Mapping[str, Any],
    first: date,
    last: date,
    *,
    errors: dict[str, str] | None = None,
    question_ids: list[str] | None = None,
) -> dict[str, tuple[float, int]]:
    """Score complete, valid candidates on the same resolved questions.

    One prediction failure disqualifies that model for the whole window, not the
    question for everyone else. The first failure identifies the model and question.
    Source/context failures propagate: no model may benefit from a broken evaluation.
    """
    ps: dict[str, list[float]] = {k: [] for k in models}
    ys: list[int] = []
    failed: dict[str, str] = {}
    b = first
    while b <= last:
        asof = datetime.combine(b, MORNING, tzinfo=UTC)
        for q in domain.generate_questions(b, asof):
            r = domain.resolve(q, FAR)
            if not isinstance(r, Resolution):
                continue
            ctx = domain.context(q, asof)
            if question_ids is not None:
                question_ids.append(q.question_id)
            for k, model in models.items():
                if k in failed:
                    continue
                try:
                    p = float(model.probability(q, ctx))
                    if not math.isfinite(p) or not 0.0 <= p <= 1.0:
                        raise ValueError(f"invalid probability {p!r}")
                    ps[k].append(p)
                except Exception as exc:
                    failed[k] = f"{q.question_id}: {type(exc).__name__}: {exc}"[:300]
            ys.append(r.outcome)
        b += timedelta(days=1)
    if errors is not None:
        errors.update(failed)
    if not ys:
        return {}
    return {k: (brier(v, ys), len(ys)) for k, v in ps.items() if k not in failed}


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
                d.error = d.reason = "domain not loaded"
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
                d.error = d.reason = "training failed for every candidate"
                continue
            try:
                current = registry.load_current(led, [name]).get(name)
            except Exception as exc:
                d.error = d.reason = f"current model load failed: {type(exc).__name__}: {exc}"[:300]
                rec.warn(f"weekly/{name}: {d.error}")
                continue
            d.current_version = current.version if current is not None else None
            models = {f"cand:{f}": m for f, m in fitted.items()}
            if current is not None:
                models["current"] = current
            errors: dict[str, str] = {}
            try:
                scores = evaluate(
                    dom, models, first, last, errors=errors, question_ids=d.evaluation_question_ids
                )
            except Exception as exc:
                d.error = d.reason = f"evaluation data failed: {type(exc).__name__}: {exc}"[:300]
                rec.warn(f"weekly/{name}: {d.error}")
                continue
            for f, m in fitted.items():
                score = scores.get(f"cand:{f}")
                error = errors.get(f"cand:{f}")
                if error:
                    rec.warn(f"weekly/{name}/{f}: prediction failed: {error}")
                d.candidates.append(
                    {
                        "family": f,
                        "version": m.version,
                        "brier": round(score[0], 6) if score else None,
                        "n": score[1] if score else 0,
                        "error": error,
                        "params": _params(m),
                    }
                )
            if "current" in errors:
                d.error = d.reason = f"current model prediction failed: {errors['current']}"
                rec.warn(f"weekly/{name}: {d.error}")
                continue
            eligible = [f for f in fitted if f"cand:{f}" in scores]
            if not eligible:
                d.error = d.reason = (
                    "prediction failed for every candidate; nothing promoted"
                    if errors
                    else "no resolved questions in the window; nothing promoted"
                )
                rec.warn(f"weekly/{name}: {d.error}")
                continue
            best = min(eligible, key=lambda f: (scores[f"cand:{f}"][0], f))
            d.best_family = best
            d.candidate_version = fitted[best].version
            d.n = scores[f"cand:{best}"][1]
            d.brier_candidate = scores[f"cand:{best}"][0]
            d.brier_current = scores["current"][0] if "current" in scores else None
            if d.brier_current is not None and d.brier_candidate > d.brier_current:
                d.reason = f"best candidate ({best}) worse than current; kept current"
                continue
            try:
                final = families[best](today - timedelta(days=LAG_DAYS))
                # Validate the refitted artifact too; its score is never used to select
                # or promote the candidate (it has seen this window during refitting).
                refit_errors: dict[str, str] = {}
                refit_ids: list[str] = []
                refit_scores = evaluate(
                    dom,
                    {"refit": final},
                    first,
                    last,
                    errors=refit_errors,
                    question_ids=refit_ids,
                )
                if "refit" not in refit_scores or refit_ids != d.evaluation_question_ids:
                    raise ValueError(refit_errors.get("refit", "refit validation set changed"))
            except Exception as exc:
                d.error = d.reason = f"refit failed validation: {type(exc).__name__}: {exc}"[:300]
                rec.warn(f"weekly/{name}: {d.error}")
                continue
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
            "ok": res.ok,
            "decisions": [asdict(x) for x in res.decisions],
            "drift": res.drift,
            "importance": {"power": res.importance},
            "shap": {"power": res.shap},
            "conformal": {"power": res.conformal},
            "quantile_diagnostics": {"power": res.quantiles},
        }
        rel = f"models/weekly/{today.isoformat()}-summary.json"
        attempt = 1
        while led.exists(rel):
            attempt += 1
            rel = f"models/weekly/{today.isoformat()}-{attempt:04d}-summary.json"
        summary["attempt"] = attempt
        led.write_raw(
            rel, (json.dumps(summary, sort_keys=True, indent=1, default=str) + "\n").encode()
        )
        if not res.ok:
            rec.count("weekly_failed_domains", sum(d.error is not None for d in res.decisions))
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
    return sorted(out, key=lambda s: (s["day"], s.get("attempt", 1)), reverse=True)
