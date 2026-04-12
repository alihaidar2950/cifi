"""Tests for CIFI config."""

import pytest

from cifi.config import Config


def test_config_defaults():
    config = Config()
    assert config.llm_provider == "github-models"
    assert config.max_tokens == 8000
    assert config.max_retries == 3


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("CIFI_LLM_PROVIDER", "github-models")
    monkeypatch.setenv("CIFI_LLM_MODEL", "openai/gpt-4o")
    monkeypatch.setenv("CIFI_LLM_API_KEY", "ghp-test")
    monkeypatch.setenv("CIFI_MAX_TOKENS", "4000")

    config = Config.from_env()
    assert config.llm_provider == "github-models"
    assert config.llm_model == "openai/gpt-4o"
    assert config.llm_api_key == "ghp-test"
    assert config.max_tokens == 4000


def test_from_env_falls_back_to_github_token(monkeypatch):
    monkeypatch.delenv("CIFI_LLM_API_KEY", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "gha-token")
    config = Config.from_env()
    assert config.llm_api_key == "gha-token"


def test_from_env_prefers_cifi_api_key_over_github_token(monkeypatch):
    monkeypatch.setenv("CIFI_LLM_API_KEY", "explicit-key")
    monkeypatch.setenv("GITHUB_TOKEN", "gha-token")
    config = Config.from_env()
    assert config.llm_api_key == "explicit-key"


def test_from_env_invalid_max_tokens(monkeypatch):
    monkeypatch.setenv("CIFI_MAX_TOKENS", "abc")
    with pytest.raises(ValueError, match="CIFI_MAX_TOKENS must be an integer"):
        Config.from_env()


def test_from_env_invalid_max_retries(monkeypatch):
    monkeypatch.setenv("CIFI_MAX_RETRIES", "xyz")
    with pytest.raises(ValueError, match="CIFI_MAX_RETRIES must be an integer"):
        Config.from_env()
