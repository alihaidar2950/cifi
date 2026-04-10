"""Configuration via environment variables."""

import os
from dataclasses import dataclass


def _int_env(name: str, default: int) -> int:
    """Read an integer env var, raising a clear error if the value is not a valid integer."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got: {raw!r}") from None


@dataclass(frozen=True)
class Config:
    """CIFI configuration — all settings from env vars."""

    llm_provider: str = "github-models"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    max_tokens: int = 8000
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            llm_provider=os.environ.get("CIFI_LLM_PROVIDER", "github-models"),
            llm_model=os.environ.get("CIFI_LLM_MODEL", ""),
            llm_api_key=os.environ.get("CIFI_LLM_API_KEY") or os.environ.get("GITHUB_TOKEN", ""),
            llm_base_url=os.environ.get("CIFI_LLM_BASE_URL", ""),
            max_tokens=_int_env("CIFI_MAX_TOKENS", 8000),
            max_retries=_int_env("CIFI_MAX_RETRIES", 3),
        )
