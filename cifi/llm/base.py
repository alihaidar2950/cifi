"""LLM provider protocol and factory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from cifi.config import Config


@runtime_checkable
class LLMProvider(Protocol):
    """Provider-agnostic interface for LLM integration."""

    async def analyze(self, prompt: str) -> str:
        """Send prompt to LLM and return raw text response."""
        ...


def create_provider(config: Config) -> LLMProvider:
    """Factory: instantiate the right provider from config."""
    match config.llm_provider:
        case "github-models":
            from cifi.llm.github_models import GitHubModelsProvider

            return GitHubModelsProvider(config)
        case _:
            raise ValueError(f"Unknown LLM provider: {config.llm_provider!r}")
