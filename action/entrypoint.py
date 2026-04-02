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


def format_comment(result: AnalysisResult, model: str) -> str:
    factors = "\n".join(f"- {f}" for f in result.contributing_factors)
    log_lines = "\n".join(result.relevant_log_lines)
    return (
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


def post_comment(token: str, repo: str, pr_number: int, body: str) -> None:
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client() as client:
        response = client.post(url, json={"body": body}, headers=headers, timeout=30)
        response.raise_for_status()


async def run() -> None:
    token = os.environ.get("INPUT_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id_str = os.environ.get("GITHUB_RUN_ID", "0")
    commit_sha = os.environ.get("GITHUB_SHA", "")
    branch = os.environ.get("GITHUB_REF_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    log_file = os.environ.get("INPUT_LOG_FILE", "")
    model = os.environ.get("INPUT_MODEL", "openai/gpt-4o-mini")

    if log_file:
        try:
            with open(log_file) as f:
                log_content = f.read()
        except OSError as exc:
            print(f"Error reading log file {log_file!r}: {exc}", file=sys.stderr)
            sys.exit(1)
    elif not sys.stdin.isatty():
        log_content = sys.stdin.read()
    else:
        print(
            "Error: no log content. Set INPUT_LOG_FILE or pipe log content to stdin.",
            file=sys.stderr,
        )
        sys.exit(1)

    run_id = int(run_id_str) if run_id_str.isdigit() else 0

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
