# Implementation Plan — CI Failure Intelligence (CIFI)

## TL;DR

Build an AI-powered CI failure analysis agent using a **two-tier architecture**:

- **Tier 1 — GitHub Action**: Embedded in target repos. Reads logs + source code from the checkout, runs a hybrid analyzer (rule engine first, LLM fallback), posts PR comments. Zero infrastructure required — 3 lines of YAML.
- **Tier 2 — Central Server** (optional): FastAPI + PostgreSQL on EKS. Aggregates failure data across repos, tracks recurring patterns, serves a dashboard, exposes MCP server + CLI.

Each phase is independently testable with explicit human checkpoints.

---

## Phase 1: Core Engine — Rule Engine + Preprocessor + Analyzer

**Goal**: Build the `cifi/` Python package — the core analysis engine that works locally. This is the foundation for both tiers.

**Steps**:
1. Create `cifi/` package with clean module structure
2. `cifi/rules.py` — Rule engine: 50+ regex patterns covering common CI failure modes (test failures, build errors, infra errors, config errors). Each rule has: pattern, failure_type, confidence, fix_template
3. `cifi/preprocessor.py` — Strip ANSI codes/timestamps, detect error boundaries, extract stack traces and assertion failures, truncate intelligently to fit LLM context window
4. `cifi/analyzer.py` — Hybrid analyzer: run rule engine first, fall back to LLM if no high-confidence match. Support multiple LLM providers (GitHub Models API, Claude, OpenAI, Ollama)
5. `cifi/schemas.py` — Pydantic models: `AnalysisResult` (failure_type, confidence, root_cause, contributing_factors, suggested_fix, relevant_log_lines)
6. `cifi/config.py` — Configuration: LLM provider, model, API keys via env vars
7. `cifi/ingestion.py` — Log ingestion: read CI logs and source code from local filesystem (for Tier 1) or via GitHub API (for Tier 2)
8. Tests with realistic failure fixtures (test failures, build errors, infra errors, timeouts)
9. Root `Makefile` with targets: `test`, `lint`, `analyze-local`

**Verification**:
- Rule engine correctly identifies common failure patterns from fixture logs
- Preprocessor strips noise and extracts error regions
- Hybrid analyzer uses rules when possible, falls back to LLM
- All tests pass with mocked LLM responses (no API key needed)
- Manual run with real API key returns valid `AnalysisResult`

**Human Checkpoint**: Review rule patterns, preprocessor quality, prompt design, output schema.

---

## Phase 2: GitHub Action — Tier 1

**Goal**: Package the core engine as a GitHub Action. When a CI step fails, CIFI analyzes the failure and posts a PR comment.

**Steps**:
1. Create `action.yml` — GitHub Action metadata (name, description, inputs, runs)
2. `action/entrypoint.py` — Main entry point: read CI logs, read source code from `$GITHUB_WORKSPACE`, run hybrid analyzer, post PR comment
3. `action/Dockerfile` — Container Action image with cifi package installed
4. PR comment formatting — Markdown template with failure type, root cause, suggested fix, relevant log lines, recurring warning
5. GitHub API integration — Post PR comment using `GITHUB_TOKEN` (provided automatically)
6. GitHub Models API integration — Free LLM fallback using `GITHUB_TOKEN`
7. Create a test repo with intentionally failing workflows for E2E testing
8. Publish Action to GitHub Marketplace
9. Makefile targets: `action-build`, `action-test`

