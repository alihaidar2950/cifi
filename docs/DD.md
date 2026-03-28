# Detailed Design (DD) — CI Failure Intelligence (CIFI)

## Purpose

This document describes the implementation-level design of each CIFI system component. It complements the HLD by going deeper into interfaces, data flows, and technology choices. The core AI engineering lives in the hybrid analyzer and multi-provider LLM integration.

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
- Optionally POST results to Tier 2 API

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

    # 6. Optional: send to API
    if api_url:
        post_to_api(api_url, result)
```

---

### 2. Log Ingestion Engine

#### Tech
- Python module: `cifi/ingestion.py`
- Local filesystem access (Tier 1)

#### Responsibilities
- Read CI logs from step output files and `$GITHUB_STEP_SUMMARY`
- Read source code directly from `$GITHUB_WORKSPACE` (full checkout)
- Read git diff via local `git diff HEAD~1`
- Read dependency manifests, config files, test fixtures from workspace

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
The quality of analysis output is directly proportional to the quality of input. The preprocessor is where most engineering work lives — not the LLM call itself. This is a key AI engineering insight: the preprocessing pipeline matters more than the model choice.

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
- Rule engine (built-in) + multi-provider LLM integration
- Pydantic for output validation

#### Responsibilities
- Run rule engine first — if high-confidence match, return immediately (free, instant)
- Fall back to LLM for complex or unmatched failures
- Parse and validate LLM JSON response against output schema
- Retry with exponential backoff on transient LLM failures or validation errors

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

#### Multi-Provider LLM Architecture
```python
class LLMProvider(Protocol):
    """Provider-agnostic interface for LLM integration."""
    async def analyze(self, prompt: str) -> str: ...

class GitHubModelsProvider(LLMProvider):
    """Free LLM via GitHub Models API. Uses GITHUB_TOKEN. Zero config."""
    base_url = "https://models.inference.ai.azure.com"

class ClaudeProvider(LLMProvider):
    """Anthropic Claude API. Higher quality analysis."""

class OpenAIProvider(LLMProvider):
    """OpenAI-compatible API. Supports any OpenAI-compatible endpoint."""

class OllamaProvider(LLMProvider):
    """Local Ollama instance. No data leaves the machine. Privacy-first."""
```

This protocol-based design is a key AI engineering pattern: it decouples the analysis logic from the LLM vendor, making the system extensible and testable.

#### Prompt Engineering
```python
# System prompt — defines role, output format, domain expertise
SYSTEM_PROMPT = """You are a CI failure analyst. Given pipeline logs, source code context,
a git diff, and test output, identify the root cause of the failure and suggest a fix.

Always respond in valid JSON matching this schema:
{schema}

Rules:
- Be specific about the root cause — reference exact files and line numbers
- The suggested fix should be actionable, not generic advice
- Include the most relevant log lines that support your analysis
- Set confidence to "low" if you're uncertain
"""

# Context window management — intelligent truncation
def build_prompt(context: ProcessedContext, max_tokens: int = 8000) -> str:
    """Build LLM prompt with intelligent context prioritization."""
    # Priority: error region > stack trace > source code > diff
    ...
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

---
<sub>Analyzed by [CIFI](https://github.com/alihaidar2950/cifi) · Rule engine match · 0.02s</sub>
```

---

## Tier 2 — Lightweight API

### 7. API Service (Phase 3)

#### Tech
- FastAPI application in `backend/`
- Docker container, deployable to any platform
- Minimal endpoints — same hybrid analyzer, different interface

#### Endpoints
```python
@router.get("/api/health")
async def health() -> dict:
    """Health check for deployment platform."""
    return {"status": "ok"}

@router.post("/api/analyze")
async def analyze_logs(payload: AnalyzeRequest) -> AnalysisResult:
    """Accept a log payload, run hybrid analyzer, return result."""
    context = preprocess(payload.logs, payload.source_files)
    return await analyze(context)
```

#### Deployment
```
Docker container → Fly.io / Railway / Cloud Run
├── Dockerfile (multi-stage build)
├── docker-compose.yml (local dev)
├── .github/workflows/deploy.yml (CI/CD: test → build → deploy)
└── Environment variables for LLM provider config
```

No Terraform modules. No Kubernetes manifests. No Kustomize overlays. The AI engine is the product — deploy it simply.

---

## Deferred Component Designs (Future)

The following are documented for future reference. They are not part of the current build plan.

<details>
<summary>Click to expand deferred component designs</summary>

### Deep Infrastructure (EKS + Terraform)
If targeting platform/infra roles specifically:
- Terraform modules: VPC/subnets, EKS cluster, ECR, RDS
- Kustomize overlays: base + dev/prod
- Prometheus + Grafana observability
- HPA, Sealed Secrets, IAM policies

### Full API Server (replaces minimal API)
- `POST /api/failures` — receive and store results from Tier 1 (JWT auth)
- `GET /api/failures` — list failures (filterable by repo, branch, date range)
- `GET /api/failures/{id}` — single failure detail
- `GET /api/patterns/{repo}` — recurring failure patterns
- SQLAlchemy ORM + Alembic migrations, `failures` and `failure_patterns` tables

### Web Dashboard
- React frontend: recent failures, recurring patterns, per-repo failure rate chart, failure detail view

### MCP Server
- `analyze_failure(run_id)`, `get_failure_history(repo, days)`, `get_recurring_patterns(repo)`, `get_fix_suggestions(run_id)`

### CLI Tool
- `cifi history <repo>`, `cifi patterns <repo>`, `cifi status` — Python + typer

### Slack Integration
- Failure summaries posted to Slack channels via incoming webhook

</details>

---

## Configuration & Environment Variables

### Tier 1 (GitHub Action Inputs)
| Input | Purpose | Default |
|---|---|---|
| `github-token` | GitHub API access + PR comments | `${{ github.token }}` |
| `llm-provider` | LLM backend: `github-models`, `claude`, `openai`, `ollama` | `github-models` |
| `llm-api-key` | API key for paid LLM providers | (optional) |

### Tier 2 API (Environment Variables)
| Variable | Purpose | Default |
|---|---|---|
| `CIFI_LLM_PROVIDER` | LLM provider for on-demand analysis | `github-models` |
| `CIFI_LLM_API_KEY` | API key for LLM provider | (optional) |

All secrets via env vars or GitHub Actions secrets. Never hardcoded.
