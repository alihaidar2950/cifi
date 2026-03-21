# Detailed Design (DD) — CI Failure Intelligence (CIFI)

## Purpose

This document describes the implementation-level design of each CIFI system component. It complements the HLD by going deeper into interfaces, data flows, and technology choices.

---

## 1. Webhook Receiver

### Tech
- FastAPI endpoint: `POST /api/webhook/github`
- Runs inside the existing `backend/` FastAPI app

### Responsibilities
- Receive `workflow_run` webhook events from GitHub Actions (status: failure)
- Validate GitHub HMAC signature on every request (reject unsigned/invalid with 403)
- Return 200 immediately, queue analysis job asynchronously via FastAPI `BackgroundTasks`
- Support Jenkins post-build webhook plugin (future)

### Interface
```python
@router.post("/webhook/github", status_code=200)
async def receive_github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict:
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    verify_github_signature(payload, signature)  # raises 403 on failure
    event = parse_workflow_run_event(payload)
    if event.action == "completed" and event.conclusion == "failure":
        background_tasks.add_task(analyze_failure, event)
    return {"status": "accepted"}
```

### Security
- HMAC-SHA256 signature verification using `GITHUB_WEBHOOK_SECRET` env var
- Rate limiting on the endpoint to prevent abuse
- No sensitive data logged from webhook payloads

---

## 2. Log Ingestion Engine

### Tech
- Python module: `cifi/ingestion.py`
- GitHub REST API via `PyGithub` library

### Responsibilities
- Given a failed run ID, fetch all relevant context for analysis
- Fetch only the failing step's logs, not the entire run (logs can be 50k+ lines)

### Data Fetched
| Data | Source | Purpose |
|---|---|---|
| Raw CI logs (stdout/stderr of failed steps) | GitHub Actions API | Primary error context |
| Test output (pytest results, JUnit XML) | GitHub Actions artifacts | Structured test failures |
| Git diff of triggering commit | GitHub Compare API | Code change context |
| PR title and description | GitHub Pull Request API | Intent context |
| Previous run result | GitHub Actions API | Regression detection |

### Interface
```python
@dataclass
class FailureContext:
    run_id: int
    repo: str
    branch: str
    commit_sha: str
    failed_step_logs: str
    test_output: str | None
    git_diff: str
    pr_title: str | None
    pr_description: str | None
    previous_run_passed: bool | None

async def fetch_failure_context(run_id: int, repo: str) -> FailureContext:
    ...
```

### Design Decision
Fetch only what's needed. The ingestion layer identifies the failing step and pulls only that step's logs — never the entire run output.

---

## 3. Preprocessor

### Tech
- Python module: `cifi/preprocessor.py`
- No external dependencies beyond stdlib + regex

### Responsibilities
- Strip ANSI escape codes and timestamps from raw logs
- Detect error boundaries (start/end of the actual error region)
- Extract stack traces, assertion failures, error messages
- Truncate intelligently to fit within LLM context window (priority: error region > stack trace > surrounding context)
- Build a structured context object for the LLM prompt

### Interface
```python
@dataclass
class ProcessedContext:
    error_region: str          # The core error output
    stack_trace: str | None    # Extracted stack trace
    test_failures: list[str]   # Individual test failure summaries
    git_diff_summary: str      # Truncated diff focused on changed files
    metadata: dict             # repo, branch, commit, PR info
    token_estimate: int        # Approximate token count

def preprocess(context: FailureContext, max_tokens: int = 8000) -> ProcessedContext:
    ...
```

### Design Decision
The quality of LLM output is directly proportional to the quality of input. The preprocessor is where most engineering work lives — not the LLM call itself. Garbage in → garbage out.

---

## 4. AI Analysis Pipeline

### Tech
- Python module: `cifi/analyzer.py`
- Anthropic Claude API (primary), OpenAI-compatible (swappable via `CIFI_LLM_PROVIDER` env var)
- Pydantic for output validation

### Responsibilities
- Send preprocessed context to LLM with a structured system prompt
- Parse and validate the JSON response against the output schema
- Retry with exponential backoff on transient failures
- Fall back to a "low confidence" result if LLM returns invalid output

### Prompt Structure
```
System: You are a CI failure analyst. Given pipeline logs, a git diff,
and test output, identify the root cause of the failure and suggest a fix.
Always respond in valid JSON matching the schema provided.

User: [structured context from preprocessor]
```

### Output Schema
```python
class AnalysisResult(BaseModel):
    failure_type: Literal["test_failure", "build_error", "infra_error", "timeout", "unknown"]
    confidence: Literal["high", "medium", "low"]
    root_cause: str                    # One sentence summary
    contributing_factors: list[str]
    suggested_fix: str                 # Specific actionable suggestion
    relevant_log_lines: list[str]
    recurring: bool
    similar_past_failures: list[str]   # run IDs
```

### Design Decision
Force JSON output via system prompt + response format enforcement. Never parse free-form LLM text. Always validate against the Pydantic schema before storing or routing.

---

## 5. Persistence Layer

