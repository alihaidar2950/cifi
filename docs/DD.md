# Detailed Design (DD) — CI Failure Intelligence (CIFI)

## Purpose

This document describes the implementation-level design of each CIFI system component. It complements the HLD by going deeper into interfaces, data flows, and technology choices. The core AI engineering lives in the LLM analyzer and multi-provider LLM integration.

---

## Analysis Pipeline Overview

```mermaid
flowchart TB
    subgraph ingestion["1. Log Ingestion"]
        logs["CI Logs\n(step outputs)"]
        src["Source Code\n($GITHUB_WORKSPACE)"]
        diff["Git Diff\n(HEAD~1)"]
        deps["Dependency Files\n(package.json, requirements.txt)"]
    end

    ingestion --> preprocess

    subgraph preprocess["2. Preprocessor"]
        strip["Strip ANSI / timestamps"]
        detect["Detect error boundaries"]
        extract["Extract stack traces"]
        truncate["Intelligent truncation\n(error > stack > source > diff)"]
        strip --> detect --> extract --> truncate
    end

    preprocess --> analyzer

    subgraph analyzer["3. LLM Analyzer"]
        subgraph llm_call["Multi-Provider LLM"]
            prompt["Build structured prompt"]
            call["Call LLM provider"]
            validate{"Pydantic validation"}
            prompt --> call --> validate
            validate -->|invalid| retry["Retry w/ backoff"]
            retry --> call
        end
    end

    validate -->|valid| output

    subgraph output["4. Output Router"]
        pr["PR Comment\n(GitHub API)"]
        terminal["Terminal\n(local runs)"]
        api["POST to API\n(optional)"]
    end

    style ingestion fill:#264653,stroke:#2a9d8f,color:#fff
    style preprocess fill:#2a9d8f,stroke:#264653,color:#fff
    style analyzer fill:#e76f51,stroke:#264653,color:#fff
    style output fill:#0f3460,stroke:#e94560,color:#fff
```

---

## Tier 1 Components (GitHub Action)

### 1. GitHub Action Entry Point

#### Tech
- `action.yml` — GitHub Action metadata
- `action/entrypoint.py` — Python entry point
- `action/Dockerfile` — Container Action image

#### Responsibilities
- Read CI failure context from the GitHub Actions environment
- Orchestrate the analysis pipeline: ingestion → preprocessing → LLM analysis
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
    description: 'LLM provider: github-models, claude, openai, ollama'
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

    # 4. LLM analysis
    result = await analyze(processed)  # multi-provider LLM analysis

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

### 4. LLM Analyzer

#### Tech
- Python module: `cifi/analyzer.py`
- Multi-provider LLM integration
- Pydantic for output validation

#### Responsibilities
- Send preprocessed context to LLM with structured prompting
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

async def analyze(context: ProcessedContext) -> AnalysisResult:
    """Analyze failure using multi-provider LLM."""
    prompt = build_prompt(context)
    response = await llm_provider.analyze(prompt)
    return AnalysisResult.model_validate_json(response)
```

#### Multi-Provider LLM Architecture

```mermaid
classDiagram
    class LLMProvider {
        <<Protocol>>
        +analyze(prompt: str) str
    }
    class GitHubModelsProvider {
        +base_url: str
        +analyze(prompt: str) str
    }
    class ClaudeProvider {
        +analyze(prompt: str) str
    }
    class OpenAIProvider {
        +analyze(prompt: str) str
    }
    class OllamaProvider {
        +analyze(prompt: str) str
    }

    LLMProvider <|.. GitHubModelsProvider : implements
    LLMProvider <|.. ClaudeProvider : implements
    LLMProvider <|.. OpenAIProvider : implements
    LLMProvider <|.. OllamaProvider : implements

    class Analyzer {
        +llm_provider: LLMProvider
        +analyze(context: ProcessedContext) AnalysisResult
    }

    Analyzer --> LLMProvider : uses
```

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

### 5. Output Router (Tier 1)

#### Tech
- Python module: `cifi/output.py`
- GitHub REST API for PR comments

#### PR Comment Format
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

---
<sub>Analyzed by [CIFI](https://github.com/alihaidar2950/cifi)</sub>
```

---

## Tier 2 — Backend API

### 6. API Service (Phase 3)

#### Tech
- FastAPI application in `backend/`
- PostgreSQL + SQLAlchemy async ORM (`asyncpg`)
- Alembic for database migrations
- API key authentication middleware
- Docker + Docker Compose

#### Responsibilities
- Expose the LLM analyzer as a REST API (on-demand analysis)
- Receive and store analysis results from Tier 1 Actions
- Persist failure history in PostgreSQL
- Detect recurring failure patterns via hash-based matching
- Serve paginated, filterable failure history

#### Endpoints
```python
# Analysis
@router.post("/api/analyze")
async def analyze_logs(payload: AnalyzeRequest, db: AsyncSession) -> AnalysisResult:
    """Run LLM analyzer, store result, return analysis."""
    context = preprocess(payload.logs, payload.source_files)
    result = await analyze(context)
    await store_failure(db, result, payload.metadata)
    await check_patterns(db, result)
    return result

# Failure History
@router.get("/api/failures")
async def list_failures(
    db: AsyncSession,
    repo: str | None = None,
    branch: str | None = None,
    failure_type: str | None = None,
    since: datetime | None = None,
    page: int = 1,
    per_page: int = 20,
) -> PaginatedResponse[FailureSummary]:
    """List stored failures with pagination and filtering."""
    ...

@router.get("/api/failures/{failure_id}")
async def get_failure(failure_id: uuid.UUID, db: AsyncSession) -> FailureDetail:
    """Get full failure detail including analysis result."""
    ...

# Pattern Detection
@router.get("/api/patterns")
async def list_patterns(
    db: AsyncSession,
    repo: str | None = None,
    min_occurrences: int = 3,
) -> list[PatternSummary]:
    """List recurring failure patterns."""
    ...

# Health
@router.get("/api/health")
async def health(db: AsyncSession) -> dict:
    """Health check with DB connectivity status."""
    ...
```

