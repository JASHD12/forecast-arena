"""Weather domain (SPEC 7.2): station maximum temperature and wet days, DWD data.

Target: Berlin calendar day D = B+1. Lock B 09:30 UTC. Resolve after D+1 06:00 UTC.
Grace 72 hours. Void when more than 2 hourly observations of D are missing.

Interpretation (DECISIONS.md, "Weather templates"):
- Daily values use the hour-ending records of the Berlin day (01:00 ... 24:00 local).
- Daily maximum = highest hourly temperature reading; daily precipitation = sum of the
  hourly totals. Both rounded half-up to 0.1 (DWD precision) before comparison.
- Observations only from DWD observation sources, never from forecasts; values filled in
  from another station count as missing.
- The MOSMIX forecast for D is stored in the as-of store at its fetch time and is part of
  the context; the morning job snapshots it under `snapshots/weather/`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from arena.domains.base import AsOfStore, Observation, is_degenerate, trailing_frequency
from arena.domains.power import quantile
from arena.models import Evidence, Question, Resolution, Void, question_id_for
from arena.sources.brightsky import (
    ATTRIBUTION,
    BERLIN,
    FORECAST_TYPES,
    OBSERVATION_TYPES,
    WxRecord,
    WxResponse,
    day_hours_ending,
    observation_available_at,
)

DOMAIN = "weather"
TEMPLATE_VERSION = 1
LOCK = time(9, 30)
RESOLVE_AFTER = time(6, 0)
GRACE = timedelta(hours=72)
MAX_MISSING = 2
TMAX_WINDOW = 14
WET_WINDOW = 90
WET_MM = 1.0
SOURCE_URL = "https://api.brightsky.dev/weather"


def r1(x: float) -> float:
    """Round half-up to one decimal."""
    return float(Decimal(repr(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def half(x: float) -> float:
    """Round half-up to the nearest 0.5."""
    return float((Decimal(repr(x)) * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2)


def obs_key(city: str, var: str) -> str:
    """Store key of an observed variable."""
    return f"obs:{city}:{var}"


def fc_key(city: str, var: str) -> str:
    """Store key of a forecast variable."""
    return f"fc:{city}:{var}"


@dataclass(frozen=True)
class Station:
    """A city and its DWD station."""

    city: str
    station_id: str
    name: str


def add_observations(store: AsOfStore, city: str, records: tuple[WxRecord, ...]) -> None:
    """Add observation records (not forecasts) stamped with the availability lag."""
    for r in records:
        if r.kind not in OBSERVATION_TYPES:
            continue
        for var in ("temperature", "precipitation"):
            v = None if var in r.fallback else getattr(r, var)
            store.add(Observation(observation_available_at(r.ts), r.ts, obs_key(city, var), v))


def add_forecast(
    store: AsOfStore, city: str, records: tuple[WxRecord, ...], fetched_at: datetime
) -> None:
    """Add MOSMIX forecast records, available from the moment they were fetched."""
    for r in records:
        if r.kind not in FORECAST_TYPES:
            continue
        for var in ("temperature", "precipitation"):
            store.add(Observation(fetched_at, r.ts, fc_key(city, var), getattr(r, var)))


def _fmt_day(d: date) -> str:
    return f"{d.strftime('%A')} {d.day} {d.strftime('%B %Y')}"


class WeatherDomain:
    """Questions about tomorrow's weather at four DWD stations."""

    name = DOMAIN

    def __init__(
        self,
        store: AsOfStore,
        stations: Mapping[str, tuple[str, str]],
        evidence: Callable[[str, date], tuple[str, str] | None] | None = None,
        on_skip: Callable[[str], None] | None = None,
    ) -> None:
        self.store = store
        self.stations = {c: Station(c, sid, name) for c, (sid, name) in stations.items()}
        self.evidence = evidence
        self.on_skip = on_skip or (lambda msg: None)
        self._maps: dict[tuple[str, datetime, int], dict[datetime, float | None]] = {}

    # ----- daily values ------------------------------------------------------------
    def _map(self, key: str, asof: datetime) -> dict[datetime, float | None]:
        ck = (key, asof, self.store.version)
        if ck not in self._maps:
            if len(self._maps) > 256:
                self._maps.clear()
            self._maps[ck] = {o.observed_at: o.value for o in self.store.series(key, asof)}
        return self._maps[ck]

    def _hourly(self, key: str, asof: datetime, day: date) -> list[float | None]:
        rows = self._map(key, asof)
        return [rows.get(ts) for ts in day_hours_ending(day)]

    def daily(self, city: str, day: date, asof: datetime, kind: str = "obs"
              ) -> dict[str, float] | None:  # fmt: skip
        """{"tmax", "precip"} for a Berlin day from data known at `asof`; None if a
        variable has more than 2 missing hours."""
        keyf = obs_key if kind == "obs" else fc_key
        t = self._hourly(keyf(city, "temperature"), asof, day)
        p = self._hourly(keyf(city, "precipitation"), asof, day)
        if sum(v is None for v in t) > MAX_MISSING or sum(v is None for v in p) > MAX_MISSING:
            return None
        tv, pv = [v for v in t if v is not None], [v for v in p if v is not None]
        return {
            "tmax": r1(max(tv)),
            "precip": r1(sum(pv)),
            "hours": float(len(t)),
            "missing_t": float(len(t) - len(tv)),
            "missing_p": float(len(p) - len(pv)),
        }

    def history(self, city: str, asof: datetime, days: int) -> dict[date, dict[str, float]]:
        """Observed daily values of the last `days` Berlin days fully available at `asof`."""
        today = asof.astimezone(BERLIN).date()
        out = {}
        for back in range(days + 2, 0, -1):
            d = today - timedelta(days=back)
            if observation_available_at(day_hours_ending(d)[-1]) > asof:
                continue
            v = self.daily(city, d, asof)
            if v is not None:
                out[d] = v
        return dict(sorted(out.items())[-days:])

    # ----- generation --------------------------------------------------------------
    def generate_questions(self, batch_date: date, asof: datetime) -> list[Question]:
        """`tmax_gt` and `wet_day` for each station; deterministic given B and the data."""
        target = batch_date + timedelta(days=1)
        lock = datetime.combine(batch_date, LOCK, tzinfo=UTC)
        created = min(asof, lock)
        out: list[Question] = []
        for city in sorted(self.stations):
            st = self.stations[city]
            hist = self.history(city, created, WET_WINDOW)
            if not hist or max(hist) < batch_date - timedelta(days=3):
                self.on_skip(f"weather/{city}: observations missing or stale")
                continue
            recent = [hist[d] for d in sorted(hist)[-TMAX_WINDOW:]]
            if len(recent) >= TMAX_WINDOW - 2:
                thr = half(quantile([v["tmax"] for v in recent], 0.5))
                freq = trailing_frequency([int(v["tmax"] > thr) for v in recent])
                if is_degenerate(freq):
                    self.on_skip(f"weather/tmax_gt/{city}: degenerate ({freq:.2f})")
                else:
                    text = (f"Will the maximum hourly air temperature measured at DWD station "
                            f"{st.name} (id {st.station_id}) on {_fmt_day(target)} "
                            f"(Europe/Berlin day) be above {thr:.1f} °C?")  # fmt: skip
                    rule = (
                        "Highest of the hour-ending hourly air temperature observations "
                        "(2 m, deg C, rounded to 0.1) of the Europe/Berlin day D from the "
                        "DWD observation sources of this station via Bright Sky; YES if "
                        "strictly greater than the threshold."
                    )
                    out.append(self._q(batch_date, target, created, lock, "tmax_gt", st, text,
                                       rule, thr, "°C", "gt", {"window_days": TMAX_WINDOW,
                                       "window_end": max(hist).isoformat(),
                                       "threshold_rule": "median of observed daily maxima, "
                                       "rounded to 0.5"}, freq))  # fmt: skip
            else:
                self.on_skip(f"weather/tmax_gt/{city}: only {len(recent)} days in window")
            wet = [int(v["precip"] >= WET_MM) for v in hist.values()]
            if len(wet) < WET_WINDOW * 0.9:
                self.on_skip(f"weather/wet_day/{city}: only {len(wet)} days in window")
                continue
            freq = trailing_frequency(wet)
            if is_degenerate(freq):
                self.on_skip(f"weather/wet_day/{city}: degenerate ({freq:.2f})")
                continue
            text = (f"Will at least {WET_MM:.1f} mm of precipitation be measured at DWD station "
                    f"{st.name} (id {st.station_id}) on {_fmt_day(target)} "
                    f"(Europe/Berlin day)?")  # fmt: skip
            rule = (
                "Sum of the hour-ending hourly precipitation totals (mm, rounded to 0.1) "
                "of the Europe/Berlin day D from the DWD observation sources of this "
                "station via Bright Sky; YES if greater than or equal to 1.0 mm."
            )
            out.append(self._q(batch_date, target, created, lock, "wet_day", st, text, rule,
                               WET_MM, "mm", "ge", {"degeneracy_window_days": WET_WINDOW},
                               freq))  # fmt: skip
        return out

    def _q(self, batch_date: date, target: date, created: datetime, lock: datetime,
           template: str, st: Station, text: str, rule: str, thr: float, unit: str,
           comparator: str, params: dict[str, Any], freq: float | None) -> Question:  # fmt: skip
        common = (
            " Void if more than 2 hourly observations of D are missing for the variable "
            "72 hours after resolve_after."
        )
        return Question(
            question_id=question_id_for(DOMAIN, template, st.city, target, TEMPLATE_VERSION),
            domain=DOMAIN,
            template=template,
            template_version=TEMPLATE_VERSION,
            entity=st.city,
            text=text,
            batch_date=batch_date,
            target_date=target,
            created_at=created,
            lock_time=lock,
            resolve_after=datetime.combine(target + timedelta(days=1), RESOLVE_AFTER, tzinfo=UTC),
            resolution_source=f"DWD station {st.station_id} ({st.name}), hourly observations "
            f"via {SOURCE_URL}?dwd_station_id={st.station_id}",
            resolution_rule=rule + common,
            threshold=thr,
            unit=unit,
            comparator=comparator,  # type: ignore[arg-type]
            params={"station_id": st.station_id, "station_name": st.name, **params},
            base_rate_hint=None if freq is None else round(freq, 4),
            tags=["numeric", "weather"],
        )

    # ----- context -----------------------------------------------------------------
    def context(self, question: Question, asof: datetime) -> dict[str, Any]:
        """Last 14 observed days and the DWD MOSMIX forecast for D, as known at `asof`."""
        city = question.entity
        hist = self.history(city, asof, TMAX_WINDOW)
        fc = self.daily(city, question.target_date, asof, kind="fc")
        hourly = {var: self._hourly(fc_key(city, var), asof, question.target_date)
                  for var in ("temperature", "precipitation")}  # fmt: skip
        return {
            "domain": DOMAIN,
            "asof": asof.isoformat(),
            "attribution": ATTRIBUTION,
            "station": self.stations[city].name,
            "observed_daily": [
                {"day": d.isoformat(), "tmax": v["tmax"], "precip": v["precip"]}
                for d, v in hist.items()
            ],
            "forecast_daily": None if fc is None else {"tmax": fc["tmax"], "precip": fc["precip"]},
            "forecast_hourly": hourly,
        }

    # ----- resolution --------------------------------------------------------------
    def resolve(self, question: Question, now: datetime) -> Resolution | Void | None:
        """None before resolve_after or while hours are missing; Void after grace."""
        if now < question.resolve_after:
            return None
        far = datetime.max.replace(tzinfo=UTC)
        city, day = question.entity, question.target_date
        var = "temperature" if question.template == "tmax_gt" else "precipitation"
        hourly = self._hourly(obs_key(city, var), far, day)
        missing = sum(v is None for v in hourly)
        if missing > MAX_MISSING:
            if now >= question.resolve_after + GRACE:
                return Void(question_id=question.question_id, reason_code="source_missing",
                            detail=f"{missing} hourly {var} observations of {day} missing "
                                   f"at end of grace", voided_at=now)  # fmt: skip
            return None
        present = [v for v in hourly if v is not None]
        assert question.threshold is not None
        if question.template == "tmax_gt":
            value = r1(max(present))
            outcome = int(value > question.threshold)
        else:
            value = r1(sum(present))
            outcome = int(value >= question.threshold)
        url, sha = self._evidence(city, day, hourly)
        return Resolution(
            question_id=question.question_id,
            outcome=outcome,  # type: ignore[arg-type]
            observed_value=value,
            resolved_at=now,
            evidence=Evidence(source_url=url, snapshot_sha256=sha,
                              values_used={"day": day.isoformat(), "variable": var,
                                           "hours": len(hourly), "missing": missing,
                                           "hourly": hourly, "value": value}),
        )  # fmt: skip

    def _evidence(self, city: str, day: date, hourly: list[float | None]) -> tuple[str, str]:
        if self.evidence is not None:
            found = self.evidence(city, day)
            if found is not None:
                return found
        blob = json.dumps({"city": city, "day": day.isoformat(), "hourly": hourly})
        return SOURCE_URL, hashlib.sha256(blob.encode()).hexdigest()

    def revised(self, question: Question, first: Resolution) -> bool:
        """True if the observations now differ from those used in the first resolution."""
        var = first.evidence.values_used.get("variable", "temperature")
        far = datetime.max.replace(tzinfo=UTC)
        now_vals = self._hourly(obs_key(question.entity, str(var)), far, question.target_date)
        return now_vals != first.evidence.values_used.get("hourly")


def weather_domain_from_responses(
    stations: Mapping[str, tuple[str, str]],
    observations: Mapping[str, WxResponse],
    forecasts: Mapping[str, WxResponse],
    fetched_at: datetime,
    on_skip: Callable[[str], None] | None = None,
) -> WeatherDomain:
    """Build a domain from fetched responses; evidence points at the observation response."""
    store = AsOfStore()
    for city, resp in observations.items():
        add_observations(store, city, resp.records)
    for city, resp in forecasts.items():
        add_forecast(store, city, resp.records, fetched_at)
    ev = {c: (r.url, r.sha256) for c, r in observations.items()}
    return WeatherDomain(store, stations, evidence=lambda c, d: ev.get(c), on_skip=on_skip)
