"""Unit tests for action/entrypoint.py"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make the standalone action script importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "action"))
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
    def test_format_comment_structure(self, sample_result):
        """Single comprehensive check — all fields appear in the comment."""
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert entrypoint._COMMENT_MARKER in comment
        assert "`test_failure`" in comment
        assert "`high`" in comment
        assert "AssertionError in test_add" in comment
        assert "- Off-by-one error in add()" in comment
        assert "Fix the return value" in comment
        assert "FAILED tests/test_math.py::test_add" in comment
        assert "openai/gpt-4o-mini" in comment
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
    def _mock_client(self):
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client.patch.return_value = mock_response
        mock_client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[]),  # no existing comments by default
        )
        return mock_client, mock_response

    def test_creates_new_comment_when_none_exists(self):
        mock_client, _ = self._mock_client()
        with patch("entrypoint.httpx.Client", return_value=mock_client):
            entrypoint.post_comment("tok", "owner/repo", 42, "hello")
        mock_client.post.assert_called_once()
        url = mock_client.post.call_args[0][0]
        assert "issues/42/comments" in url

    def test_updates_existing_comment_when_found(self):
        mock_response = MagicMock()
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.patch.return_value = mock_response
        mock_client.get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value=[
                {"id": 999, "body": f"{entrypoint._COMMENT_MARKER}\nold content"}
            ]),
        )
        with patch("entrypoint.httpx.Client", return_value=mock_client):
            entrypoint.post_comment("tok", "owner/repo", 42, "new content")
        mock_client.patch.assert_called_once()
        url = mock_client.patch.call_args[0][0]
        assert "comments/999" in url
        mock_client.post.assert_not_called()

    def test_raises_on_http_error(self):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 403")
        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client.get.return_value = MagicMock(
            status_code=200, json=MagicMock(return_value=[])
        )
        with patch("entrypoint.httpx.Client", return_value=mock_client):
            with pytest.raises(Exception, match="HTTP 403"):
                entrypoint.post_comment("tok", "owner/repo", 1, "body")


class TestWriteOutputs:
    def test_writes_to_github_output(self, sample_result, tmp_path):
        output_file = tmp_path / "github_output"
        output_file.write_text("")
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            entrypoint.write_outputs(sample_result)
        content = output_file.read_text()
        assert "failure-type=test_failure" in content
        assert "confidence=high" in content
        assert "root-cause=" in content

    def test_no_op_when_github_output_not_set(self, sample_result):
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_OUTPUT"}
        with patch.dict(os.environ, env, clear=True):
            # Should not raise
            entrypoint.write_outputs(sample_result)
