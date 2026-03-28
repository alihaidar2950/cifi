# High-Level Design — CI Failure Intelligence (CIFI)

## System Overview

CIFI is an **AI-powered CI failure analysis agent** built on a two-tier architecture with a **hybrid AI analysis core**:

- **Tier 1 — GitHub Action** (embedded in target repos): Runs inside the CI pipeline itself, has full access to source code, logs, and test output. Performs hybrid analysis (rule engine first, multi-provider LLM fallback) and posts results as PR comments. Zero infrastructure required — just add the Action to your workflow.
- **Tier 2 — Backend API** (optional, deployed via Docker): A real FastAPI backend with PostgreSQL persistence, API key auth, failure history, and pattern detection. Receives results from Tier 1 Actions, stores them, detects recurring patterns, and exposes a RESTful API.

The core AI engineering is in the **hybrid analysis engine**: a two-stage architecture that combines deterministic pattern matching (50+ rules, instant, free) with multi-provider LLM intelligence (Claude, OpenAI, GitHub Models, Ollama) for complex failures. The backend engineering is in **Tier 2**: a production-grade API with database persistence, authentication, and algorithmic pattern detection.

---

## Architecture Diagram

```
                    ┌─────────────────────────────────────────────┐
                    │           TARGET REPO (GitHub)               │
                    │                                             │
                    │  Developer pushes commit                    │
                    │       │                                     │
                    │       ▼                                     │
                    │  GitHub Actions workflow runs                │
                    │       │                                     │
                    │       ▼ (on failure)                        │
                    │  ┌──────────────────────────────────────┐   │
                    │  │  TIER 1 — CIFI GitHub Action         │   │
                    │  │                                      │   │
                    │  │  ┌─────────────┐  ┌──────────────┐   │   │
                    │  │  │ Log Ingestion│  │ Source Code  │   │   │
                    │  │  │ (local files)│  │ Context      │   │   │
                    │  │  └──────┬──────┘  └──────┬───────┘   │   │
                    │  │         └───────┬─────────┘           │   │
                    │  │                 ▼                     │   │
                    │  │         ┌──────────────┐              │   │
                    │  │         │ Preprocessor │              │   │
                    │  │         └──────┬───────┘              │   │
                    │  │                ▼                      │   │
                    │  │  ┌──────────────────────────────────┐ │   │
                    │  │  │      Hybrid AI Analyzer          │ │   │
                    │  │  │                                  │ │   │
                    │  │  │  ┌────────────────────────────┐  │ │   │
                    │  │  │  │ Stage 1: Rule Engine       │  │ │   │
                    │  │  │  │ 50+ patterns, instant,     │  │ │   │
                    │  │  │  │ handles ~70% of failures   │  │ │   │
                    │  │  │  └────────────┬───────────────┘  │ │   │
                    │  │  │              miss?               │ │   │
                    │  │  │               ▼                  │ │   │
                    │  │  │  ┌────────────────────────────┐  │ │   │
                    │  │  │  │ Stage 2: Multi-Provider LLM│  │ │   │
                    │  │  │  │ ┌────────┬────────┬──────┐ │  │ │   │
                    │  │  │  │ │Claude  │OpenAI  │GitHub│ │  │ │   │
                    │  │  │  │ │        │        │Models│ │  │ │   │
                    │  │  │  │ ├────────┴────────┴──────┤ │  │ │   │
                    │  │  │  │ │      Ollama (local)    │ │  │ │   │
                    │  │  │  │ └────────────────────────┘ │  │ │   │
                    │  │  │  │ Structured prompting       │  │ │   │
                    │  │  │  │ JSON enforcement           │  │ │   │
                    │  │  │  │ Pydantic validation        │  │ │   │
                    │  │  │  └────────────────────────────┘  │ │   │
                    │  │  └──────────────┬───────────────────┘ │   │
                    │  │                 │                     │   │
                    │  │         ┌───────┴────────┐            │   │
                    │  │         ▼                ▼            │   │
                    │  │    PR Comment      POST to API        │   │
                    │  │    (GitHub API)    (if configured)     │   │
                    │  └──────────────────────────────────────┘   │
                    └─────────────────────────────────────────────┘

                                      │
                                      │ (optional)
                                      ▼

                    ┌─────────────────────────────────────────────┐
                    │       TIER 2 — Backend API                  │
                    │       (Docker + managed platform)            │
                    │                                             │
                    │  ┌──────────────────────────────────────┐   │
                    │  │  FastAPI + PostgreSQL                    │   │
                    │  │  POST /api/analyze (hybrid analyzer)      │   │
                    │  │  GET  /api/failures (history + filtering) │   │
                    │  │  GET  /api/patterns (recurring failures)  │   │
                    │  │  GET  /api/health                        │   │
                    │  │  API key auth • SQLAlchemy ORM • Alembic  │   │
                    │  └──────────────────────────────────────┘   │
                    └─────────────────────────────────────────────┘
```

