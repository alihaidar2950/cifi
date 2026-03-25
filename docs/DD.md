# Detailed Design (DD) — CI Failure Intelligence (CIFI)

## Purpose

This document describes the implementation-level design of each CIFI system component across both tiers. It complements the HLD by going deeper into interfaces, data flows, and technology choices.

---

## Tier 1 Components (GitHub Action)

### 1. GitHub Action Entry Point

#### Tech
- `action.yml` — GitHub Action metadata
- `action/entrypoint.py` — Python entry point
- `action/Dockerfile` — Container Action image

#### Responsibilities
- Read CI failure context from the GitHub Actions environment
- Orchestrate the analysis pipeline: ingestion → preprocessing → hybrid analysis
- Post results as a PR comment
- Optionally POST results to Tier 2 central server

#### Interface — `action.yml`
```yaml
name: 'CIFI — CI Failure Intelligence'
description: 'AI-powered CI failure analysis. Get root cause + fix suggestions on every failure.'
inputs:
  github-token:
    description: 'GitHub token for API access and PR comments'
    required: true
    default: ${{ github.token }}
  llm-provider:
    description: 'LLM provider for complex failures: github-models, claude, openai, ollama'
    required: false
    default: 'github-models'
  llm-api-key:
    description: 'API key for LLM provider (not needed for github-models)'
    required: false
  central-server-url:
    description: 'Tier 2 central server URL for aggregation (optional)'
    required: false
  central-server-token:
    description: 'JWT token for Tier 2 API auth (optional)'
    required: false
runs:
  using: 'docker'
  image: 'Dockerfile'
```

#### Entry Point Logic
```python
async def main():
    # 1. Read environment
    context = read_github_context()  # repo, run_id, pr_number, etc.

    # 2. Ingest failure data
    failure_context = ingest_local(
        workspace=os.environ["GITHUB_WORKSPACE"],
        step_outputs=read_step_outputs(),
    )

    # 3. Preprocess
    processed = preprocess(failure_context, max_tokens=8000)

    # 4. Hybrid analysis
    result = await analyze(processed)  # rules first, LLM fallback

    # 5. Post PR comment
    post_pr_comment(context.pr_number, format_comment(result))

    # 6. Optional: send to Tier 2
    if central_server_url:
        post_to_tier2(central_server_url, result)
```

---

### 2. Log Ingestion Engine

#### Tech
- Python module: `cifi/ingestion.py`
- Local filesystem access (Tier 1) + GitHub REST API (Tier 2 fallback)

#### Responsibilities
- Read CI logs from step output files and `$GITHUB_STEP_SUMMARY`
- Read source code directly from `$GITHUB_WORKSPACE` (full checkout)
- Read git diff via local `git diff HEAD~1`
- Read dependency manifests, config files, test fixtures from workspace
- For Tier 2 (remote analysis): fall back to GitHub REST API

#### Interface
```python
@dataclass
class FailureContext:
    run_id: int
    repo: str
    branch: str
    commit_sha: str
    failed_step_logs: str       # CI logs from failed step
    source_files: dict[str, str]  # relevant source code {path: content}
    test_output: str | None     # pytest/JUnit output
    git_diff: str               # diff of triggering commit
    dependency_files: dict[str, str]  # package.json, requirements.txt, etc.
    pr_title: str | None
    pr_description: str | None

def ingest_local(workspace: str, step_outputs: list[str]) -> FailureContext:
    """Tier 1: Read everything from local filesystem."""
    ...

async def ingest_remote(run_id: int, repo: str) -> FailureContext:
    """Tier 2: Fetch via GitHub REST API (less context available)."""
    ...
```

#### Source Code Context Strategy
The ingestion engine reads source files intelligently, not the entire repo:
1. Parse error messages for file paths and line numbers
2. Read those specific files from the workspace
3. Read files mentioned in the git diff
4. Read dependency manifests (`package.json`, `requirements.txt`, `pyproject.toml`)
5. Total source context capped at ~4000 tokens to leave room for logs

---

### 3. Preprocessor

#### Tech
- Python module: `cifi/preprocessor.py`
- No external dependencies beyond stdlib + regex

#### Responsibilities
- Strip ANSI escape codes and timestamps from raw logs
- Detect error boundaries (start/end of the actual error region)
- Extract stack traces, assertion failures, error messages
- Truncate intelligently to fit within LLM context window (priority: error region > stack trace > source code > diff)
- Build a structured context object for analysis

#### Interface
```python
@dataclass
class ProcessedContext:
    error_region: str          # The core error output
    stack_trace: str | None    # Extracted stack trace
    test_failures: list[str]   # Individual test failure summaries
    source_context: dict[str, str]  # Relevant source files
    git_diff_summary: str      # Truncated diff
    dependency_info: str       # Relevant dependency context
    metadata: dict             # repo, branch, commit, PR info
    token_estimate: int        # Approximate token count

def preprocess(context: FailureContext, max_tokens: int = 8000) -> ProcessedContext:
    ...
```

