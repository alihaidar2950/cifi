"""Tests for CIFI preprocessor."""

from cifi.preprocessor import (
    _clean,
    _extract_error_region,
    _extract_stack_trace,
    _extract_test_failures,
    _truncate_to_budget,
    preprocess,
)
from cifi.schemas import FailureContext


def test_strip_ansi():
    text = "\x1b[31mERROR\x1b[0m: something failed"
    assert _clean(text) == "ERROR: something failed"


def test_strip_timestamps():
    text = "2024-01-15T10:30:00Z some log line"
    result = _clean(text)
    assert "some log line" in result
    assert "2024-01-15" not in result


def test_extract_error_region_with_markers():
    logs = "\n".join(
        [
            "Step 1: passed",
            "Step 2: passed",
            "ERROR: compilation failed",
            "  at src/main.py:42",
            "  missing semicolon",
            "Step 3: skipped",
        ]
    )
    region = _extract_error_region(logs)
    assert "ERROR: compilation failed" in region
    assert "missing semicolon" in region


def test_extract_error_region_fallback():
    """When no error markers found, returns last 100 lines."""
    logs = "\n".join(f"line {i}" for i in range(200))
    region = _extract_error_region(logs)
    assert "line 199" in region
    assert "line 100" in region


def test_extract_stack_trace():
    logs = """some output
Traceback (most recent call last):
  File "test.py", line 10, in test_func
    assert x == 1
AssertionError: assert 2 == 1

more output"""
    trace = _extract_stack_trace(logs)
    assert trace is not None
    assert "Traceback" in trace
    assert "AssertionError" in trace


def test_extract_stack_trace_none():
    assert _extract_stack_trace("no traceback here") is None


def test_extract_test_failures():
    logs = """
FAILED tests/test_user.py::test_create_user - AssertionError
FAILED tests/test_auth.py::test_login - ValueError
PASSED tests/test_health.py::test_ping
"""
    failures = _extract_test_failures(logs)
    assert len(failures) == 2
    assert "test_create_user" in failures[0]


def test_preprocess_full():
    ctx = FailureContext(
        run_id=1,
        repo="owner/repo",
        branch="main",
        commit_sha="abc123",
        failed_step_logs="ERROR: test failed\nFAILED tests/test_x.py::test_y",
        source_files={"src/app.py": "def main(): pass"},
        git_diff="diff --git a/src/app.py",
        dependency_files={"requirements.txt": "flask==3.0"},
    )
    processed = preprocess(ctx, max_tokens=8000)
    assert processed.error_region
    assert processed.metadata.repo == "owner/repo"
    assert "src/app.py" in processed.source_context


def test_truncate_to_budget_within_limit():
    text = "short text"
    result = _truncate_to_budget(text, 1000)
    assert result == text
    assert "... [truncated]" not in result


def test_truncate_to_budget_exceeds_limit():
    text = "x" * 10000
    result = _truncate_to_budget(text, 10)
    assert result.endswith("... [truncated]")
    assert len(result) <= 10 * 4 + len("\n... [truncated]")


def test_preprocess_token_budget_truncation():
    ctx = FailureContext(
        run_id=99,
        repo="owner/repo",
        branch="main",
        commit_sha="abc123",
        failed_step_logs="ERROR: fail\n" * 1000,
    )
    processed = preprocess(ctx, max_tokens=100)
    assert processed.error_region is not None
    assert len(processed.error_region) <= 400


def test_preprocess_metadata_pr_fields():
    ctx = FailureContext(
        run_id=1,
        repo="owner/repo",
        branch="main",
        commit_sha="abc123",
        failed_step_logs="ERROR: something failed",
        pr_title="Fix the login bug",
        pr_description="Fixes issue #42",
    )
    processed = preprocess(ctx)
    assert processed.metadata.pr_title == "Fix the login bug"
    assert processed.metadata.pr_description == "Fixes issue #42"


def test_preprocess_empty_source_files():
    ctx = FailureContext(
        run_id=1,
        repo="owner/repo",
        branch="main",
        commit_sha="abc123",
        failed_step_logs="ERROR: something failed",
        source_files={},
    )
    processed = preprocess(ctx)
    assert processed.source_context == {}


def test_preprocess_with_stack_trace_extracted():
    logs = (
        "some output\n"
        "Traceback (most recent call last):\n"
        '  File "app.py", line 5, in main\n'
        "    raise ValueError('oops')\n"
        "ValueError: oops\n"
        "more output"
    )
    ctx = FailureContext(
        run_id=1,
        repo="owner/repo",
        branch="main",
        commit_sha="abc123",
        failed_step_logs=logs,
    )
    processed = preprocess(ctx)
    assert processed.stack_trace is not None
    assert "Traceback" in processed.stack_trace


def test_extract_error_region_context_lines():
    """Context window includes lines before and after the error marker."""
    lines = [f"output line {i}" for i in range(20)]
    lines[10] = "ERROR: something broke"
    logs = "\n".join(lines)
    region = _extract_error_region(logs)
    assert "ERROR: something broke" in region
    assert "output line 9" in region   # immediately before error
    assert "output line 5" in region   # exactly 5 lines before (boundary of window)
    assert "output line 11" in region  # immediately after error


def test_preprocess_no_error_markers_fallback():
    """When logs have no error keywords, error_region falls back to last 100 lines."""
    no_error_lines = [f"output line {i}" for i in range(200)]
    ctx = FailureContext(
        run_id=1,
        repo="owner/repo",
        branch="main",
        commit_sha="abc123",
        failed_step_logs="\n".join(no_error_lines),
    )
    processed = preprocess(ctx)
    assert processed.error_region  # non-empty fallback
