"""Unit tests for action/entrypoint.py"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make the standalone action script importable
sys.path.insert(0, str(Path(__file__).parent.parent / "action"))
import entrypoint

from cifi.schemas import AnalysisResult


@pytest.fixture
def sample_result() -> AnalysisResult:
    return AnalysisResult(
        failure_type="test_failure",
        confidence="high",
        root_cause="AssertionError in test_add: expected 4, got 5",
        contributing_factors=["Off-by-one error in add()", "Missing edge case coverage"],
        suggested_fix="Fix the return value in add() to return a + b instead of a + b + 1",
        relevant_log_lines=["FAILED tests/test_math.py::test_add", "AssertionError: 4 != 5"],
    )


class TestFormatComment:
    def test_contains_failure_type(self, sample_result):
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert "`test_failure`" in comment

    def test_contains_confidence(self, sample_result):
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert "`high`" in comment

    def test_contains_root_cause(self, sample_result):
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert "AssertionError in test_add" in comment

    def test_contributing_factors_bulleted(self, sample_result):
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert "- Off-by-one error in add()" in comment
        assert "- Missing edge case coverage" in comment

    def test_contains_suggested_fix(self, sample_result):
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert "Fix the return value" in comment

    def test_log_lines_in_code_block(self, sample_result):
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert "FAILED tests/test_math.py::test_add" in comment
        assert "AssertionError: 4 != 5" in comment

    def test_model_in_footer(self, sample_result):
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert "openai/gpt-4o-mini" in comment

    def test_cifi_link_in_footer(self, sample_result):
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert "https://github.com/alihaidar2950/cifi" in comment


class TestGetPrNumber:
    def test_pull_request_event(self):
        event = {"pull_request": {"number": 42, "title": "Fix bug"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(event, f)
            path = f.name
        assert entrypoint.get_pr_number(path) == 42

    def test_issue_event_with_number(self):
        event = {"number": 17, "action": "opened"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(event, f)
            path = f.name
        assert entrypoint.get_pr_number(path) == 17

    def test_missing_file_returns_none(self):
        assert entrypoint.get_pr_number("/nonexistent/path/event.json") is None

    def test_invalid_json_returns_none(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json{{")
            path = f.name
        assert entrypoint.get_pr_number(path) is None

    def test_no_pr_key_returns_none(self):
        event = {"action": "push", "ref": "refs/heads/main"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(event, f)
            path = f.name
        assert entrypoint.get_pr_number(path) is None

    def test_pull_request_number_takes_priority(self):
        # Both pull_request.number and event.number present — PR wins
        event = {"pull_request": {"number": 99}, "number": 1}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(event, f)
            path = f.name
        assert entrypoint.get_pr_number(path) == 99


class TestPostComment:
    def test_posts_to_correct_url(self):
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("entrypoint.httpx.Client", return_value=mock_client):
            entrypoint.post_comment("tok", "owner/repo", 42, "hello")

        call_args = mock_client.post.call_args
        url = call_args[0][0]
        assert "owner/repo" in url
        assert "issues/42/comments" in url

    def test_sends_correct_body(self):
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("entrypoint.httpx.Client", return_value=mock_client):
            entrypoint.post_comment("tok", "owner/repo", 7, "my comment")

        call_kwargs = mock_client.post.call_args.kwargs
        assert call_kwargs["json"] == {"body": "my comment"}

    def test_sends_auth_header(self):
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("entrypoint.httpx.Client", return_value=mock_client):
            entrypoint.post_comment("my-secret-token", "owner/repo", 1, "body")

        headers = mock_client.post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer my-secret-token"

    def test_raises_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 403")
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response

        with patch("entrypoint.httpx.Client", return_value=mock_client):
            with pytest.raises(Exception, match="HTTP 403"):
                entrypoint.post_comment("tok", "owner/repo", 1, "body")
