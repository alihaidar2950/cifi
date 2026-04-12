"""Tests for CIFI prompt builder."""

from cifi.prompts import SYSTEM_PROMPT, build_prompt
from cifi.schemas import ProcessedContext, RunMetadata


def test_system_prompt_contains_schema():
    assert "failure_type" in SYSTEM_PROMPT
    assert "confidence" in SYSTEM_PROMPT
    assert "root_cause" in SYSTEM_PROMPT


def test_build_prompt_includes_error_region():
    ctx = ProcessedContext(
        error_region="FATAL: connection refused",
        metadata=RunMetadata(repo="test/repo", branch="main", commit_sha="abc"),
    )
    prompt = build_prompt(ctx)
    assert "FATAL: connection refused" in prompt
    assert "test/repo" in prompt


def test_build_prompt_includes_optional_sections():
    ctx = ProcessedContext(
        error_region="error here",
        stack_trace="Traceback...",
        test_failures=["FAILED test_x"],
        source_context={"app.py": "def main(): pass"},
        git_diff_summary="diff --git",
        dependency_info="flask==3.0",
        metadata=RunMetadata(repo="r", branch="b", commit_sha="c"),
    )
    prompt = build_prompt(ctx)
    assert "## Stack Trace" in prompt
    assert "## Failed Tests" in prompt
    assert "## Relevant Source Code" in prompt
    assert "## Git Diff" in prompt
    assert "## Dependency Info" in prompt


def test_build_prompt_skips_empty_sections():
    ctx = ProcessedContext(
        error_region="error",
        metadata=RunMetadata(repo="r", branch="b", commit_sha="c"),
    )
    prompt = build_prompt(ctx)
    assert "## Stack Trace" not in prompt
    assert "## Failed Tests" not in prompt
