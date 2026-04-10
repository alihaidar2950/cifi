"""Tests for CIFI schemas."""

from cifi.schemas import AnalysisResult, FailureContext, ProcessedContext


def test_failure_context_defaults():
    ctx = FailureContext(
        run_id=1,
        repo="owner/repo",
        branch="main",
        commit_sha="abc123",
        failed_step_logs="some log",
    )
    assert ctx.source_files == {}
    assert ctx.git_diff == ""
    assert ctx.dependency_files == {}
    assert ctx.pr_title is None


def test_processed_context_defaults():
    ctx = ProcessedContext(error_region="error here")
    assert ctx.stack_trace is None
    assert ctx.test_failures == []
    assert ctx.source_context == {}


def test_analysis_result_valid():
    result = AnalysisResult(
        failure_type="test_failure",
        confidence="high",
        root_cause="Test assertion failed",
        contributing_factors=["outdated fixture"],
        suggested_fix="Update the fixture data",
        relevant_log_lines=["AssertionError: expected 1, got 2"],
    )
    assert result.failure_type == "test_failure"
    assert result.confidence == "high"


def test_analysis_result_from_json():
    raw = """{
        "failure_type": "build_error",
        "confidence": "medium",
        "root_cause": "Missing import",
        "contributing_factors": ["typo in import path"],
        "suggested_fix": "Fix the import statement",
        "relevant_log_lines": ["ModuleNotFoundError: No module named 'foo'"]
    }"""
    result = AnalysisResult.model_validate_json(raw)
    assert result.failure_type == "build_error"
    assert len(result.relevant_log_lines) == 1


def test_analysis_result_rejects_invalid_type():
    import pytest

    with pytest.raises(Exception):
        AnalysisResult(
            failure_type="invalid_type",
            confidence="high",
            root_cause="x",
            contributing_factors=[],
            suggested_fix="y",
            relevant_log_lines=["some line"],
        )