### Tech
- PostgreSQL (shared with the FastAPI template's existing database)
- SQLAlchemy ORM + Alembic migrations

### Tables

#### `failures`
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| repo | VARCHAR | Repository full name (owner/repo) |
| run_id | BIGINT | GitHub Actions run ID |
| branch | VARCHAR | Branch that triggered the run |
| commit_sha | VARCHAR(40) | Commit SHA |
| triggered_at | TIMESTAMP | When the failure occurred |
| failure_type | VARCHAR | test_failure, build_error, etc. |
| confidence | VARCHAR | high, medium, low |
| root_cause | TEXT | One sentence summary |
| suggested_fix | TEXT | Actionable fix suggestion |
| raw_analysis_json | JSONB | Full LLM response |
| created_at | TIMESTAMP | When the record was created |

#### `failure_patterns`
| Column | Type | Description |
|---|---|---|
| id | UUID | Primary key |
| repo | VARCHAR | Repository full name |
| pattern_hash | VARCHAR(64) | SHA-256 of normalized error + failure type |
| failure_type | VARCHAR | Category of failure |
| first_seen | TIMESTAMP | First occurrence |
| last_seen | TIMESTAMP | Most recent occurrence |
| occurrence_count | INTEGER | Number of times seen |
| example_run_ids | BIGINT[] | Array of example run IDs |

### Pattern Detection
`pattern_hash` = SHA-256(normalize(error_message) + failure_type). This detects recurring failures deterministically without LLM calls for every comparison. A failure is flagged as recurring when `occurrence_count >= 3`.

---

## 6. Output Router

### Tech
- Python module: `cifi/output.py`
- GitHub REST API for PR comments
- Slack Incoming Webhook for Slack messages

### Routing Rules
| Destination | Trigger | Format |
|---|---|---|
| GitHub PR Comment | Failure on a PR branch | Markdown summary with code blocks |
| Slack Message | All failures (if configured) | Short summary + link to dashboard |
| Dashboard | All failures | Stored in DB, rendered in web UI |
| Terminal (CLI) | Manual invocation | Rich terminal output |

### PR Comment Format
```markdown
## 🔍 CIFI — CI Failure Analysis

**Failure Type**: `test_failure` | **Confidence**: `high`

**Root Cause**: The `test_user_creation` test fails because the email
validation regex was updated but the test fixture still uses an old format.

**Suggested Fix**: Update the test fixture email in `tests/conftest.py` line 42
to use a valid email format matching the new regex.

**Relevant Log Lines**:
> AssertionError: assert 'invalid' == 'valid'
> tests/test_users.py::test_user_creation FAILED

⚠️ *This failure has occurred 5 times in the last 7 days.*
```

---

## 7. MCP Server

### Tech
- Python MCP SDK
- Runs as a separate process or integrated into the FastAPI app

### Exposed Tools
```
analyze_failure(run_id: int) → AnalysisResult
    Run analysis on a specific CI run

get_failure_history(repo: str, days: int = 7) → list[FailureSummary]
    Return recent failure trends for a repo

get_recurring_patterns(repo: str) → list[PatternSummary]
    Return failures that repeat across runs

get_fix_suggestions(run_id: int) → FixSuggestion
    Return suggested fixes for a given failure
```

### Design Decision
This turns CIFI from a standalone tool into something pluggable into any AI agent workflow. It's the differentiating layer.

---

## 8. Web Dashboard

### Tech
- React (existing frontend from the FastAPI template)
- FastAPI API endpoints for data

### Views
| View | Description |
|---|---|
| Recent Failures | List of failures with root cause summaries, filterable by repo |
| Recurring Patterns | Failures seen 3+ times, grouped by pattern hash |
| Failure Rate | Per-repo failure rate over time (simple chart) |
| Failure Detail | Full analysis view with logs, diff, and LLM output |

### Design Decision
Keep genuinely simple. The value is in the data, not the UI. Resist the urge to make it a full dashboard product.

---

## 9. CLI Tool

### Tech
- Python + `typer`
- Installable via `pyproject.toml`

### Commands
```bash
cifi analyze <run_id>         # Analyze a specific failed run
cifi history <repo>           # Show recent failure history
cifi patterns <repo>          # Show recurring failure patterns
cifi status                   # Check CIFI service health
cifi watch                    # Stream live failure events
```

---

## 10. Configuration & Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `CIFI_LLM_PROVIDER` | LLM backend: `claude`, `openai`, `ollama` | `claude` |
| `CIFI_LLM_API_KEY` | API key for the LLM provider | (required) |
| `CIFI_LLM_MODEL` | Model name | `claude-sonnet-4-20250514` |
| `CIFI_LLM_BASE_URL` | Base URL for OpenAI-compatible APIs / Ollama | (provider default) |
| `GITHUB_WEBHOOK_SECRET` | HMAC secret for webhook verification | (required) |
| `GITHUB_TOKEN` | GitHub API token for fetching logs + posting comments | (required) |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | (optional) |

All secrets via env vars or K8s Secrets. Never hardcoded.

## 🚀 Future Enhancements

* Alerting system (PagerDuty/Slack simulation)
* Advanced anomaly detection
* Multi-service architecture
* Full cloud deployment
