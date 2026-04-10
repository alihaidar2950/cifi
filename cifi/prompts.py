"""Prompt engineering — system prompt, context formatting, JSON enforcement."""

from cifi.schemas import ProcessedContext

SYSTEM_PROMPT = """\
You are a CI failure analyst. Given pipeline logs, source code context, \
a git diff, and test output, identify the root cause of the failure and suggest a fix.

You MUST respond with valid JSON and nothing else. Use exactly this format:

{
  "failure_type": "<test_failure|build_error|infra_error|config_error|timeout|unknown>",
  "confidence": "<high|medium|low>",
  "root_cause": "One sentence describing the root cause",
  "contributing_factors": ["factor 1", "factor 2"],
  "suggested_fix": "Specific actionable fix suggestion",
  "relevant_log_lines": ["relevant line from the logs"]
}

Rules:
- Be specific about the root cause — reference exact files and line numbers when possible
- The suggested fix should be actionable, not generic advice
- Include the most relevant log lines that support your analysis
- Set confidence to "low" if the logs are unclear or ambiguous
- Do NOT wrap the JSON in markdown code fences — return raw JSON only"""


def build_prompt(context: ProcessedContext) -> str:
    """Build the full prompt from system prompt + preprocessed context."""
    parts = [SYSTEM_PROMPT, "\n\n--- CI FAILURE CONTEXT ---\n"]

    # Metadata
    meta = context.metadata
    parts.append(f"Repository: {meta.repo or 'unknown'}")
    parts.append(f"Branch: {meta.branch or 'unknown'}")
    parts.append(f"Commit: {meta.commit_sha or 'unknown'}")
    if meta.pr_title:
        parts.append(f"PR: {meta.pr_title}")
    parts.append("")

    # Error region (highest priority)
    parts.append("## Error Output")
    parts.append(context.error_region)
    parts.append("")

    # Stack trace
    if context.stack_trace:
        parts.append("## Stack Trace")
        parts.append(context.stack_trace)
        parts.append("")

    # Test failures
    if context.test_failures:
        parts.append("## Failed Tests")
        parts.append("\n".join(context.test_failures))
        parts.append("")

    # Source code context
    if context.source_context:
        parts.append("## Relevant Source Code")
        for path, content in context.source_context.items():
            parts.append(f"### {path}")
            parts.append(content)
        parts.append("")

    # Git diff
    if context.git_diff_summary:
        parts.append("## Git Diff (recent changes)")
        parts.append(context.git_diff_summary)
        parts.append("")

    # Dependencies
    if context.dependency_info:
        parts.append("## Dependency Info")
        parts.append(context.dependency_info)
        parts.append("")

    return "\n".join(parts)
