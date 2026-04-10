"""Tests for CIFI analyzer — uses mocked LLM provider."""

import json

import pytest

from cifi.analyzer import AnalysisError, analyze
from cifi.config import Config
from cifi.schemas import AnalysisResult, ProcessedContext, RunMetadata

# -- Fixtures --

VALID_RESPONSE = json.dumps(
    {
        "failure_type": "test_failure",
        "confidence": "high",
        "root_cause": "Assertion failed in test_user_creation",
        "contributing_factors": ["Outdated test fixture"],
        "suggested_fix": "Update email format in conftest.py",
        "relevant_log_lines": ["AssertionError: assert 'invalid' == 'valid'"],
    }
)

INVALID_JSON = "this is not json"

WRAPPED_RESPONSE = f"```json\n{VALID_RESPONSE}\n```"


def _make_context() -> ProcessedContext:
    return ProcessedContext(
        error_region="AssertionError: assert 'invalid' == 'valid'",
        stack_trace="Traceback...",
        test_failures=["FAILED tests/test_user.py::test_user_creation"],
        metadata=RunMetadata(repo="test/repo", branch="main", commit_sha="abc123"),
    )


class MockProvider:
    """Mock LLM provider that returns pre-defined responses."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._call_count = 0

    async def analyze(self, prompt: str) -> str:
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return self._responses[idx]


# -- Tests --


async def test_analyze_success(monkeypatch):
    """Valid JSON response → successful AnalysisResult."""
    provider = MockProvider([VALID_RESPONSE])

    monkeypatch.setattr("cifi.analyzer.create_provider", lambda _: provider)

    result = await analyze(_make_context(), Config(max_retries=1))
    assert isinstance(result, AnalysisResult)
    assert result.failure_type == "test_failure"
    assert result.confidence == "high"


async def test_analyze_strips_markdown_fences(monkeypatch):
    """LLM wraps JSON in ```json``` fences → still parses correctly."""
    provider = MockProvider([WRAPPED_RESPONSE])
    monkeypatch.setattr("cifi.analyzer.create_provider", lambda _: provider)

    result = await analyze(_make_context(), Config(max_retries=1))
    assert result.failure_type == "test_failure"


async def test_analyze_retries_on_invalid_json(monkeypatch):
    """First attempt returns bad JSON, second succeeds."""
    provider = MockProvider([INVALID_JSON, VALID_RESPONSE])
    monkeypatch.setattr("cifi.analyzer.create_provider", lambda _: provider)

    result = await analyze(_make_context(), Config(max_retries=2))
    assert result.failure_type == "test_failure"
    assert provider._call_count == 2


async def test_analyze_raises_after_max_retries(monkeypatch):
    """All attempts fail → raises AnalysisError."""
    provider = MockProvider([INVALID_JSON])
    monkeypatch.setattr("cifi.analyzer.create_provider", lambda _: provider)

    with pytest.raises(AnalysisError, match="failed after"):
        await analyze(_make_context(), Config(max_retries=2))
