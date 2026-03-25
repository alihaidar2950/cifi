High-Level Design — CI Failure Intelligence (CIFI)

## System Overview

CIFI is an AI-powered CI failure analysis agent built on a **two-tier architecture**:

- **Tier 1 — GitHub Action** (embedded in target repos): Runs inside the CI pipeline itself, has full access to source code, logs, and test output. Performs hybrid analysis (rule engine first, LLM fallback) and posts results as PR comments. Zero infrastructure required — just add the Action to your workflow.
- **Tier 2 — Central Server** (optional, deployed on EKS): Aggregates failure data across repos, tracks recurring patterns, serves a web dashboard, exposes an MCP server and CLI. Built with FastAPI + PostgreSQL.

This two-tier design solves the fundamental context problem: by running inside the repo's CI, CIFI has access to the full checkout — source code, dependency files, configuration, test fixtures — not just the logs. External webhook-based tools can only see what the API exposes; CIFI sees everything.

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
                    │  │     ┌───────────────────┐             │   │
                    │  │     │ Hybrid Analyzer   │             │   │
                    │  │     │ ┌───────────────┐ │             │   │
                    │  │     │ │ Rule Engine   │ │ ← handles   │   │
                    │  │     │ │ (50+ patterns)│ │   ~70% of   │   │
                    │  │     │ └───────┬───────┘ │   failures  │   │
                    │  │     │         │ miss?   │             │   │
                    │  │     │         ▼         │             │   │
                    │  │     │ ┌───────────────┐ │             │   │
                    │  │     │ │ LLM Fallback  │ │ ← handles   │   │
                    │  │     │ │ (Claude/GH    │ │   complex   │   │
                    │  │     │ │  Models/etc.) │ │   ~30%      │   │
                    │  │     │ └───────────────┘ │             │   │
                    │  │     └───────┬───────────┘             │   │
                    │  │             │                         │   │
                    │  │     ┌───────┴────────┐                │   │
                    │  │     ▼                ▼                │   │
                    │  │  PR Comment     POST to Tier 2        │   │
                    │  │  (GitHub API)   (if configured)       │   │
                    │  └──────────────────────────────────────┘   │
                    └─────────────────────────────────────────────┘

                                      │
                                      │ (optional)
                                      ▼

                    ┌─────────────────────────────────────────────┐
                    │       TIER 2 — CIFI Central Server          │
                    │       (EKS + Terraform)                     │
                    │                                             │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
                    │  │ FastAPI  │  │ Postgres │  │ Pattern  │  │
                    │  │ API      │  │ (history)│  │ Detector │  │
                    │  └────┬─────┘  └──────────┘  └──────────┘  │
                    │       │                                     │
                    │  ┌────┴───────────────────────────────────┐ │
                    │  │                                        │ │
                    │  ▼            ▼            ▼              │ │
                    │ Dashboard   MCP Server   CLI API          │ │
                    │ (React)     (AI agents)  (typer)          │ │
                    └─────────────────────────────────────────────┘
