"""Tests for CIFI preprocessor."""

from cifi.preprocessor import (
    _clean,
    _extract_error_region,
    _extract_stack_trace,
    _extract_test_failures,
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
