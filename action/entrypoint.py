#!/usr/bin/env python3
"""GitHub Action entrypoint for CIFI — CI Failure Intelligence."""

import asyncio
import json
import os
import sys

import httpx

from cifi.analyzer import analyze
from cifi.config import Config
from cifi.ingestion import ingest_local
from cifi.preprocessor import preprocess
from cifi.schemas import AnalysisResult

_GITHUB_API = "https://api.github.com"
_COMMENT_MARKER = "<!-- cifi-analysis -->"


def _gh_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def format_comment(result: AnalysisResult, model: str) -> str:
    factors = "\n".join(f"- {f}" for f in result.contributing_factors)
    log_lines = "\n".join(result.relevant_log_lines)
    return (
        f"{_COMMENT_MARKER}\n"
        f"## 🤖 CIFI — CI Failure Analysis\n\n"
        f"**Failure Type:** `{result.failure_type}` | **Confidence:** `{result.confidence}`\n\n"
        f"### Root Cause\n{result.root_cause}\n\n"
        f"### Contributing Factors\n{factors}\n\n"
        f"### Suggested Fix\n{result.suggested_fix}\n\n"
        f"### Relevant Log Lines\n```\n{log_lines}\n```\n\n"
        f"---\n*Analyzed by [CIFI](https://github.com/alihaidar2950/cifi) using GitHub Models ({model})*"
    )


def get_pr_number(event_path: str) -> int | None:
    try:
        with open(event_path) as f:
            event = json.load(f)
        return event.get("pull_request", {}).get("number") or event.get("number") or None
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return None


async def fetch_run_logs(token: str, repo: str, run_id: int) -> str:
    """Fetch logs for failed jobs in this run via GitHub API."""
    headers = _gh_headers(token)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        jobs_resp = await client.get(
            f"{_GITHUB_API}/repos/{repo}/actions/runs/{run_id}/jobs",
            headers=headers,
        )
        jobs_resp.raise_for_status()
        jobs = jobs_resp.json().get("jobs", [])

        failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"] or jobs[:1]

        parts: list[str] = []
        for job in failed_jobs[:3]:
            log_resp = await client.get(
                f"{_GITHUB_API}/repos/{repo}/actions/jobs/{job['id']}/logs",
                headers=headers,
            )
            if log_resp.status_code == 200:
                parts.append(log_resp.text)

        return "\n".join(parts)


def find_existing_comment(token: str, repo: str, pr_number: int) -> int | None:
    """Return the comment ID of an existing CIFI comment, or None."""
    url = f"{_GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
    with httpx.Client() as client:
        resp = client.get(url, headers=_gh_headers(token), timeout=15)
        resp.raise_for_status()
        for comment in resp.json():
            if _COMMENT_MARKER in comment.get("body", ""):
                return comment["id"]
    return None


def post_comment(token: str, repo: str, pr_number: int, body: str) -> None:
    """Create or update the CIFI PR comment (deduplication via hidden marker)."""
    headers = _gh_headers(token)
    existing_id = find_existing_comment(token, repo, pr_number)
    with httpx.Client() as client:
        if existing_id:
            url = f"{_GITHUB_API}/repos/{repo}/issues/comments/{existing_id}"
            response = client.patch(url, json={"body": body}, headers=headers, timeout=30)
        else:
            url = f"{_GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
            response = client.post(url, json={"body": body}, headers=headers, timeout=30)
        response.raise_for_status()


def write_outputs(result: AnalysisResult) -> None:
    """Write structured outputs to $GITHUB_OUTPUT for downstream steps."""
    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if not github_output:
        return
    with open(github_output, "a") as f:
        f.write(f"failure-type={result.failure_type}\n")
        f.write(f"confidence={result.confidence}\n")
        # Escape newlines — GITHUB_OUTPUT uses newline as delimiter
        root_cause = result.root_cause.replace("\n", " ")
        f.write(f"root-cause={root_cause}\n")


async def run() -> None:
    token = os.environ.get("INPUT_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id_str = os.environ.get("GITHUB_RUN_ID", "0")
    commit_sha = os.environ.get("GITHUB_SHA", "")
    branch = os.environ.get("GITHUB_REF_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    log_file = os.environ.get("INPUT_LOG_FILE", "")
    model = os.environ.get("INPUT_MODEL", "openai/gpt-4o-mini")
    run_id = int(run_id_str) if run_id_str.isdigit() else 0

    if log_file:
        # Docker containers run with /github/workspace as workdir and only that
        # directory is volume-mounted from the runner. If an absolute path outside
        # the workspace was given (e.g. /tmp/…), try the basename under /github/workspace.
        resolved = log_file
        if not os.path.exists(resolved):
            fallback = os.path.join("/github/workspace", os.path.basename(resolved))
            if os.path.exists(fallback):
                resolved = fallback
        try:
            with open(resolved) as f:
                log_content = f.read()
        except OSError as exc:
            print(
                f"Error reading log file {log_file!r}: {exc}\n"
                "Tip: log files must be inside the workspace. Write the log to\n"
                "$GITHUB_WORKSPACE/file.log and pass log-file: file.log (relative path).",
                file=sys.stderr,
            )
            sys.exit(1)
    elif run_id and repo and token:
        print("No log file provided — fetching run logs from GitHub API...")
        log_content = await fetch_run_logs(token, repo, run_id)
        if not log_content:
            print("Error: could not fetch run logs from GitHub API.", file=sys.stderr)
            sys.exit(1)
    else:
        print(
            "Error: no log content. Set INPUT_LOG_FILE or ensure GITHUB_RUN_ID, "
            "GITHUB_REPOSITORY, and GITHUB_TOKEN are set.",
            file=sys.stderr,
        )
        sys.exit(1)

    ctx = ingest_local(
        workspace=".",
        step_logs=log_content,
        run_id=run_id,
        repo=repo,
        branch=branch,
        commit_sha=commit_sha,
    )

    config = Config(
        llm_provider="github-models",
        llm_api_key=token,
        llm_model=model,
    )

    processed = preprocess(ctx)
    result = await analyze(processed, config)
    comment = format_comment(result, model)
    write_outputs(result)

    pr_number = get_pr_number(event_path) if event_path else None
    if pr_number:
        post_comment(token, repo, pr_number, comment)
        print(f"Posted analysis to PR #{pr_number}")
    else:
        print(comment)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