```

---

## Tier 1 — GitHub Action (Embedded Analysis)

### What It Does
Runs as a step in the target repo's GitHub Actions workflow. When a preceding step fails, CIFI activates, reads logs and source code directly from the checkout, analyzes the failure, and posts a PR comment with the root cause and suggested fix.

### Why Embedded
The critical insight: a webhook-based server can only access what the GitHub API exposes — logs, diffs, and PR metadata. It cannot see the full source code, dependency files, test fixtures, or configuration that often hold the real root cause. By running inside the CI pipeline, CIFI has the full checkout at its disposal.

### How It Works
1. The Action reads CI logs from `$GITHUB_STEP_SUMMARY` or step output files
2. Log ingestion reads source code directly from the workspace (`$GITHUB_WORKSPACE`)
3. Preprocessor strips noise, extracts error regions, builds context
4. Rule engine matches against 50+ known failure patterns (no API call needed)
5. If no rule matches with high confidence, falls back to LLM analysis
6. Posts structured analysis as a PR comment via GitHub API
7. Optionally sends results to Tier 2 for aggregation

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

## Tier 2 — Central Server (Optional Aggregation)

### What It Does
Receives analysis results from Tier 1 instances across multiple repos, stores them in PostgreSQL, detects recurring failure patterns, and serves a web dashboard + API + MCP server + CLI.

### When It's Needed
Tier 2 is optional. A team can use CIFI as just a GitHub Action (Tier 1 only) and get immediate value. Tier 2 adds value when:
- You want to track failure patterns across multiple repos
- You want a dashboard showing failure trends over time
- You want MCP server integration for AI agent workflows
- You want CLI access to historical failure data

### Components
1. **FastAPI API** — Receives analysis results from Tier 1, serves dashboard data, health/metrics endpoints
2. **PostgreSQL** — Stores failure history, pattern data
3. **Pattern Detector** — Hash-based recurring failure detection (SHA-256 of normalized error + failure type)
4. **Web Dashboard** — React UI showing failure history, trends, recurring patterns
5. **MCP Server** — Exposes CIFI tools to AI agent workflows (`analyze_failure`, `get_history`, `get_patterns`)
6. **CLI API** — Backend for `cifi history`, `cifi patterns`, `cifi status` commands

---

## Hybrid Analysis Strategy

CIFI uses a two-stage analysis approach to minimize cost and maximize speed:

### Stage 1 — Rule Engine (Free, Instant)
A pattern-matching engine with 50+ rules covering common CI failure modes:
- **Test failures**: assertion errors, import errors, fixture issues, timeout
- **Build errors**: syntax errors, missing dependencies, type errors, compilation failures
- **Infrastructure errors**: network timeouts, service unavailable, disk space, OOM
- **Configuration errors**: missing env vars, invalid YAML, permission denied

Each rule is a regex pattern + failure type + confidence + suggested fix template. When a rule matches with high confidence, CIFI skips the LLM entirely.

### Stage 2 — LLM Fallback (Complex Cases)
When no rule matches or confidence is low, CIFI sends preprocessed context to an LLM:
- **GitHub Models API** — Free via `GITHUB_TOKEN` (available in Actions by default)
- **Claude API** — Higher quality, pay-per-use
- **OpenAI-compatible** — Any OpenAI-compatible endpoint
- **Ollama** — Self-hosted, for teams that can't send logs externally

The LLM receives the full preprocessed context (logs + source code + diff) and returns structured JSON.

### Why Hybrid
| Approach | Speed | Cost | Accuracy | Coverage |
|---|---|---|---|---|
| Rules only | Instant | Free | High (when matched) | ~70% of failures |
| LLM only | 3-10s | $0.01-0.05/call | High | ~95% of failures |
| **Hybrid** | **Instant for 70%, 3-10s for 30%** | **$0 for 70%, paid for 30%** | **High** | **~95%** |

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
- Truncate intelligently to fit LLM context window
- Build structured context object

### 3. Rule Engine (Tier 1)
Pattern-matching engine for common failures:
- 50+ regex-based rules organized by failure category
- Each rule: pattern, failure_type, confidence, fix_template
- Deterministic, no external API calls, instant results
- Extensible — users can add custom rules

### 4. AI Analyzer (Tier 1)
LLM-based analysis for complex failures:
- Structured system prompt + preprocessed context
- Force JSON output, validate against Pydantic schema
- Provider-agnostic: Claude, OpenAI, GitHub Models, Ollama
- Retry with backoff on transient failures

### 5. Output Router (Tier 1 + Tier 2)
Delivers analysis results to the right destination:
- **PR Comment** (Tier 1): Markdown summary posted via GitHub API
- **Tier 2 API** (Tier 1 → Tier 2): POST analysis result for aggregation
- **Slack** (Tier 2): Short summary + link to dashboard
- **Dashboard** (Tier 2): Stored and rendered in web UI
- **Terminal** (CLI): Rich terminal output

### 6. Persistence Layer (Tier 2)
Stores failure history and pattern data:
- PostgreSQL with SQLAlchemy ORM + Alembic migrations
- `failures` table: repo, run_id, branch, commit, failure_type, root_cause, suggested_fix
- `failure_patterns` table: pattern_hash, occurrence_count, first_seen, last_seen
- Pattern hash = SHA-256(normalize(error) + failure_type) — deterministic, no LLM needed

### 7. Pattern Detector (Tier 2)
Identifies recurring failures across repos:
- Hash-based comparison, flags when `occurrence_count >= 3`
- Cross-repo pattern correlation
- Trend tracking over time

### 8. Web Dashboard (Tier 2)
Simple UI for failure visibility:
- Recent failures with root cause summaries
- Recurring pattern tracker
- Per-repo failure rate chart
- Single failure detail view

### 9. MCP Server (Tier 2)
Exposes CIFI to AI agent workflows:
- `analyze_failure(run_id)` — Run analysis on a specific CI run
- `get_failure_history(repo, days)` — Recent failure trends
- `get_recurring_patterns(repo)` — Recurring failures
- `get_fix_suggestions(run_id)` — Suggested fixes

### 10. CLI Tool (talks to Tier 2)
Developer terminal interface:
- `cifi analyze <run_id>` — Analyze a specific failed run
- `cifi history <repo>` — Show recent failure history
- `cifi patterns <repo>` — Show recurring failure patterns
- `cifi status` — Check central server health

---

## Infrastructure Design

### Tier 1 (No Infrastructure)
The GitHub Action runs in GitHub's hosted runners. No infrastructure to manage. Users add 3 lines to their workflow file.

### Tier 2 — Local Development
```
Docker Compose
├── cifi-api          (FastAPI app)
├── postgres          (failure history)
└── redis             (optional: job queue)
```

### Tier 2 — Production (AWS)
```
Terraform provisions:
├── VPC + subnets
├── EKS cluster (1 node group, t3.medium)
├── RDS PostgreSQL (db.t3.micro)
├── ECR (container registry)
├── ALB (Application Load Balancer → API endpoint)
└── IAM roles + policies

