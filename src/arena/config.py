"""Typed settings read from `ARENA_*` environment variables.

Secrets are only ever read from the environment and are held as `SecretStr`, so they do
not appear in `repr()`, logs or run manifests.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

PREFIX = "ARENA_"
DEFAULT_REPO_URL = "https://github.com/JASHD12/forecast-arena"


class Settings(BaseModel):
    """All runtime configuration. Field `foo_bar` is read from `ARENA_FOO_BAR`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contact: str | None = Field(None, description="Contact for the HTTP User-Agent")
    repo_url: str = DEFAULT_REPO_URL
    ledger_dir: Path = Path("_ledger")
    cache_dir: Path = Path("data_cache")
    lock_time_utc: time = time(9, 30)

    llm_provider: str | None = None
    llm_model: str | None = None
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_temperature: float = 0.0
    llm_questions_per_domain: int = Field(3, ge=0)
    llm_max_requests_per_day: int = Field(100, ge=0)
    llm_max_tokens_per_day: int = Field(400_000, ge=0)
    llm_max_output_tokens: int = Field(400, ge=1)
    agent_max_tool_calls: int = Field(4, ge=0)

    panel_csv_url: str | None = None
    domains: tuple[str, ...] = ("power",)

    @field_validator("domains", mode="before")
    @classmethod
    def _split_csv(cls, value: Any) -> Any:
        if isinstance(value, str):
            return tuple(part.strip() for part in value.split(",") if part.strip())
        return value

    @field_validator(
        "contact", "llm_provider", "llm_model", "llm_base_url", "panel_csv_url", mode="before"
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