#### Design Decision
The quality of analysis output is directly proportional to the quality of input. The preprocessor is where most engineering work lives — not the LLM call itself.

---

### 4. Rule Engine

#### Tech
- Python module: `cifi/rules.py`
- Pure regex patterns, no external dependencies

#### Responsibilities
- Match CI log content against 50+ known failure patterns
- Return high-confidence analysis instantly without API calls
- Provide fix templates for common failures

#### Interface
```python
@dataclass
class Rule:
    id: str                    # e.g. "test_assertion_error"
    category: str              # test_failure, build_error, infra_error, config_error
    pattern: re.Pattern        # Compiled regex
    failure_type: str          # Maps to AnalysisResult.failure_type
    confidence: str            # "high" or "medium"
    root_cause_template: str   # Template with {match_groups}
    fix_template: str          # Suggested fix template

@dataclass
class RuleMatch:
    rule: Rule
    matched_text: str
    groups: dict[str, str]     # Named capture groups

class RuleEngine:
    def __init__(self, rules: list[Rule] | None = None):
        self.rules = rules or load_default_rules()

    def match(self, logs: str) -> RuleMatch | None:
        """Return the highest-confidence match, or None."""
        ...

    def match_all(self, logs: str) -> list[RuleMatch]:
        """Return all matches, sorted by confidence."""
        ...
```

#### Rule Categories (50+ rules)
| Category | Examples | Count |
|---|---|---|
| Test failures | AssertionError, ImportError, fixture not found, timeout | ~15 |
| Build errors | SyntaxError, ModuleNotFoundError, TypeScript errors, compilation failed | ~15 |
| Infrastructure | Connection refused, DNS resolution failed, disk full, OOM killed | ~10 |
| Configuration | Missing env var, invalid YAML/JSON, permission denied, file not found | ~10 |

#### Example Rules
```python
Rule(
    id="test_assertion_error",
    category="test_failure",
    pattern=re.compile(r"AssertionError: (?P<assertion>.+)"),
    failure_type="test_failure",
    confidence="high",
    root_cause_template="Test assertion failed: {assertion}",
    fix_template="Check the assertion in the failing test — the expected value may need updating.",
),
Rule(
    id="missing_dependency",
    category="build_error",
    pattern=re.compile(r"ModuleNotFoundError: No module named '(?P<module>[^']+)'"),
    failure_type="build_error",
    confidence="high",
    root_cause_template="Missing Python dependency: {module}",
    fix_template="Add '{module}' to requirements.txt or pyproject.toml and install it.",
),
```

---

### 5. Hybrid Analyzer

#### Tech
- Python module: `cifi/analyzer.py`
- Rule engine (built-in) + LLM providers (GitHub Models, Claude, OpenAI, Ollama)
- Pydantic for output validation

#### Responsibilities
- Run rule engine first — if high-confidence match, return immediately (free, instant)
- Fall back to LLM for complex or unmatched failures
- Parse and validate LLM JSON response against output schema
- Retry with exponential backoff on transient LLM failures

#### Interface
```python
class AnalysisResult(BaseModel):
    failure_type: Literal["test_failure", "build_error", "infra_error", "config_error", "timeout", "unknown"]
    confidence: Literal["high", "medium", "low"]
    root_cause: str                    # One sentence summary
    contributing_factors: list[str]
    suggested_fix: str                 # Specific actionable suggestion
    relevant_log_lines: list[str]
    analysis_method: Literal["rule_engine", "llm"]  # How was this analyzed?

async def analyze(context: ProcessedContext) -> AnalysisResult:
    """Hybrid analysis: rules first, LLM fallback."""
    # Try rule engine
    match = rule_engine.match(context.error_region)
    if match and match.rule.confidence == "high":
        return AnalysisResult(
            failure_type=match.rule.failure_type,
            confidence=match.rule.confidence,
            root_cause=match.rule.root_cause_template.format(**match.groups),
            suggested_fix=match.rule.fix_template.format(**match.groups),
            analysis_method="rule_engine",
            ...
        )

    # Fall back to LLM
    return await llm_analyze(context)
```

#### LLM Providers
```python
class LLMProvider(Protocol):
    async def analyze(self, prompt: str) -> str: ...

class GitHubModelsProvider(LLMProvider):
    """Free LLM via GitHub Models API. Uses GITHUB_TOKEN."""
    base_url = "https://models.inference.ai.azure.com"

class ClaudeProvider(LLMProvider):
    """Anthropic Claude API. Requires CIFI_LLM_API_KEY."""

class OpenAIProvider(LLMProvider):
    """OpenAI-compatible API. Supports any OpenAI-compatible endpoint."""

class OllamaProvider(LLMProvider):
    """Local Ollama instance. No data leaves the machine."""
```

