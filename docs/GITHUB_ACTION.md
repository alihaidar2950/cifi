# CIFI — GitHub Action Workflow

This document covers how the CIFI GitHub Action works: the Docker container lifecycle, the execution flow inside `action/entrypoint.py`, how logs are acquired, and how to integrate it into a workflow.

---

## Action Execution Flow

```mermaid
flowchart TD
    start([Action container starts]) --> read_env["Read environment variables\nINPUT_GITHUB_TOKEN · GITHUB_REPOSITORY\nGITHUB_RUN_ID · GITHUB_SHA · GITHUB_REF_NAME\nINPUT_LOG_FILE · INPUT_MODEL"]

    read_env --> log_check{INPUT_LOG_FILE\nset?}

    log_check -->|yes| file_resolve["Resolve file path\n(workspace-relative or absolute)"]
    file_resolve --> file_exists{File exists\nat resolved path?}
    file_exists -->|yes| read_file["Read log file content"]
    file_exists -->|no| try_fallback["Try basename under\n/github/workspace/"]
    try_fallback --> fallback_exists{Fallback\nexists?}
    fallback_exists -->|yes| read_file
    fallback_exists -->|no| exit1["Exit 1: file not found\n(print tip about workspace paths)"]

    log_check -->|no| api_check{run_id AND repo\nAND token available?}
    api_check -->|yes| fetch_jobs["GET /repos/{repo}/actions/runs/{id}/jobs"]
    fetch_jobs --> filter_jobs["Filter: jobs with conclusion=failure\nFallback: first job"]
    filter_jobs --> fetch_logs["GET /repos/{repo}/actions/jobs/{id}/logs\n(up to 3 failed jobs)"]
    fetch_logs --> merge_logs["Merge log strings"]
    merge_logs --> read_file

    api_check -->|no| exit2["Exit 1: no log content available"]

    read_file --> ingest["ingest_local(workspace, step_logs, run_id, repo, branch, commit_sha)\n→ FailureContext"]
    ingest --> preprocess["preprocess(context, max_tokens=8000)\n→ ProcessedContext"]
    preprocess --> analyze["analyze(processed, config)\n→ AnalysisResult (with retry loop)"]
    analyze --> format["format_comment(result, model)\n→ Markdown string"]
    format --> write_out["write_outputs(result)\n→ $GITHUB_OUTPUT\nfailure-type · confidence · root-cause"]

    write_out --> pr_check{PR number\nfrom GITHUB_EVENT_PATH?}
    pr_check -->|yes| search_existing["GET /repos/{repo}/issues/{pr}/comments\nSearch for cifi-analysis marker"]
    search_existing --> exists{CIFI comment\nalready exists?}
    exists -->|yes| patch["PATCH /repos/{repo}/issues/comments/{id}\n(update existing)"]
    exists -->|no| post["POST /repos/{repo}/issues/{pr}/comments\n(create new)"]
    patch --> done([Done])
    post --> done
    pr_check -->|no| stdout["Print comment to stdout"] --> done
```

---

## Log Acquisition Decision Tree

There are two ways CIFI gets log content, chosen automatically:

```mermaid
flowchart LR
    trigger["CIFI Action\ntriggered"] --> q1{log-file input\nprovided?}

    q1 -->|yes| mode1["Mode 1: File Read\nFastest. Works in same job.\nFile must be in /github/workspace/"]
    q1 -->|no| q2{GITHUB_RUN_ID\n+ GITHUB_REPOSITORY\n+ token all set?}

    q2 -->|yes| mode2["Mode 2: GitHub API\nFetches logs from previous/failed jobs.\nBest for a dedicated analysis job."]
    q2 -->|no| error["Error: no log content\nExit 1"]

    mode1 --> note1["Write logs first:\ntee GITHUB_WORKSPACE/my.log\nThen: log-file: my.log"]
    mode2 --> note2["Use in a separate job:\n  needs: [test-job]\n  if: failure()"]
```

**Mode 1 (log-file)** is simpler and works in the same job. The step that fails must write its output to a file first:
```yaml
- name: Run tests
  run: pytest 2>&1 | tee $GITHUB_WORKSPACE/test-output.log
  continue-on-error: true

- uses: alihaidar2950/cifi@v1
  if: failure()
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
    log-file: test-output.log
```

**Mode 2 (API)** works across jobs. CIFI runs in its own job after the failing job:
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: pytest

  analyze:
    needs: test
    if: failure()
    runs-on: ubuntu-latest
    steps:
      - uses: alihaidar2950/cifi@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## action.yml — Inputs & Outputs

