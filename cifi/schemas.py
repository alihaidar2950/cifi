"""Pydantic models and dataclasses for CIFI analysis pipeline."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel


@dataclass
class FailureContext:
    """Raw failure context ingested from the CI environment."""

    run_id: int
    repo: str
    branch: str
    commit_sha: str
    failed_step_logs: str
    source_files: dict[str, str] = field(default_factory=dict)
    test_output: str | None = None
    git_diff: str = ""
    dependency_files: dict[str, str] = field(default_factory=dict)
    pr_title: str | None = None
    pr_description: str | None = None


@dataclass
class ProcessedContext:
    """Preprocessed context ready for LLM analysis."""

    error_region: str
    stack_trace: str | None = None
    test_failures: list[str] = field(default_factory=list)
    source_context: dict[str, str] = field(default_factory=dict)
    git_diff_summary: str = ""
    dependency_info: str = ""
    metadata: dict = field(default_factory=dict)
    token_estimate: int = 0


class AnalysisResult(BaseModel):
    """Structured LLM analysis output — validated against this schema."""

    failure_type: Literal[
        "test_failure", "build_error", "infra_error", "config_error", "timeout", "unknown"
    ]
    confidence: Literal["high", "medium", "low"]
    root_cause: str
    contributing_factors: list[str]
    suggested_fix: str
    relevant_log_lines: list[str]