#### LLM Prompt Structure
```
System: You are a CI failure analyst. Given pipeline logs, source code context,
a git diff, and test output, identify the root cause of the failure and suggest
a fix. Always respond in valid JSON matching the schema provided.

User: {preprocessed context with logs, source code, diff, metadata}
```

---

### 6. Output Router (Tier 1)

#### Tech
- Python module: `cifi/output.py`
- GitHub REST API for PR comments

#### PR Comment Format
```markdown
## 🔍 CIFI — CI Failure Analysis

**Failure Type**: `test_failure` | **Confidence**: `high` | **Method**: `rule_engine`

**Root Cause**: The `test_user_creation` test fails because the email
validation regex was updated but the test fixture still uses an old format.

**Suggested Fix**: Update the test fixture email in `tests/conftest.py` line 42
to use a valid email format matching the new regex.

**Relevant Log Lines**:
> AssertionError: assert 'invalid' == 'valid'
> tests/test_users.py::test_user_creation FAILED

⚠️ *This failure has occurred 5 times in the last 7 days.*

---
<sub>Analyzed by [CIFI](https://github.com/alihaidar2950/cifi) · Rule engine match · 0.02s</sub>
```

---

## Tier 2 Components (Central Server)

### 7. FastAPI API Server

#### Tech
- FastAPI application in `backend/`
- JWT authentication for Tier 1 → Tier 2 communication
- SQLAlchemy ORM + Alembic migrations

#### Endpoints
```python
# Receive results from Tier 1
@router.post("/api/failures", status_code=201)
async def create_failure(failure: FailureCreate, token: JWTToken) -> FailureResponse:
    ...

# Query failures
@router.get("/api/failures")
async def list_failures(repo: str | None, branch: str | None, limit: int = 50) -> list[FailureSummary]:
    ...

@router.get("/api/failures/{failure_id}")
async def get_failure(failure_id: UUID) -> FailureDetail:
    ...

# Patterns
@router.get("/api/patterns/{repo}")
async def get_patterns(repo: str) -> list[PatternSummary]:
    ...

# Health
@router.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
```

---

### 8. Persistence Layer

#### Tech
- PostgreSQL, SQLAlchemy ORM, Alembic migrations

#### Tables

##### `failures`
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
| analysis_method | VARCHAR | rule_engine or llm |
| raw_analysis_json | JSONB | Full analysis result |
| created_at | TIMESTAMP | When the record was created |

##### `failure_patterns`
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

#### Pattern Detection
`pattern_hash` = SHA-256(normalize(error_message) + failure_type). Detects recurring failures deterministically without LLM calls. Flagged as recurring when `occurrence_count >= 3`.

---

### 9. Web Dashboard

#### Tech
- React frontend
- Talks to Tier 2 FastAPI API

#### Views
| View | Description |
|---|---|
| Recent Failures | List of failures with root cause summaries, filterable by repo |
| Recurring Patterns | Failures seen 3+ times, grouped by pattern hash |
| Failure Rate | Per-repo failure rate over time (simple chart) |
| Failure Detail | Full analysis view with logs, source context, and suggested fix |

---

### 10. MCP Server

#### Tech
- Python MCP SDK
- Integrated into the Tier 2 FastAPI app

#### Exposed Tools
```python
@mcp.tool()
async def analyze_failure(run_id: int) -> AnalysisResult:
    """Run analysis on a specific CI run."""

@mcp.tool()
async def get_failure_history(repo: str, days: int = 7) -> list[FailureSummary]:
    """Return recent failure trends for a repo."""

@mcp.tool()
async def get_recurring_patterns(repo: str) -> list[PatternSummary]:
    """Return failures that repeat across runs."""

@mcp.tool()
async def get_fix_suggestions(run_id: int) -> FixSuggestion:
    """Return suggested fixes for a given failure."""
```

---

### 11. CLI Tool

#### Tech
- Python + `typer`
- Talks to Tier 2 API

#### Commands
```bash
cifi history <repo>           # Show recent failure history
cifi patterns <repo>          # Show recurring failure patterns
cifi status                   # Check central server health
```

---

## Configuration & Environment Variables

### Tier 1 (GitHub Action Inputs)
| Input | Purpose | Default |
|---|---|---|
| `github-token` | GitHub API access + PR comments | `${{ github.token }}` |
| `llm-provider` | LLM backend: `github-models`, `claude`, `openai`, `ollama` | `github-models` |
| `llm-api-key` | API key for paid LLM providers | (optional) |
| `central-server-url` | Tier 2 server URL for aggregation | (optional) |
| `central-server-token` | JWT token for Tier 2 auth | (optional) |

### Tier 2 (Environment Variables)
| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | (required) |
| `SECRET_KEY` | JWT signing key | (required) |
| `CIFI_LLM_PROVIDER` | Default LLM provider for on-demand analysis | `github-models` |
| `CIFI_LLM_API_KEY` | API key for LLM provider | (optional) |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | (optional) |

All secrets via env vars, GitHub Actions secrets, or K8s Secrets. Never hardcoded.