```mermaid
flowchart LR
    subgraph inputs["Inputs"]
        i1["github-token\nrequired: true\nUsed for: GitHub Models LLM + API calls"]
        i2["log-file\nrequired: false\nRelative path inside workspace"]
        i3["model\ndefault: openai/gpt-4o-mini\nAny GitHub Models model identifier"]
    end

    subgraph action["CIFI Action"]
        docker["docker://ghcr.io/alihaidar2950/cifi:v1"]
    end

    subgraph outputs["Outputs"]
        o1["failure-type\ntest_failure | build_error | infra_error | config_error | timeout | unknown"]
        o2["confidence\nhigh | medium | low"]
        o3["root-cause\nOne-line summary string"]
    end

    inputs --> action --> outputs
```

### Full action.yml

```yaml
name: CI Failure Intelligence
description: AI-powered CI failure analysis — posts structured root cause analysis as PR comments

inputs:
  github-token:
    description: GitHub token for API access and GitHub Models LLM
    required: true
  log-file:
    description: Path to a CI log file inside the workspace (relative path)
    required: false
    default: ""
  model:
    description: GitHub Models model to use
    required: false
    default: "openai/gpt-4o-mini"

outputs:
  failure-type:
    description: test_failure | build_error | infra_error | config_error | timeout | unknown
  confidence:
    description: high | medium | low
  root-cause:
    description: Root cause summary

runs:
  using: docker
  image: docker://ghcr.io/alihaidar2950/cifi:v1
  env:
    INPUT_GITHUB_TOKEN: ${{ inputs.github-token }}
    INPUT_LOG_FILE: ${{ inputs.log-file }}
    INPUT_MODEL: ${{ inputs.model }}
```

---

## Docker Container Architecture

```mermaid
flowchart TB
    subgraph img["Docker Image — ghcr.io/alihaidar2950/cifi:v1"]
        direction TB
        base["python:3.12-slim"]
        deps["pip install pydantic httpx\n(from pyproject.toml)"]
        src["cifi/ package\n(core engine)"]
        ep["/entrypoint.py\n(action/entrypoint.py)"]

        base --> deps --> src --> ep
    end

    subgraph runner["GitHub Actions Runner"]
        workspace["/github/workspace\n(repo checkout — volume mounted)"]
        token["GITHUB_TOKEN"]
        env_vars["Environment variables\nGITHUB_REPOSITORY, GITHUB_RUN_ID, etc."]
    end

    runner --> img
```

**Two-stage build** in the Dockerfile:
1. Copy `pyproject.toml` + stub `cifi/__init__.py` → `pip install` (resolves deps only; cached layer)
2. Copy real `cifi/` source → `pip install --no-deps` (installs package without re-downloading)

This keeps the image layer cache efficient — rebuilds only reinstall deps when `pyproject.toml` changes.

---

## PR Comment Format

The posted comment is idempotent. CIFI checks for a hidden HTML comment marker (`<!-- cifi-analysis -->`) and PATCHes the existing comment rather than creating a new one on re-runs.

```
<!-- cifi-analysis -->
## 🤖 CIFI — CI Failure Analysis

**Failure Type:** `test_failure` | **Confidence:** `high`

### Root Cause
AssertionError in tests/test_math.py:15 — expected 4 but got 5

### Contributing Factors
- Off-by-one error in add() function
- Missing edge case for negative numbers

### Suggested Fix
Change `return a + b + 1` to `return a + b` in math_utils.py line 3

### Relevant Log Lines
```
FAILED tests/test_math.py::test_add - AssertionError: assert 5 == 4
```

---
*Analyzed by CIFI using GitHub Models (openai/gpt-4o-mini)*
```

---

## Minimal Integration (3 lines)

```yaml
- uses: alihaidar2950/cifi@v1
  if: failure()
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

Add this as the last step in any job. When any preceding step fails, CIFI activates, analyzes the failure, and posts a comment to the PR.

---

## Using Outputs in Downstream Steps

```yaml
- uses: alihaidar2950/cifi@v1
  id: cifi
  if: failure()
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}

- name: Check analysis result
  if: failure()
  run: |
    echo "Failure type: ${{ steps.cifi.outputs.failure-type }}"
    echo "Confidence: ${{ steps.cifi.outputs.confidence }}"
    echo "Root cause: ${{ steps.cifi.outputs.root-cause }}"
```

The three outputs (`failure-type`, `confidence`, `root-cause`) are written to `$GITHUB_OUTPUT` and available as step outputs for conditional logic, notifications, or further automation.
