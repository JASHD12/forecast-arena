"""Weather domain (SPEC 7.2): station temperature, rain, frost, gusts and city duels, DWD data.

Target: Berlin calendar day D = B+1. Lock B 09:30 UTC. Resolve after D+1 06:00 UTC.
Grace 72 hours. Void when more than 2 hourly observations of D are missing.

Interpretation (DECISIONS.md, "Weather templates"):
- Daily values use the hour-ending records of the Berlin day (01:00 ... 24:00 local).
- Daily maximum = highest hourly temperature reading; daily precipitation = sum of the
  hourly totals. Both rounded half-up to 0.1 (DWD precision) before comparison.
- Observations only from DWD observation sources, never from forecasts; values filled in
  from another station count as missing.
- Templates added 2026-11-12 on the owner's request (DECISIONS.md, "More interesting
  weather questions"), before the official record: `frost_day` (daily minimum below
  0.0 °C, the DWD "Frosttag"), `gust_gt` (highest hourly maximum gust above an adaptive
  threshold, only at stations that report gusts), and the city duels `warmer_than`
  (daily maximum of A strictly above B's) and `wetter_than` (daily precipitation of A
  strictly above B's; equal amounts, including two dry days, are NO).
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

from arena.domains.base import (
    AsOfStore,
    Observation,
    is_degenerate,
    template_version_for,
    trailing_frequency,
)
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
#: Template versions: 1 = published on the batch morning, 2 = the evening before (T160).
LOCK = time(9, 30)
RESOLVE_AFTER = time(6, 0)
GRACE = timedelta(hours=72)
MAX_MISSING = 2
TMAX_WINDOW = 14
WET_WINDOW = 90
WET_MM = 1.0
FROST_WINDOW = 30
GUST_WINDOW = 14
DUEL_WINDOW = 30
#: Fixed city duels (A vs B); the order is part of the question.
DUELS: tuple[tuple[str, str], ...] = (("berlin", "munich"), ("hamburg", "frankfurt"))
DUEL_TEMPLATES = ("warmer_than", "wetter_than")
VARS = ("temperature", "precipitation", "wind_gust_speed")
SOURCE_URL = "https://api.brightsky.dev/weather"


def r1(x: float) -> float:
    """Round half-up to one decimal."""
    return float(Decimal(repr(x)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def five(x: float) -> float:
    """Round half-up to the nearest 5."""
    return float((Decimal(repr(x)) / 5).quantize(Decimal("1"), rounding=ROUND_HALF_UP) * 5)


def duel_entity(a: str, b: str) -> str:
    """Entity of a city duel."""
    return f"{a}_vs_{b}"


def template_variable(template: str) -> str:
    """The observed variable a template resolves on."""
    if template in ("wet_day", "wetter_than"):
        return "precipitation"
    if template == "gust_gt":
        return "wind_gust_speed"
    return "temperature"


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
        for var in VARS:
            v = None if var in r.fallback else getattr(r, var)
            store.add(Observation(observation_available_at(r.ts), r.ts, obs_key(city, var), v))


def add_forecast(
    store: AsOfStore, city: str, records: tuple[WxRecord, ...], fetched_at: datetime
) -> None:
    """Add MOSMIX forecast records, available from the moment they were fetched."""
    for r in records:
        if r.kind not in FORECAST_TYPES:
            continue
        for var in VARS:
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
            "tmin": r1(min(tv)),
            "precip": r1(sum(pv)),
            "hours": float(len(t)),
            "missing_t": float(len(t) - len(tv)),
            "missing_p": float(len(p) - len(pv)),
        }

    def gust(self, city: str, day: date, asof: datetime, kind: str = "obs") -> float | None:
        """Highest hourly maximum gust (km/h) of a Berlin day; None if more than 2 hours
        are missing (Berlin-Dahlem reports no gusts at all)."""
        keyf = obs_key if kind == "obs" else fc_key
        g = self._hourly(keyf(city, "wind_gust_speed"), asof, day)
        if sum(v is None for v in g) > MAX_MISSING:
            return None
        return r1(max(v for v in g if v is not None))

    def gust_history(self, city: str, asof: datetime, days: int) -> dict[date, float]:
        """Observed daily maximum gusts of the last `days` Berlin days known at `asof`."""
        today = asof.astimezone(BERLIN).date()
        out = {}
        for back in range(days + 2, 0, -1):
            d = today - timedelta(days=back)
            if observation_available_at(day_hours_ending(d)[-1]) > asof:
                continue
            v = self.gust(city, d, asof)
            if v is not None:
                out[d] = v
        return dict(sorted(out.items())[-days:])

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
        out += self._generate_v1(batch_date, target, created, lock)
        out += self._generate_events(batch_date, target, created, lock)
        out += self._generate_duels(batch_date, target, created, lock)
        return out

    def _generate_v1(self, batch_date: date, target: date, created: datetime, lock: datetime
                     ) -> list[Question]:  # fmt: skip
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

    def _generate_events(self, batch_date: date, target: date, created: datetime,
                         lock: datetime) -> list[Question]:  # fmt: skip
        """`frost_day` and `gust_gt` per station."""
        out: list[Question] = []
        for city in sorted(self.stations):
            st = self.stations[city]
            hist = self.history(city, created, FROST_WINDOW)
            if not hist or max(hist) < batch_date - timedelta(days=3):
                continue  # already reported by the v1 templates
            frost = [int(v["tmin"] < 0.0) for v in hist.values()]
            freq = trailing_frequency(frost)
            if len(frost) < FROST_WINDOW * 0.9:
                self.on_skip(f"weather/frost_day/{city}: only {len(frost)} days in window")
            elif is_degenerate(freq):
                self.on_skip(f"weather/frost_day/{city}: degenerate ({freq:.2f})")
            else:
                text = (f"Will the minimum hourly air temperature measured at DWD station "
                        f"{st.name} (id {st.station_id}) on {_fmt_day(target)} "
                        f"(Europe/Berlin day) be below 0.0 °C?")  # fmt: skip
                rule = (
                    "Lowest of the hour-ending hourly air temperature observations (2 m, "
                    "deg C, rounded to 0.1) of the Europe/Berlin day D from the DWD "
                    "observation sources of this station via Bright Sky; YES if strictly "
                    "less than 0.0 (a DWD frost day)."
                )
                out.append(self._q(batch_date, target, created, lock, "frost_day", st, text,
                                   rule, 0.0, "°C", "lt",
                                   {"degeneracy_window_days": FROST_WINDOW}, freq))  # fmt: skip
            gh = self.gust_history(city, created, GUST_WINDOW)
            if len(gh) < GUST_WINDOW - 2:
                self.on_skip(f"weather/gust_gt/{city}: only {len(gh)} days with gust data")
                continue
            thr = five(quantile(list(gh.values()), 0.5))
            freq = trailing_frequency([int(v > thr) for v in gh.values()])
            if is_degenerate(freq):
                self.on_skip(f"weather/gust_gt/{city}: degenerate ({freq:.2f})")
                continue
            text = (f"Will the highest wind gust measured at DWD station {st.name} "
                    f"(id {st.station_id}) on {_fmt_day(target)} (Europe/Berlin day) be "
                    f"above {thr:.0f} km/h?")  # fmt: skip
            rule = (
                "Highest of the hour-ending hourly maximum wind gust observations (10 m, "
                "km/h, rounded to 0.1) of the Europe/Berlin day D from the DWD observation "
                "sources of this station via Bright Sky; YES if strictly greater than the "
                "threshold."
            )
            out.append(self._q(batch_date, target, created, lock, "gust_gt", st, text, rule,
                               thr, "km/h", "gt", {"window_days": GUST_WINDOW,
                               "window_end": max(gh).isoformat(),
                               "threshold_rule": "median of observed daily maximum gusts, "
                               "rounded to 5"}, freq))  # fmt: skip
        return out

    def _generate_duels(self, batch_date: date, target: date, created: datetime,
                        lock: datetime) -> list[Question]:  # fmt: skip
        """`warmer_than` and `wetter_than` for the fixed city duels."""
        out: list[Question] = []
        for a, b in DUELS:
            if a not in self.stations or b not in self.stations:
                continue
            ha = self.history(a, created, DUEL_WINDOW)
            hb = self.history(b, created, DUEL_WINDOW)
            days = sorted(set(ha) & set(hb))
            if len(days) < DUEL_WINDOW * 0.9 or max(days) < batch_date - timedelta(days=3):
                self.on_skip(f"weather/duels/{a}-{b}: only {len(days)} common days")
                continue
            sa, sb = self.stations[a], self.stations[b]
            kinds = (
                ("warmer_than", "tmax", "maximum hourly air temperature"),
                ("wetter_than", "precip", "precipitation total"),
            )
            for template, stat, noun in kinds:
                freq = trailing_frequency([int(ha[d][stat] > hb[d][stat]) for d in days])
                if is_degenerate(freq):
                    self.on_skip(f"weather/{template}/{a}-{b}: degenerate ({freq:.2f})")
                    continue
                text = (f"Will the {noun} measured at DWD station {sa.name} "
                        f"(id {sa.station_id}) on {_fmt_day(target)} (Europe/Berlin day) be "
                        f"higher than at DWD station {sb.name} (id {sb.station_id})?")  # fmt: skip
                what = (
                    "highest hour-ending hourly air temperature (2 m, deg C)"
                    if stat == "tmax"
                    else "sum of the hour-ending hourly precipitation totals (mm)"
                )
                rule = (
                    f"For each station, the {what}, rounded to 0.1, of the Europe/Berlin day "
                    "D from its DWD observation sources via Bright Sky; YES if the first "
                    "station's value is strictly greater than the second's (equal values, "
                    "including two dry days, are NO). Void if more than 2 hourly "
                    "observations of D are missing at either station 72 hours after "
                    "resolve_after."
                )
                out.append(self._duel_q(batch_date, target, created, lock, template, sa, sb,
                                        text, rule, freq))  # fmt: skip
        return out

    def _duel_q(self, batch_date: date, target: date, created: datetime, lock: datetime,
                template: str, sa: Station, sb: Station, text: str, rule: str,
                freq: float | None) -> Question:  # fmt: skip
        entity = duel_entity(sa.city, sb.city)
        version = template_version_for(batch_date, created)
        return Question(
            question_id=question_id_for(DOMAIN, template, entity, target, version),
            domain=DOMAIN,
            template=template,
            template_version=version,
            entity=entity,
            text=text,
            batch_date=batch_date,
            target_date=target,
            created_at=created,
            lock_time=lock,
            resolve_after=datetime.combine(target + timedelta(days=1), RESOLVE_AFTER, tzinfo=UTC),
            resolution_source=(
                f"DWD stations {sa.station_id} ({sa.name}) and {sb.station_id} ({sb.name}), "
                f"hourly observations via {SOURCE_URL}"
            ),
            resolution_rule=rule,
            threshold=None,
            unit="°C" if template == "warmer_than" else "mm",
            comparator="gt",
            params={
                "city_a": sa.city,
                "city_b": sb.city,
                "station_a": sa.station_id,
                "station_b": sb.station_id,
                "degeneracy_window_days": DUEL_WINDOW,
            },
            base_rate_hint=None if freq is None else round(freq, 4),
            tags=["weather", "duel"],
        )

    def _q(self, batch_date: date, target: date, created: datetime, lock: datetime,
           template: str, st: Station, text: str, rule: str, thr: float, unit: str,
           comparator: str, params: dict[str, Any], freq: float | None) -> Question:  # fmt: skip
        common = (
            " Void if more than 2 hourly observations of D are missing for the variable "
            "72 hours after resolve_after."
        )
        version = template_version_for(batch_date, created)
        return Question(
            question_id=question_id_for(DOMAIN, template, st.city, target, version),
            domain=DOMAIN,
            template=template,
            template_version=version,
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
        """Last 14 observed days and the DWD MOSMIX forecast for D, as known at `asof`.

        The v1 templates (`tmax_gt`, `wet_day`) keep exactly their original context; the
        templates added later get extra fields (minimum temperature, gusts, both cities)."""
        if question.template in DUEL_TEMPLATES:
            a, b = str(question.params["city_a"]), str(question.params["city_b"])
            ca = self._city_context(a, question.target_date, asof, extra=True)
            cb = self._city_context(b, question.target_date, asof, extra=True)
            return {"domain": DOMAIN, "asof": asof.isoformat(), "attribution": ATTRIBUTION,
                    "city_a": ca, "city_b": cb}  # fmt: skip
        extra = question.template not in ("tmax_gt", "wet_day")
        ctx = self._city_context(question.entity, question.target_date, asof, extra=extra)
        return {"domain": DOMAIN, "asof": asof.isoformat(), "attribution": ATTRIBUTION, **ctx}

    def _city_context(self, city: str, target: date, asof: datetime, *, extra: bool
                      ) -> dict[str, Any]:  # fmt: skip
        hist = self.history(city, asof, TMAX_WINDOW)
        fc = self.daily(city, target, asof, kind="fc")
        hourly = {var: self._hourly(fc_key(city, var), asof, target)
                  for var in ("temperature", "precipitation")}  # fmt: skip
        out: dict[str, Any] = {
            "station": self.stations[city].name,
            "observed_daily": [
                {"day": d.isoformat(), "tmax": v["tmax"], "precip": v["precip"]}
                for d, v in hist.items()
            ],
            "forecast_daily": None if fc is None else {"tmax": fc["tmax"], "precip": fc["precip"]},
            "forecast_hourly": hourly,
        }
        if extra:
            gh = self.gust_history(city, asof, TMAX_WINDOW)
            for row in out["observed_daily"]:
                d = date.fromisoformat(row["day"])
                row["tmin"] = hist[d]["tmin"]
                row["gust_max"] = gh.get(d)
            if out["forecast_daily"] is not None and fc is not None:
                out["forecast_daily"]["tmin"] = fc["tmin"]
                out["forecast_daily"]["gust_max"] = self.gust(city, target, asof, kind="fc")
        return out

    # ----- resolution --------------------------------------------------------------
    def resolve(self, question: Question, now: datetime) -> Resolution | Void | None:
        """None before resolve_after or while hours are missing; Void after grace."""
        if now < question.resolve_after:
            return None
        if question.template in DUEL_TEMPLATES:
            return self._resolve_duel(question, now)
        far = datetime.max.replace(tzinfo=UTC)
        city, day = question.entity, question.target_date
        var = template_variable(question.template)
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
        if question.template in ("tmax_gt", "gust_gt"):
            value = r1(max(present))
            outcome = int(value > question.threshold)
        elif question.template == "frost_day":
            value = r1(min(present))
            outcome = int(value < question.threshold)
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

    def _resolve_duel(self, question: Question, now: datetime) -> Resolution | Void | None:
        far = datetime.max.replace(tzinfo=UTC)
        day = question.target_date
        a, b = str(question.params["city_a"]), str(question.params["city_b"])
        var = template_variable(question.template)
        ha = self._hourly(obs_key(a, var), far, day)
        hb = self._hourly(obs_key(b, var), far, day)
        ma, mb = sum(v is None for v in ha), sum(v is None for v in hb)
        if ma > MAX_MISSING or mb > MAX_MISSING:
            if now >= question.resolve_after + GRACE:
                return Void(question_id=question.question_id, reason_code="source_missing",
                            detail=f"{ma}/{mb} hourly {var} observations of {day} missing "
                                   f"at end of grace ({a}/{b})", voided_at=now)  # fmt: skip
            return None
        pa, pb = [v for v in ha if v is not None], [v for v in hb if v is not None]
        if var == "temperature":
            va, vb = r1(max(pa)), r1(max(pb))
        else:
            va, vb = r1(sum(pa)), r1(sum(pb))
        ua, sha_a = self._evidence(a, day, ha)
        ub, sha_b = self._evidence(b, day, hb)
        sha = hashlib.sha256(f"{sha_a}|{sha_b}".encode()).hexdigest()
        return Resolution(
            question_id=question.question_id,
            outcome=int(va > vb),  # type: ignore[arg-type]
            observed_value=r1(va - vb),
            resolved_at=now,
            evidence=Evidence(source_url=ua, snapshot_sha256=sha,
                              values_used={"day": day.isoformat(), "variable": var,
                                           "value_a": va, "value_b": vb, "hourly_a": ha,
                                           "hourly_b": hb, "missing_a": ma, "missing_b": mb,
                                           "source_b": ub}),
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
        if question.template in DUEL_TEMPLATES:
            a, b = str(question.params["city_a"]), str(question.params["city_b"])
            day = question.target_date
            return self._hourly(obs_key(a, str(var)), far, day) != first.evidence.values_used.get(
                "hourly_a"
            ) or self._hourly(obs_key(b, str(var)), far, day) != first.evidence.values_used.get(
                "hourly_b"
            )
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