**Usage**:
```yaml
- uses: alihaidar2950/cifi@v1
  if: failure()
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

**Verification**:
- Action triggers on CI failure in test repo
- Rule engine catches common failures instantly (no LLM call)
- LLM fallback works for complex failures
- PR comment appears with structured analysis
- Works without any secrets beyond `GITHUB_TOKEN`

**Human Checkpoint**: Review Action metadata, entrypoint, PR comment format, demo on real repo. **Tier 1 MVP complete.**

---

## Phase 3: Central API + Persistence — Tier 2 Foundation

**Goal**: Build the Tier 2 central server that receives and stores analysis results from Tier 1 instances.

**Steps**:
1. Set up FastAPI application in `backend/`
2. PostgreSQL + SQLAlchemy + Alembic migration: `failures` table (id, repo, run_id, branch, commit_sha, triggered_at, failure_type, confidence, root_cause, suggested_fix, raw_analysis_json)
3. Alembic migration: `failure_patterns` table (id, repo, pattern_hash, failure_type, first_seen, last_seen, occurrence_count, example_run_ids)
4. `POST /api/failures` — Endpoint to receive analysis results from Tier 1 (JWT auth)
5. `GET /api/failures` — List failures (filterable by repo, branch, date range)
6. `GET /api/failures/{id}` — Single failure detail
7. `GET /api/patterns/{repo}` — Recurring failure patterns
8. `GET /api/health` — Health check for K8s probes
9. Update Tier 1 Action to optionally POST results to Tier 2 (new input: `central-server-url`)
10. Docker Compose for local development (cifi-api + postgres)
11. Makefile targets: `server-up`, `server-down`, `server-test`

**Verification**:
- API endpoints work end-to-end
- Tier 1 Action successfully posts results to Tier 2
- Failure records stored and queryable
- Pattern detection flags recurring failures (occurrence_count >= 3)

**Human Checkpoint**: Review API design, DB schema, Tier 1 → Tier 2 integration.

---

## Phase 4: Dashboard + CLI + MCP Server

**Goal**: Add user-facing interfaces to Tier 2 — web dashboard, CLI tool, and MCP server.

**Steps**:
1. **Dashboard** (React frontend): Recent failures list, recurring pattern tracker, per-repo failure rate chart, single failure detail view
2. **CLI** (`cli/`): `cifi history <repo>`, `cifi patterns <repo>`, `cifi status` — Python + `typer`, talks to Tier 2 API
3. **MCP Server** (`cifi/mcp_server.py`): Expose tools — `analyze_failure(run_id)`, `get_failure_history(repo, days)`, `get_recurring_patterns(repo)`, `get_fix_suggestions(run_id)`
4. **Slack integration**: Output Router sends failure summaries to a Slack channel via webhook
5. Makefile targets: `cli-install`, `cli-test`, `mcp-test`

**Verification**:
- Dashboard shows failure history and patterns
- CLI commands work end-to-end
- MCP tools callable from AI agent workflows
- Slack messages delivered on failure

**Human Checkpoint**: Review dashboard UX, CLI help text, MCP tool design.

---

## Phase 5: Infrastructure — EKS + Terraform

**Goal**: Deploy Tier 2 on AWS EKS via Terraform. Legitimate cloud infrastructure experience.

**Steps**:
1. `k8s/namespace.yaml` — dedicated `cifi` namespace
2. `k8s/backend/` — Deployment (liveness/readiness → `/api/health`) + Service + init container for Alembic migrations
3. `k8s/frontend/` — Deployment + Service (built React app via nginx)
4. `k8s/ingress.yaml` — Ingress routing, ALB for API endpoint
5. `k8s/secrets.yaml.example` — template only, never commit real values
6. `k8s/kustomization.yaml` — Kustomize base
7. `terraform/` — VPC + subnets, EKS cluster (1 node group, t3.medium), RDS PostgreSQL (db.t3.micro), ECR, ALB, IAM roles
8. Update Tier 1 Action docs with production Tier 2 URL configuration
9. Makefile targets: `k8s-deploy`, `k8s-status`, `terraform-plan`, `terraform-apply`

**Verification**:
- All pods Running in `cifi` namespace, readiness probes pass
- Tier 2 API accessible via ALB
- `terraform validate` + `terraform plan` pass
- End-to-end: GitHub failure → Tier 1 analysis → POST to Tier 2 → dashboard updated

**Human Checkpoint**: Review K8s manifests, Terraform plan, security groups, IAM policies.

---

## Phase 6: Polish + Launch

**Goal**: Production-ready polish, documentation, and launch.

**Steps**:
1. **Observability**: Structured JSON logging, `/api/metrics` endpoint, Prometheus metrics (`failures_analyzed_total`, `analysis_latency_seconds`, `rule_engine_hit_rate`, `llm_fallback_count`)
2. **README**: Architecture diagram, demo GIF, install instructions (3-line quick start), interview-ready documentation
3. **Action README**: Marketplace listing, all inputs/outputs documented, examples
4. **Demo video**: Record a real CI failure → CIFI analysis → PR comment flow
5. **Blog post**: Technical write-up of the two-tier design and hybrid analysis approach
6. **Security hardening**: Log scrubbing before LLM, rate limiting, input validation audit

**Verification**:
- README makes a hiring manager stop scrolling
- Demo GIF shows real failure → analysis → fix cycle
- All tests pass in CI
- Security review complete

**Human Checkpoint**: Review README quality, demo, blog draft. **Full version complete.**

---

## Execution Principles

| Principle | How |
|---|---|
| **Tier 1 first** | Deliver value with zero infrastructure before adding complexity |
| **Incremental delivery** | Each phase produces a working artifact. Never advance with broken tests. |
| **Human-in-the-loop** | Pause after each phase for review/approval before advancing. |
| **Test continuously** | Every phase adds tests. CI runs them automatically on every push. |
| **Progressive complexity** | Phase 1-2 = no infra. Phase 3-4 = Docker. Phase 5 = cloud. |
| **Real over impressive** | Every component solves an actual problem. No padding. |

---

## Decisions

| Decision | Rationale |
|---|---|
| **Two-tier architecture** | Tier 1 solves the context problem (full checkout), Tier 2 adds aggregation |
| **GitHub Action as Tier 1** | Zero infra, marketplace distribution, 3-line adoption |
| **Hybrid analysis (rules + LLM)** | 70% of failures resolved instantly for free by rule engine |
| **GitHub Models API** | Free LLM access via GITHUB_TOKEN — no API key needed |
| **FastAPI for Tier 2** | Lightweight, async, well-suited for API + dashboard serving |
| **`cifi/` as core package** | Shared between Tier 1 (Action) and Tier 2 (server), clean domain boundary |
| **Force JSON from LLM** | Structured prompts + schema validation, never parse free-form text |
| **Hash-based pattern detection** | Fast, cheap, deterministic (no LLM calls for comparison) |
| **EKS + Terraform for Tier 2** | Legitimate K8s + IaC experience on the resume |
| **MCP server in Tier 2** | Differentiating — pluggable into AI agent workflows |
| **Tier 2 optional** | Immediate value with Action alone, teams opt into central server |

---

## Project Structure

```
cifi/               # Core engine: rules, preprocessor, analyzer, schemas
action/             # GitHub Action: entrypoint, Dockerfile, action.yml
backend/            # Tier 2 FastAPI server (Phase 3+)
frontend/           # Tier 2 React dashboard (Phase 4+)
cli/                # Developer CLI (Phase 4+)
k8s/                # Kubernetes manifests (Phase 5)
terraform/          # AWS EKS + supporting infra (Phase 5)
docs/               # Design docs: HLD, DD, Plan, North Star
.github/            # Copilot instructions, PR workflow, CI
```