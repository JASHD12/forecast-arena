"""Typed settings read from `ARENA_*` environment variables.

Secrets are only ever read from the environment and are held as `SecretStr`, so they do
not appear in `repr()`, logs or run manifests.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date, time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

PREFIX = "ARENA_"
DEFAULT_REPO_URL = "https://github.com/JASHD12/forecast-arena"
DEFAULT_SITE_URL = "https://jashd12.github.io/forecast-arena/"

#: Weather cities -> (DWD station id, station name). Chosen 2026-11-12 for long, continuous
#: hourly records and a DWD MOSMIX forecast point at the same station (docs/SOURCES.md).
WEATHER_STATIONS: dict[str, tuple[str, str]] = {
    "frankfurt": ("01420", "Frankfurt/Main"),
    "berlin": ("00403", "Berlin-Dahlem (FU)"),
    "hamburg": ("01975", "Hamburg-Fuhlsbüttel"),
    "munich": ("01262", "München-Flughafen"),
}


class Settings(BaseModel):
    """All runtime configuration. Field `foo_bar` is read from `ARENA_FOO_BAR`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contact: str | None = Field(None, description="Contact for the HTTP User-Agent")
    repo_url: str = DEFAULT_REPO_URL
    site_url: str = DEFAULT_SITE_URL
    #: T143: public URL of the Streamlit dashboard; the site links to it only when set (H19).
    dashboard_url: str | None = None
    ledger_dir: Path = Path("_ledger")
    ledger_remote: str | None = Field(None, description="Git remote of the ledger branch")
    cache_dir: Path = Path("data_cache")
    lock_time_utc: time = time(9, 30)
    #: T110: the official record never starts before this date (owner decision).
    official_start_not_before: date | None = None

    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_temperature: float = 0.0
    #: Anthropic `output_config.effort` (low|medium|high|xhigh|max); unset = provider default.
    #: Thinking tokens count against `llm_max_output_tokens`, so larger models need low effort
    #: or a higher output cap.
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    llm_questions_per_domain: int = Field(3, ge=0)
    llm_max_requests_per_day: int = Field(100, ge=0)
    llm_max_tokens_per_day: int = Field(400_000, ge=0)
    llm_max_output_tokens: int = Field(400, ge=1)
    #: T190: automatic prompt caching (Anthropic); changes cost, never the answer.
    llm_cache: bool = False
    #: T190: schema-constrained answers (Anthropic structured outputs) on calls without
    #: tools; a new output contract, visible in forecaster versions. Off until evaluated.
    llm_structured: bool = False
    agent_max_tool_calls: int = Field(4, ge=0)
    #: T120: offer the agent the similar-past-questions tool (prompt v2); needs fastembed
    #: (requirements/rag.txt). Off by default; the workflows switch it on.
    agent_rag: bool = False
    #: T121: run the LangGraph agent `agent_graph` (needs requirements/graph.txt).
    agent_graph: bool = False
    #: T122: run `llm_local`, an open model on the local CPU (needs requirements/local.txt).
    llm_local: bool = False
    #: Where large model weights are cached (kept apart from the per-run data cache).
    models_dir: Path = Path("models_cache")

    panel_csv_url: str | None = None
    #: T161: published CSV of the public players' form (H15); intake is off when unset.
    players_csv_url: str | None = None
    coingecko_api_key: SecretStr | None = None
    domains: tuple[str, ...] = ("power",)

    @field_validator("domains", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator(
        "contact",
        "ledger_remote",
        "llm_provider",
        "llm_model",
        "llm_base_url",
        "llm_effort",
        "panel_csv_url",
        "players_csv_url",
        "coingecko_api_key",
        "official_start_not_before",
        "dashboard_url",
        mode="before",
    )
    @classmethod
    def _empty_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def llm_configured(self) -> bool:
        """True when a provider, a model and a key are all set."""
        return bool(self.llm_provider and self.llm_model and self.llm_api_key)

    def user_agent(self) -> str:
        """The identifying User-Agent sent to every data source."""
        who = self.contact or self.repo_url
        return f"ForecastArena/0.1 (+{self.repo_url}; {who})"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from `env` (defaults to `os.environ`); unknown ARENA_ keys fail."""
        source = os.environ if env is None else env
        values: dict[str, Any] = {}
        for key, raw in source.items():
            if not key.startswith(PREFIX):
                continue
            name = key[len(PREFIX) :].lower()
            if name not in cls.model_fields:
                raise ValueError(f"unknown setting {key}")
            values[name] = raw
        return cls(**values)
