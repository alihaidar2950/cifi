"""Tests for CIFI config."""

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


def test_default_model():
    assert Config().default_model == "openai/gpt-4o-mini"


def test_explicit_model_overrides_default():
    config = Config(llm_model="openai/gpt-4o")
    assert config.default_model == "openai/gpt-4o"