#### Authentication Middleware
```python
async def verify_api_key(request: Request) -> None:
    """API key auth middleware. Key passed via X-API-Key header."""
    api_key = request.headers.get("X-API-Key")
    if not api_key or not verify(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
```

---

### 8. Database Models + Pattern Detection

#### Tech
- SQLAlchemy 2.0 async ORM
- Alembic for schema migrations
- PostgreSQL

#### Database Schema

```mermaid
erDiagram
    FAILURES {
        uuid id PK
        varchar repo
        varchar branch
        varchar commit_sha
        int run_id
        int pr_number
        varchar failure_type
        varchar confidence
        text root_cause
        text suggested_fix
        jsonb contributing_factors
        jsonb relevant_log_lines
        varchar analysis_method
        varchar pattern_hash FK
        timestamp created_at
    }

    PATTERNS {
        uuid id PK
        varchar pattern_hash UK
        varchar failure_type
        text root_cause_summary
        int occurrence_count
        jsonb repos
        timestamp first_seen
        timestamp last_seen
    }

    PATTERNS ||--o{ FAILURES : "pattern_hash"
```

```python
class Failure(Base):
    __tablename__ = "failures"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    repo: Mapped[str] = mapped_column(String(255), index=True)
    branch: Mapped[str] = mapped_column(String(255))
    commit_sha: Mapped[str] = mapped_column(String(40))
    run_id: Mapped[int | None]
    pr_number: Mapped[int | None]
    failure_type: Mapped[str] = mapped_column(String(50), index=True)
    confidence: Mapped[str] = mapped_column(String(10))
    root_cause: Mapped[str] = mapped_column(Text)
    suggested_fix: Mapped[str] = mapped_column(Text)
    contributing_factors: Mapped[list[str]] = mapped_column(JSONB)
    relevant_log_lines: Mapped[list[str]] = mapped_column(JSONB)
    analysis_method: Mapped[str] = mapped_column(String(20))  # llm provider used
    pattern_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256
    created_at: Mapped[datetime] = mapped_column(default=func.now(), index=True)

class Pattern(Base):
    __tablename__ = "patterns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pattern_hash: Mapped[str] = mapped_column(String(64), unique=True)
    failure_type: Mapped[str] = mapped_column(String(50))
    root_cause_summary: Mapped[str] = mapped_column(Text)
    occurrence_count: Mapped[int] = mapped_column(default=1)
    repos: Mapped[list[str]] = mapped_column(JSONB)  # repos where this pattern appears
    first_seen: Mapped[datetime] = mapped_column(default=func.now())
    last_seen: Mapped[datetime] = mapped_column(default=func.now())
```

#### Pattern Detection Logic
```python
def compute_pattern_hash(root_cause: str, failure_type: str) -> str:
    """Deterministic hash for failure pattern matching."""
    normalized = normalize_error(root_cause)  # strip line numbers, paths, etc.
    return hashlib.sha256(f"{normalized}:{failure_type}".encode()).hexdigest()

async def check_patterns(db: AsyncSession, result: AnalysisResult, repo: str) -> None:
    """Update or create pattern record. Flag when occurrence_count >= 3."""
    pattern_hash = compute_pattern_hash(result.root_cause, result.failure_type)
    existing = await db.execute(
        select(Pattern).where(Pattern.pattern_hash == pattern_hash)
    )
    pattern = existing.scalar_one_or_none()
    if pattern:
        pattern.occurrence_count += 1
        pattern.last_seen = func.now()
        if repo not in pattern.repos:
            pattern.repos = [*pattern.repos, repo]
    else:
        db.add(Pattern(
            pattern_hash=pattern_hash,
            failure_type=result.failure_type,
            root_cause_summary=result.root_cause,
            repos=[repo],
        ))
    await db.commit()
```

#### Deployment

```mermaid
flowchart LR
    subgraph local["Local Development"]
        compose["Docker Compose"]
        api_local["cifi-api\nPort 8000"]
        pg_local[("PostgreSQL 16\nPort 5432")]
        compose --> api_local
        compose --> pg_local
        api_local <--> pg_local
    end

    subgraph prod["Production"]
        container["Docker Container\n(API)"]
        pg_prod[("Managed\nPostgreSQL")]
        container <--> pg_prod
    end

    subgraph cicd["CI/CD Pipeline"]
        lint["Lint"] --> test["Test"] --> build["Build"] --> migrate["Migrate"] --> deploy["Deploy"]
    end

    cicd --> prod

    style local fill:#264653,stroke:#2a9d8f,color:#fff
    style prod fill:#0f3460,stroke:#e94560,color:#fff
    style cicd fill:#2d6a4f,stroke:#1b4332,color:#fff
```

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
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `CIFI_API_KEY` | API key for authenticating clients | (required) |

All secrets via env vars or GitHub Actions secrets. Never hardcoded.
