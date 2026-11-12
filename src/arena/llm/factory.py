"""Build the configured LLM client from settings (environment only, SPEC 9.1)."""

from __future__ import annotations

from arena.config import Settings
from arena.llm.client import LLMClient


def client_from_settings(settings: Settings) -> LLMClient | None:
    """The configured client, or None when provider/model/key are not all set."""
    if not settings.llm_configured:
        return None
    assert settings.llm_api_key is not None and settings.llm_model is not None
    key = settings.llm_api_key.get_secret_value()
    if settings.llm_provider == "anthropic":
        from arena.llm.anthropic_adapter import AnthropicLLM

        return AnthropicLLM(settings.llm_model, key)
    if settings.llm_provider == "openai_compatible":
        from arena.llm.openai_compatible import OpenAICompatibleLLM

        return OpenAICompatibleLLM(
            settings.llm_model,
            key,
            settings.llm_base_url or "",
            temperature=settings.llm_temperature,
        )
    raise ValueError(f"unknown ARENA_LLM_PROVIDER {settings.llm_provider!r}")
