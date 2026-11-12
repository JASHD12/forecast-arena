"""Ledger record schemas (SPEC section 5) and canonical JSON serialisation.

Every record carries `schema_version` and a `kind` discriminator so a JSONL file can mix
record types (forecasts with skips, resolutions with voids) and still be parsed strictly.
Run `python -m arena.models` (or `make schemas`) to re-export `docs/schemas/`.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from arena.clock import ensure_utc

SCHEMA_VERSION = 1
MAX_RATIONALE_WORDS = 80

UTCDatetime = Annotated[datetime, AfterValidator(ensure_utc)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_]*$")]

_ENTITY_RE = re.compile(r"^[A-Za-z0-9_.%~+]+$")


class Record(BaseModel):
    """Common base: immutable, no unknown fields, versioned."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[1] = SCHEMA_VERSION

    @property
    def record_id(self) -> str:
        """Identifier used for duplicate detection inside one record family."""
        raise NotImplementedError


def question_id_for(domain: str, template: str, entity: str, target: date, version: int) -> str:
    """Build the canonical question id `{domain}-{template}-{entity}-{target_date}-v{n}`."""
    return f"{domain}-{template}-{entity}-{target.isoformat()}-v{version}"


class Question(Record):
    """One concrete yes/no proposition about a target day."""

    kind: Literal["question"] = "question"
    question_id: str
    domain: Slug
    template: Slug
    template_version: int = Field(ge=1)
    entity: str
    text: str = Field(min_length=10)
    batch_date: date
    target_date: date
    created_at: UTCDatetime
    lock_time: UTCDatetime
    resolve_after: UTCDatetime
    resolution_source: str
    resolution_rule: str
    threshold: float | None
    unit: str
    comparator: Literal["gt", "ge", "lt"]
    params: dict[str, Any] = Field(default_factory=dict)
    base_rate_hint: float | None = Field(None, ge=0.0, le=1.0)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> Question:
        if not _ENTITY_RE.match(self.entity):
            raise ValueError(f"entity must be URL-safe: {self.entity!r}")
        expected = question_id_for(
            self.domain, self.template, self.entity, self.target_date, self.template_version
        )
        if self.question_id != expected:
            raise ValueError(f"question_id must be {expected!r}, got {self.question_id!r}")
        if not self.created_at <= self.lock_time <= self.resolve_after:
            raise ValueError("need created_at <= lock_time <= resolve_after")
        return self

    @property
    def record_id(self) -> str:
        return self.question_id


class Forecast(Record):
    """A forecaster's probability of YES, written before the question's lock time."""

    kind: Literal["forecast"] = "forecast"
    forecast_id: str
    question_id: str
    forecaster_id: Slug
    forecaster_version: str = Field(min_length=1)
    probability: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    created_at: UTCDatetime
    rationale: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check(self) -> Forecast:
        if self.forecast_id != f"{self.question_id}::{self.forecaster_id}":
            raise ValueError("forecast_id must be '{question_id}::{forecaster_id}'")
        if self.rationale is not None and len(self.rationale.split()) > MAX_RATIONALE_WORDS:
            raise ValueError(f"rationale longer than {MAX_RATIONALE_WORDS} words")
        return self

    @property
    def record_id(self) -> str:
        return self.forecast_id


SkipReason = Literal["not_sampled", "budget_exhausted", "parse_failure", "model_missing", "error"]


class Skip(Record):
    """A forecaster did not answer a question; the reason is recorded instead of a guess."""

    kind: Literal["skip"] = "skip"
    question_id: str
    forecaster_id: Slug
    forecaster_version: str | None = None
    reason_code: SkipReason
    detail: str = ""
    created_at: UTCDatetime

    @property
    def record_id(self) -> str:
        # Shares the forecast id space: one forecaster answers or skips a question, once.
        return f"{self.question_id}::{self.forecaster_id}"


class Evidence(BaseModel):
    """Where an outcome came from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_url: str
    snapshot_sha256: Sha256
    values_used: dict[str, Any] = Field(default_factory=dict)


class Resolution(Record):
    """The recorded outcome of a question."""

    kind: Literal["resolution"] = "resolution"
    question_id: str
    outcome: Literal[0, 1]
    observed_value: float | None
    resolved_at: UTCDatetime
    evidence: Evidence

    @property
    def record_id(self) -> str:
        return f"resolution::{self.question_id}"


VoidReason = Literal["source_missing", "source_revised", "late_lock", "ambiguous", "bug"]


class Void(Record):
    """A question withdrawn from scoring for a stated, coded reason."""

    kind: Literal["void"] = "void"
    question_id: str
    reason_code: VoidReason
    detail: str = ""
    voided_at: UTCDatetime

    @property
    def record_id(self) -> str:
        return f"void::{self.question_id}::{self.reason_code}"


class RunManifest(Record):
    """What one job run did, for audit and for summing LLM usage across a day."""

    kind: Literal["run"] = "run"
    run_id: str
    job: Slug
    batch_date: date
    status: Literal["ok", "failed"]
    code_sha: str
    package_versions: dict[str, str] = Field(default_factory=dict)
    started_at: UTCDatetime
    ended_at: UTCDatetime
    dry_run: bool = False
    counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    llm_usage: dict[str, int] = Field(default_factory=dict)
    source_availability: dict[str, UTCDatetime] = Field(default_factory=dict)
    error: str | None = None

    @property
    def record_id(self) -> str:
        return self.run_id


class BatchSeal(Record):
    """Seals the questions and forecasts files of one batch (SPEC 6)."""

    kind: Literal["batch_seal"] = "batch_seal"
    batch_date: date
    sealed_at: UTCDatetime
    files: dict[str, Sha256]

    @property
    def record_id(self) -> str:
        return f"batch::{self.batch_date.isoformat()}"


class DaySeal(Record):
    """Seals every ledger file of one day and links it to the previous seal (SPEC 6)."""

    kind: Literal["day_seal"] = "day_seal"
    day: date
    sealed_at: UTCDatetime
    files: dict[str, Sha256]
    prev_chain_sha256: Sha256
    chain_sha256: Sha256

    @property
    def record_id(self) -> str:
        return f"day::{self.day.isoformat()}"


AnyRecord = Annotated[
    Question | Forecast | Skip | Resolution | Void | RunManifest | BatchSeal | DaySeal,
    Field(discriminator="kind"),
]
_ADAPTER: TypeAdapter[Any] = TypeAdapter(AnyRecord)

ALL_MODELS: tuple[type[Record], ...] = (
    Question,
    Forecast,
    Skip,
    Resolution,
    Void,
    RunManifest,
    BatchSeal,
    DaySeal,
)


def canonical_json(record: BaseModel) -> str:
    """Serialise one record as canonical JSON: sorted keys, UTF-8, no spaces, one `\\n`."""
    payload = record.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"


def parse_record(line: str) -> Record:
    """Parse and validate one JSONL line into the right record type."""
    record: Record = _ADAPTER.validate_json(line)
    return record


def export_schemas(out_dir: Path) -> list[Path]:
    """Write one JSON Schema file per record type; return the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for model in ALL_MODELS:
        path = out_dir / f"{model.__name__}.schema.json"
        text = json.dumps(model.model_json_schema(), indent=2, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for p in export_schemas(Path(__file__).resolve().parents[2] / "docs" / "schemas"):
        print(p)
