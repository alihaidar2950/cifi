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