---

## Tier 1 — GitHub Action (Embedded Analysis)

### What It Does
Runs as a step in the target repo's GitHub Actions workflow. When a preceding step fails, CIFI activates, reads logs and source code directly from the checkout, analyzes the failure using the hybrid AI engine, and posts a PR comment with the root cause and suggested fix.

### Why Embedded
The critical insight: a webhook-based server can only access what the GitHub API exposes — logs, diffs, and PR metadata. It cannot see the full source code, dependency files, test fixtures, or configuration that often hold the real root cause. By running inside the CI pipeline, CIFI has the full checkout at its disposal.

### How It Works
1. The Action reads CI logs from `$GITHUB_STEP_SUMMARY` or step output files
2. Log ingestion reads source code directly from the workspace (`$GITHUB_WORKSPACE`)
3. Preprocessor strips noise, extracts error regions, builds structured context
4. Rule engine matches against 50+ known failure patterns (no API call needed)
5. If no rule matches with high confidence, falls back to multi-provider LLM analysis
6. LLM response validated against Pydantic schema — malformed responses retried
7. Posts structured analysis as a PR comment via GitHub API
8. Optionally sends results to Tier 2 API

### Usage (3 lines in a workflow)
```yaml
- uses: alihaidar2950/cifi@v1
  if: failure()
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

### Context Available in Tier 1
| Context | How Accessed | Value |
|---|---|---|
| CI logs | `$GITHUB_STEP_SUMMARY`, step output files | Primary error source |
| Source code | `$GITHUB_WORKSPACE` (checkout) | Full codebase context |
| Dependency files | `package.json`, `requirements.txt`, etc. from checkout | Dependency issues |
| Test fixtures | Direct file read from workspace | Test data context |
| Git diff | `git diff HEAD~1` locally | What changed |
| Config files | `.env.example`, `tsconfig.json`, etc. | Configuration context |

---

## Tier 2 — Backend API

### What It Does
A real FastAPI backend service with PostgreSQL persistence. Receives analysis results from Tier 1 Actions (or runs on-demand analysis), stores failure history, detects recurring patterns across repos, and exposes a RESTful API with pagination, filtering, and authentication.

### Why a Real Backend
A health-check-only API proves nothing. A backend with database persistence, authentication, query filtering, and pattern detection demonstrates real backend engineering: database design, ORM usage, migration management, API design, auth middleware, and async Python.

### Components
1. **FastAPI API** — RESTful endpoints: analyze, list failures, get failure detail, list patterns, health check
2. **PostgreSQL** — Failure history storage, pattern tracking
3. **SQLAlchemy ORM** — Async ORM with `asyncpg`, proper model design
4. **Alembic** — Database schema migrations
5. **API Key Auth** — Middleware-based authentication for all endpoints
6. **Pattern Detection** — Hash-based recurring failure identification (SHA-256 of normalized error + failure type)
7. **Docker** — Multi-stage Dockerfile, Docker Compose for local dev (API + PostgreSQL)
8. **CI/CD** — GitHub Actions: test → build → migrate → deploy

### Deferred Components
These are separate projects:
- Deep infrastructure (EKS, Terraform, Kustomize, Prometheus/Grafana)
- React web dashboard
- MCP server for AI agent integration
- CLI tool, Slack integration

---

## Hybrid AI Analysis — The Core Architecture

This is the heart of CIFI and the primary AI engineering showcase. The hybrid approach demonstrates production-grade AI system design, not just "wrap an LLM API."

### Stage 1 — Rule Engine (Free, Instant)
A pattern-matching engine with 50+ rules covering common CI failure modes:
- **Test failures**: assertion errors, import errors, fixture issues, timeout
- **Build errors**: syntax errors, missing dependencies, type errors, compilation failures
- **Infrastructure errors**: network timeouts, service unavailable, disk space, OOM
- **Configuration errors**: missing env vars, invalid YAML, permission denied

Each rule is a regex pattern + failure type + confidence + suggested fix template. When a rule matches with high confidence, CIFI skips the LLM entirely.

### Stage 2 — Multi-Provider LLM (Complex Cases)
When no rule matches or confidence is low, CIFI sends preprocessed context to an LLM via a provider-agnostic architecture:

- **GitHub Models API** — Free via `GITHUB_TOKEN` (available in Actions by default)
- **Claude API** — Higher quality, pay-per-use
- **OpenAI-compatible** — Any OpenAI-compatible endpoint
- **Ollama** — Self-hosted, for teams that can't send logs externally

Each provider implements a shared Python protocol, making the system extensible. Adding a new LLM provider requires implementing a single method.

### Structured Prompting + Output Validation
- System prompt with role definition, output format specification, and domain context
- User prompt with preprocessed logs, source code, diff, and metadata
- JSON output enforcement — the LLM must respond in valid JSON
- Pydantic schema validation — every response is validated before use
- Retry with exponential backoff on validation failures
- Few-shot examples for edge cases

### Why Hybrid
| Approach | Speed | Cost | Accuracy | Coverage |
|---|---|---|---|---|
| Rules only | Instant | Free | High (when matched) | ~70% of failures |
| LLM only | 3-10s | $0.01-0.05/call | High | ~95% of failures |
| **Hybrid** | **Instant for 70%, 3-10s for 30%** | **$0 for 70%, paid for 30%** | **High** | **~95%** |

### AI Engineering Decisions
| Decision | Rationale |
|---|---|
| Rules before LLM | Cost optimization + speed. Real AI systems use the cheapest viable method first. |
| Provider-agnostic design | Protocol-based abstraction. Not locked to any vendor. |
| Pydantic validation | Production-grade output handling. Malformed responses are caught and retried. |
| Structured prompting | Explicit JSON format, role definitions, context prioritization. Not "summarize this log." |
| Context window management | Intelligent truncation: error region > stack trace > source > diff. Maximizes signal per token. |
| GitHub Models as default | Free LLM access via existing `GITHUB_TOKEN`. Zero-config for users. |

---

## Component Breakdown

### 1. Log Ingestion (Tier 1)
Reads failure context directly from the local CI environment:
- CI logs from step output / log files
- Source code from the checked-out workspace
- Git diff via local `git` commands
- Dependency manifests from the filesystem

### 2. Preprocessor (Tier 1)
Cleans and structures raw data before analysis:
- Strip ANSI escape codes and timestamps
- Detect error boundaries (start/end of error region)
- Extract stack traces, assertion failures, error messages
- Truncate intelligently to fit within LLM context window (priority: error region > stack trace > source code > diff)
- Build structured context object
- **Key insight**: The quality of AI analysis is directly proportional to preprocessing quality. This is where most engineering work lives.

### 3. Rule Engine (Tier 1)
Pattern-matching engine for common failures:
- 50+ regex-based rules organized by failure category
- Each rule: pattern, failure_type, confidence, fix_template
- Deterministic, no external API calls, instant results
- Extensible — users can add custom rules

### 4. Multi-Provider LLM Integration (Tier 1)
Provider-agnostic LLM analysis for complex failures:
- Python protocol class defining the provider interface
- Individual implementations: Claude, OpenAI, GitHub Models, Ollama
- Structured system prompt + preprocessed context
- Force JSON output, validate against Pydantic schema
- Retry with backoff on transient failures

### 5. Output Router (Tier 1)
Delivers analysis results:
- **PR Comment** (Tier 1): Markdown summary posted via GitHub API
- **Terminal** (local): Rich terminal output for local runs
- **Tier 2 API** (optional): POSTs result to backend for storage and pattern tracking

### 6. Backend API (Phase 3)
FastAPI service with PostgreSQL:
- `POST /api/analyze` — accepts log payload, runs hybrid analyzer, stores result, returns analysis
- `GET /api/failures` — list stored failures with pagination + filtering (repo, branch, date range)
- `GET /api/failures/{id}` — single failure detail
- `GET /api/patterns` — recurring failure patterns (hash-based detection)
- `GET /api/health` — health check with DB connectivity status
- API key authentication middleware
- SQLAlchemy async ORM + Alembic migrations
- Structured JSON logging with request IDs

---

## Infrastructure Design

### Tier 1 (No Infrastructure)
The GitHub Action runs in GitHub's hosted runners. No infrastructure to manage. Users add 3 lines to their workflow file.

### Tier 2 — Local Development
```
Docker Compose
├── cifi-api          (FastAPI app)
└── postgres          (PostgreSQL database)
```

### Tier 2 — Production
```
Docker container deployed to managed platform:
├── Fly.io / Railway / Cloud Run
├── Managed PostgreSQL (Fly Postgres / Railway / Cloud SQL)
├── HTTPS (automatic)
├── Health checks
├── Environment variables for config
└── GitHub Actions CI/CD: test → build → migrate → deploy
```

No VPCs, no EKS clusters, no Terraform modules. Deploy simply — the AI engine and backend design are the product.

---

## Data Flow — End to End

### Tier 1 (Standalone — Primary Use Case)
```
1. Developer pushes commit to GitHub
2. GitHub Actions workflow runs and fails
3. CIFI Action activates (if: failure())
4. Reads CI logs from step outputs
5. Reads source code from $GITHUB_WORKSPACE
6. Preprocessor extracts error region, builds structured context
7. Rule engine checks against 50+ patterns
8.   → Match found? → Use rule result (instant, free)
9.   → No match?   → Send to LLM via provider abstraction
10.  → LLM returns JSON → Validate against Pydantic schema
11. Posts PR comment with root cause + suggested fix
12. Developer reads 3-line summary, fixes issue in 5 minutes
```

### Tier 2 API (On-Demand Analysis + Persistence)
```
1. Client authenticates with API key
2. Client POSTs log payload to /api/analyze
3. Preprocessor extracts error region
4. Hybrid analyzer runs (rules → LLM fallback)
5. Result stored in PostgreSQL (failures table)
6. Pattern detector checks for recurring failures (hash match)
7. Returns structured AnalysisResult JSON

