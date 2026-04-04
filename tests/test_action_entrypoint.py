"""Unit tests for action/entrypoint.py"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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

    def test_comment_contains_dedup_marker(self, sample_result):
        comment = entrypoint.format_comment(sample_result, "openai/gpt-4o-mini")
        assert entrypoint._COMMENT_MARKER in comment


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

    def test_sends_correct_body(self):
        mock_client, _ = self._mock_client()
        with patch("entrypoint.httpx.Client", return_value=mock_client):
            entrypoint.post_comment("tok", "owner/repo", 7, "my comment")
        assert mock_client.post.call_args.kwargs["json"] == {"body": "my comment"}

    def test_sends_auth_header(self):
        mock_client, _ = self._mock_client()
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
        mock_client.get.return_value = MagicMock(
            status_code=200, json=MagicMock(return_value=[])
        )
        with patch("entrypoint.httpx.Client", return_value=mock_client):
            with pytest.raises(Exception, match="HTTP 403"):
                entrypoint.post_comment("tok", "owner/repo", 1, "body")


class TestFetchRunLogs:
    @pytest.mark.asyncio
    async def test_fetches_failed_job_logs(self):
        jobs_payload = {
            "jobs": [
                {"id": 101, "conclusion": "success"},
                {"id": 202, "conclusion": "failure"},
            ]
        }
        log_text = "ERROR: test failed\nAssertionError: 1 != 2"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        jobs_resp = MagicMock(status_code=200)
        jobs_resp.raise_for_status = MagicMock()
        jobs_resp.json.return_value = jobs_payload

        log_resp = MagicMock(status_code=200, text=log_text)

        mock_client.get.side_effect = [jobs_resp, log_resp]

        with patch("entrypoint.httpx.AsyncClient", return_value=mock_client):
            result = await entrypoint.fetch_run_logs("tok", "owner/repo", 123)

        assert log_text in result

    @pytest.mark.asyncio
    async def test_falls_back_to_first_job_when_no_failures(self):
        jobs_payload = {"jobs": [{"id": 101, "conclusion": "success"}]}
        log_resp_text = "some log"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        jobs_resp = MagicMock(status_code=200)
        jobs_resp.raise_for_status = MagicMock()
        jobs_resp.json.return_value = jobs_payload

        log_resp = MagicMock(status_code=200, text=log_resp_text)
        mock_client.get.side_effect = [jobs_resp, log_resp]

        with patch("entrypoint.httpx.AsyncClient", return_value=mock_client):
            result = await entrypoint.fetch_run_logs("tok", "owner/repo", 123)

        assert log_resp_text in result


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
