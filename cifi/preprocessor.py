"""Log preprocessing — strip noise, extract errors, build structured context."""

import re

from cifi.schemas import FailureContext, ProcessedContext, RunMetadata

# ANSI escape code pattern
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
# Timestamp patterns (ISO, syslog-style, GitHub Actions)
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[^\s]*\s*", re.MULTILINE)
# Common error boundary markers — all lowercase; matching uses .lower() on each line
_ERROR_MARKERS = [
    "error",
    "failed",
    "fail",
    "exception",
    "traceback (most recent call last)",
    "assertionerror",
    "typeerror",
    "valueerror",
    "keyerror",
    "attributeerror",
    "modulenotfounderror",
    "importerror",
    "syntaxerror",
    "indentationerror",
    "fatal",
    "panic",
    "npm err!",
    "cargo error",
]

# Rough chars-per-token estimate (conservative)
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return len(text) // _CHARS_PER_TOKEN


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _strip_timestamps(text: str) -> str:
    return _TIMESTAMP_RE.sub("", text)


def _clean(text: str) -> str:
    return _strip_timestamps(_strip_ansi(text))


def _extract_error_region(logs: str) -> str:
    """Extract the region around errors from logs."""
    lines = logs.splitlines()
    error_indices: list[int] = []

    for i, line in enumerate(lines):
        lower = line.lower()
        if any(marker.lower() in lower for marker in _ERROR_MARKERS):
            error_indices.append(i)

    if not error_indices:
        # No clear error markers — return last 100 lines as fallback
        return "\n".join(lines[-100:])

    # Expand around each error line with context (5 lines before, 10 after)
    selected: set[int] = set()
    for idx in error_indices:
        start = max(0, idx - 5)
        end = min(len(lines), idx + 11)
        selected.update(range(start, end))

    return "\n".join(lines[i] for i in sorted(selected))


def _extract_stack_trace(logs: str) -> str | None:
    """Extract Python-style stack traces (including the final exception line)."""
    traceback_pattern = re.compile(
        r"Traceback \(most recent call last\):\n(?:\s+.+\n)+\S[^\n]*", re.MULTILINE
    )
    matches = traceback_pattern.findall(logs)
    return "\n---\n".join(matches) if matches else None


def _extract_test_failures(logs: str) -> list[str]:
    """Extract individual test failure summaries."""
    failures: list[str] = []
    # pytest short summary line format
    for match in re.finditer(r"^(FAILED|ERROR)\s+(.+)$", logs, re.MULTILINE):
        failures.append(match.group(0))
    return failures


def _truncate_to_budget(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token budget."""
    max_chars = max_tokens * _CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def preprocess(context: FailureContext, max_tokens: int = 8000) -> ProcessedContext:
    """Preprocess raw failure context into structured LLM-ready context.

    Priority allocation (of max_tokens):
      error region:  40%
      stack trace:   20%
      source code:   25%
      git diff:      10%
      dependencies:   5%
    """
    cleaned_logs = _clean(context.failed_step_logs)

    # Extract structured pieces
    error_region = _extract_error_region(cleaned_logs)
    stack_trace = _extract_stack_trace(cleaned_logs)
    test_failures = _extract_test_failures(cleaned_logs)

    # Budget allocation
    error_budget = int(max_tokens * 0.40)
    stack_budget = int(max_tokens * 0.20)
    source_budget = int(max_tokens * 0.25)
    diff_budget = int(max_tokens * 0.10)
    dep_budget = int(max_tokens * 0.05)

    error_region = _truncate_to_budget(error_region, error_budget)
    if stack_trace:
        stack_trace = _truncate_to_budget(stack_trace, stack_budget)

    # Truncate source files to budget
    source_context: dict[str, str] = {}
    remaining = source_budget * _CHARS_PER_TOKEN
    for path, content in context.source_files.items():
        if remaining <= 0:
            break
        truncated = content[:remaining]
        source_context[path] = truncated
        remaining -= len(truncated)

    git_diff_summary = _truncate_to_budget(_clean(context.git_diff), diff_budget)

    # Dependency info — just file names and first few lines
    dep_parts: list[str] = []
    remaining = dep_budget * _CHARS_PER_TOKEN
    for path, content in context.dependency_files.items():
        if remaining <= 0:
            break
        snippet = f"--- {path} ---\n{content[:remaining]}"
        dep_parts.append(snippet)
        remaining -= len(snippet)
    dependency_info = "\n".join(dep_parts)

    metadata = RunMetadata(
        repo=context.repo,
        branch=context.branch,
        commit_sha=context.commit_sha,
        run_id=context.run_id,
        pr_title=context.pr_title,
        pr_description=context.pr_description,
    )

    return ProcessedContext(
        error_region=error_region,
        stack_trace=stack_trace,
        test_failures=test_failures,
        source_context=source_context,
        git_diff_summary=git_diff_summary,
        dependency_info=dependency_info,
        metadata=metadata,
    )