Kubernetes manifests:
├── cifi-api Deployment (2 replicas)
├── cifi-api Service + Ingress
├── cifi-dashboard Deployment + Service
├── ConfigMap (non-secret config)
└── Secret (API keys, DB credentials)
```

---

## Data Flow — End to End

### Tier 1 Only (Standalone)
```
1. Developer pushes commit to GitHub
2. GitHub Actions workflow runs and fails
3. CIFI Action activates (if: failure())
4. Reads CI logs from step outputs
5. Reads source code from $GITHUB_WORKSPACE
6. Preprocessor extracts error region, builds context
7. Rule engine checks against 50+ patterns
8.   → Match found? → Use rule result (instant, free)
9.   → No match?   → Send to LLM, receive JSON analysis
10. Posts PR comment with root cause + suggested fix
11. Developer reads 3-line summary, fixes issue in 5 minutes
```

### Tier 1 + Tier 2 (Full)
```
Steps 1-10 same as above, plus:
11. CIFI Action POSTs analysis result to Tier 2 API
12. Tier 2 stores result in PostgreSQL
13. Pattern Detector checks for recurring failures
14. Dashboard updated with new failure record
15. Slack notification sent (if configured)
16. CLI / MCP server can query historical data
```

---

## Security Considerations

- `GITHUB_TOKEN` is the only required secret for Tier 1 — provided automatically by GitHub Actions
- LLM API keys (if using paid providers) stored as GitHub Actions secrets
- Tier 2 API authentication via JWT tokens
- API keys stored in Kubernetes Secrets / AWS Secrets Manager — never in code
- Logs may contain sensitive data — scrubbing layer before sending to external LLM APIs
- Rate limiting on Tier 2 API endpoints
- Rule engine runs entirely locally — no data leaves the runner

---

## Observability (Minimal but Real)

- Structured JSON logging in both tiers
- Tier 2: `/health` and `/metrics` endpoints
- Basic Prometheus metrics: `failures_analyzed_total`, `analysis_latency_seconds`, `rule_engine_hit_rate`, `llm_fallback_count`

---

## Key Design Decisions — Summary

| Decision | Choice | Rationale |
|---|---|---|
| Two-tier architecture | GitHub Action + optional central server | Full repo context in Tier 1, aggregation in Tier 2 |
| Hybrid analysis | Rule engine first, LLM fallback | 70% of failures resolved instantly for free |
| Embedded in CI | GitHub Action, not webhook receiver | Solves the context problem — full checkout access |
| Force JSON from LLM | Yes | Reliable parsing; no prompt-output ambiguity |
| Pattern detection | Hash-based, not LLM-based | Fast, cheap, deterministic |
| Infrastructure | EKS + Terraform (Tier 2) | Legitimate K8s + IaC experience |
| MCP layer | Yes (Tier 2) | Differentiating; pluggable into AI agent workflows |
| LLM provider | Swappable via config | GitHub Models (free), Claude, OpenAI, Ollama |
| Tier 2 optional | Yes | Immediate value with Action alone, progressive complexity |

---

## What This Project Proves to a Hiring Manager

| Skill | Evidence in CIFI |
|---|---|
| CI/CD systems | GitHub Action that runs inside CI, deep understanding of failure modes |
| Python | Core engine, rule engine, AI pipeline, CLI tooling |
| AI / LLM integration | Hybrid analysis, structured prompting, JSON enforcement, MCP server |
| GitHub Actions | Custom Action published to marketplace, workflow integration |
| Kubernetes | EKS deployment for Tier 2, manifests, service/ingress |
| Terraform | Full AWS infrastructure for Tier 2 provisioned as code |
| System design | Two-tier architecture, progressive complexity, separation of concerns |
| Developer empathy | Built to solve a real problem — 3 lines to add, immediate value |
