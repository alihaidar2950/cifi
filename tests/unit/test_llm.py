"""Tests for CIFI LLM provider layer."""

import pytest

from cifi.config import Config
from cifi.llm.base import LLMProvider, create_provider
from cifi.llm.github_models import GitHubModelsProvider


def test_create_provider_github_models():
    config = Config(llm_provider="github-models", llm_api_key="test-token")
    provider = create_provider(config)
    assert isinstance(provider, GitHubModelsProvider)


def test_create_provider_unknown():
    config = Config(llm_provider="unknown")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_provider(config)


def test_provider_implements_protocol():
    provider = create_provider(Config(llm_provider="github-models", llm_api_key="test"))
    assert isinstance(provider, LLMProvider)


def test_provider_raises_on_empty_api_key():
    config = Config(llm_provider="github-models", llm_api_key="")
    with pytest.raises(ValueError, match="CIFI_LLM_API_KEY or GITHUB_TOKEN"):
        create_provider(config)


def test_provider_uses_default_model_when_none_set():
    provider = create_provider(Config(llm_provider="github-models", llm_api_key="tok"))
    assert provider.model == GitHubModelsProvider.DEFAULT_MODEL


def test_provider_uses_explicit_model():
    provider = create_provider(
        Config(llm_provider="github-models", llm_api_key="tok", llm_model="openai/gpt-4o")
    )
    assert provider.model == "openai/gpt-4o"
