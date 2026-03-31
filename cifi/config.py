"""Configuration via environment variables."""

import os
from dataclasses import dataclass


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
            llm_api_key=os.environ.get("CIFI_LLM_API_KEY", ""),
            llm_base_url=os.environ.get("CIFI_LLM_BASE_URL", ""),
            max_tokens=int(os.environ.get("CIFI_MAX_TOKENS", "8000")),
            max_retries=int(os.environ.get("CIFI_MAX_RETRIES", "3")),
        )

    @property
    def default_model(self) -> str:
        """Return the model name, falling back to provider default."""
        return self.llm_model or "openai/gpt-4o-mini"