Querying history:
8. Client GETs /api/failures?repo=X&branch=Y&page=1
9. Returns paginated failure list with metadata
```

---

## Security Considerations

- `GITHUB_TOKEN` is the only required secret for Tier 1 — provided automatically by GitHub Actions
- LLM API keys (if using paid providers) stored as GitHub Actions secrets
- Logs may contain sensitive data — scrubbing layer before sending to external LLM APIs
- Rule engine runs entirely locally — no data leaves the runner
- API key authentication for Tier 2 endpoints
- Input validation on all API endpoints
- Rate limiting on analysis endpoints

---

## Key Design Decisions — Summary

| Decision | Choice | Rationale |
|---|---|---|
| **Hybrid AI analysis** | Rule engine first, LLM fallback | 70% of failures resolved instantly for free. Production AI = cost optimization. |
| **Multi-provider LLM** | Protocol-based abstraction | Vendor-agnostic, extensible, real AI engineering pattern |
| **Structured prompting** | JSON enforcement + Pydantic | Production-grade LLM integration, not notebook demos |
| **Embedded in CI** | GitHub Action, not webhook | Solves the context problem — full checkout access |
| **Simple deployment** | Docker + managed platform | Deploy simply. The AI engine and backend design are the product. |
| **Two-tier architecture** | Action + optional backend API | GitHub Action for CI, backend API for history/patterns/on-demand. |
| **Force JSON from LLM** | Yes | Reliable parsing; no prompt-output ambiguity |
| **Pattern detection** | Hash-based, not LLM-based | Fast, cheap, deterministic |
| **PostgreSQL persistence** | Real database, not in-memory | Backend engineering signal: schema design, migrations, ORM |
