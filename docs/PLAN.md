# Implementation Plan — CI Failure Intelligence (CIFI)

## TL;DR

Build an AI-powered CI failure analysis agent using the **full-stack-fastapi-template** (FastAPI + React + PostgreSQL + Docker Compose + JWT auth) as the application foundation. CIFI watches CI pipelines for failures, ingests logs and context, runs them through an LLM analysis pipeline, and delivers structured root cause summaries to developers via PR comments, Slack, or a web dashboard. Each phase is independently testable with explicit human checkpoints.

**What the template gives us for free**: Full-stack app with auth, Docker Compose, Traefik reverse proxy, Postgres, pre-commit hooks, pytest + Playwright tests, basic GitHub Actions CI, Alembic migrations, email-based password recovery via Mailcatcher.

**What we build**: Webhook receiver, log ingestion engine, preprocessor, AI analysis pipeline, MCP server, failure persistence + pattern detection, output router (PR comments, Slack), dashboard, CLI, and cloud deployment via EKS + Terraform.

---

## Phase 1: Adopt the Full-Stack FastAPI Template

**Goal**: Get the template running locally, verify tests pass, integrate into the CIFI repo. This becomes the foundation for the webhook receiver, API layer, and dashboard.

**Steps**:
1. Copy the template (pinned to release `0.10.0`) into the repo — `backend/`, `frontend/`, `compose.yml`, `compose.override.yml`, `.env`, `scripts/`, etc.
2. Regenerate secrets in `.env` (`SECRET_KEY`, `POSTGRES_PASSWORD`, `FIRST_SUPERUSER_PASSWORD`)
3. Run `docker compose up -d`, verify all services start
4. Run existing tests: `docker compose exec backend pytest`
5. Add a `/api/health` endpoint (needed for K8s probes and service health checks)
6. Create a root `Makefile` with targets: `up`, `down`, `test-backend`, `test-e2e`, `logs`
7. Update `README.md` with CIFI branding and overview

**Verification**:
- All containers healthy (`docker compose ps` shows all services "Up")
- `make test-backend` passes
- Frontend loads at `http://localhost`; Swagger UI at `http://localhost/api/docs`
- `/api/health` returns `{"status": "ok"}`

**Human Checkpoint**: Review structure, confirm app runs end-to-end, check `.env` for secrets.

---

## Phase 2: Core Engine — Log Ingestion + AI Analysis

**Goal**: Build the core CIFI engine that fetches CI logs, preprocesses them, and runs LLM-based root cause analysis.

**Steps**:
1. Create `cifi/` package — the core engine, separate from the FastAPI `backend/`
2. `cifi/ingestion.py` — Log Ingestion Engine: fetch raw CI logs, test output, git diff, PR context via GitHub REST API (`PyGithub`)
3. `cifi/preprocessor.py` — Strip ANSI codes/timestamps, detect error boundaries, extract stack traces/assertion failures, truncate intelligently to fit LLM context window
4. `cifi/analyzer.py` — AI Analysis Pipeline: structured prompt → Claude/OpenAI API → validated JSON output
5. `cifi/prompts.py` — System and user prompt templates for the LLM
6. `cifi/schemas.py` — Pydantic models for analysis output: `failure_type`, `confidence`, `root_cause`, `contributing_factors`, `suggested_fix`, `relevant_log_lines`, `recurring`, `similar_past_failures`
7. `cifi/config.py` — LLM provider config (swappable via env: Claude, OpenAI, Ollama)
8. Tests with mocked HTTP responses and realistic failure fixtures (test failures, build errors, infra errors, timeouts)
9. Makefile targets: `cifi-test`, `cifi-analyze`

**Verification**:
- Mocked tests pass in CI (no API key needed)
- Manual run with real API key returns structured JSON analysis matching the schema
- `grep -r "API_KEY\|SECRET" --include="*.py"` → only env-var references
- Preprocessor correctly strips noise and extracts error regions from sample logs

**Human Checkpoint**: Review prompts, output schema, preprocessor quality, error handling, security.

---

## Phase 3: GitHub Integration — Webhook Receiver + PR Comments

**Goal**: Connect CIFI to GitHub Actions so failures are automatically detected and analysis is posted back to PRs.

**Steps**:
1. Add webhook receiver endpoint to `backend/` — `POST /api/webhook/github` accepting `workflow_run` events
2. Implement GitHub webhook signature verification (HMAC secret validation)
3. Async processing — webhook returns 200 immediately, queues analysis via FastAPI background tasks
4. Output Router: post analysis as a PR comment via GitHub API (Markdown formatted)
5. Add ngrok config for local development (receive webhooks locally)
6. Configure a test GitHub repo with a workflow that intentionally fails
7. End-to-end test: push → failure → webhook → analysis → PR comment
8. Makefile targets: `webhook-test`, `cifi-demo`

**Verification**:
- Webhook endpoint validates GitHub signatures (rejects invalid requests)
- Failed workflow triggers analysis automatically
- PR comment appears with structured root cause summary
- Invalid/unsigned webhook requests are rejected with 403

**Human Checkpoint**: Review webhook security, async flow, PR comment format, demo on real repo.

---

## Phase 4: Persistence + Pattern Detection — MVP Complete

**Goal**: Store failure history in PostgreSQL, detect recurring patterns. This completes the MVP.

**Steps**:
1. Alembic migration: add `failures` table (id, repo, run_id, branch, commit_sha, triggered_at, failure_type, confidence, root_cause, suggested_fix, raw_analysis_json)
2. Alembic migration: add `failure_patterns` table (id, repo, pattern_hash, failure_type, first_seen, last_seen, occurrence_count, example_run_ids)
3. `cifi/persistence.py` — Store analysis results, query history
4. `cifi/patterns.py` — Hash-based recurring pattern detection (normalized error message + failure type → pattern_hash)
5. API endpoints: `GET /api/failures` (list), `GET /api/failures/{id}` (detail), `GET /api/patterns/{repo}` (recurring patterns)
6. Flag recurring failures in PR comments ("⚠️ This failure has occurred 5 times in the last 7 days")
7. Tests for persistence and pattern detection logic

**Verification**:
- Failure records stored in DB after analysis
- Recurring patterns detected when same error appears 3+ times
- API returns failure history and pattern data
- PR comments flag recurring failures

**Human Checkpoint**: Review DB schema, pattern detection logic, API design. **MVP is complete here.**

---

## Phase 5: Infrastructure — Docker + EKS + Terraform

**Goal**: Deploy CIFI on AWS EKS via Terraform. Legitimate cloud infrastructure experience.

**Steps**:
1. `k8s/namespace.yaml` — dedicated `cifi` namespace
2. `k8s/backend/` — Deployment (liveness/readiness → `/api/health`) + Service + init container for Alembic migrations
3. `k8s/frontend/` — Deployment + Service (built React app via nginx)
4. `k8s/ingress.yaml` — Ingress routing, ALB for webhook endpoint
5. `k8s/secrets.yaml.example` — template only, never commit real values
6. `k8s/kustomization.yaml` — Kustomize base
7. `terraform/` — VPC + subnets, EKS cluster (1 node group, t3.medium), RDS PostgreSQL (db.t3.micro), ECR, ALB, IAM roles
8. Makefile targets: `k8s-deploy`, `k8s-status`, `terraform-plan`, `terraform-apply`

**Verification**:
- All pods Running in `cifi` namespace, readiness probes pass
- Webhook endpoint accessible via ALB
- `terraform validate` + `terraform plan` pass
- End-to-end: GitHub failure → webhook to ALB → analysis → PR comment

**Human Checkpoint**: Review K8s manifests, Terraform plan, security groups, IAM policies.

---

## Phase 6: Dashboard + CLI + MCP Server + Polish

**Goal**: Add the web dashboard, CLI tool, MCP server, Slack integration, and polish for launch.

**Steps**:
1. **Dashboard**: Adapt the existing React frontend — recent failures list, recurring pattern tracker, per-repo failure rate chart, single failure detail view
2. **CLI** (`cli/`): `cifi analyze <run_id>`, `cifi history <repo>`, `cifi patterns <repo>`, `cifi status`, `cifi watch` — Python + `typer`
3. **MCP Server** (`cifi/mcp_server.py`): Expose tools — `analyze_failure(run_id)`, `get_failure_history(repo, days)`, `get_recurring_patterns(repo)`, `get_fix_suggestions(run_id)`
4. **Slack integration**: Output Router sends failure summaries to a Slack channel via webhook
5. **Observability**: Structured JSON logging, `/api/metrics` endpoint, basic Prometheus metrics (`failures_analyzed_total`, `analysis_latency_seconds`, `llm_errors_total`)
6. **README**: Architecture diagram, demo GIF, install instructions, interview-ready documentation
7. Makefile targets: `cli-install`, `cli-test`, `mcp-test`

**Verification**:
- Dashboard shows failure history and patterns
- CLI commands work end-to-end
- MCP tools callable from AI agent workflows
- Slack messages delivered on failure
- README makes a hiring manager stop scrolling

**Human Checkpoint**: Review dashboard UX, CLI help text, MCP tool design, README quality. **Full version complete.**

---

## Execution Principles

| Principle | How |
|---|---|
| **Incremental delivery** | Each phase produces a working artifact. Never advance with broken tests. |
| **Human-in-the-loop** | Pause after each phase for review/approval before advancing. |
| **Test continuously** | Every phase adds tests. After Phase 3, CI runs them automatically on every push. |
| **Start local, go remote** | Phases 1–4 are local. Phase 5 adds cloud. Phase 6 adds polish. |
| **One concern at a time** | Don't mix analysis engine with infrastructure. Isolation reduces debugging surface. |
| **Real over impressive** | Every component solves an actual problem. No padding. |

---

## Decisions

- **full-stack-fastapi-template as the foundation** — production-realistic (FastAPI + React + PostgreSQL + JWT auth + email), reused for webhook receiver, API, and dashboard
- **Copy (not fork) the template** — own the code, modify freely, pin to `0.10.0`
- **`cifi/` as the core engine package** — separate from the FastAPI `backend/` app, clean domain boundary
- **Force JSON from LLM** — structured prompts + schema validation, never parse free-form text
- **Hash-based pattern detection** — fast, cheap, deterministic (no LLM calls for comparison)
- **Async webhook processing** — LLM calls are slow; return 200 immediately, analyze in background
- **Claude API (primary), OpenAI-compatible (swappable)** — configurable via env, supports Ollama for local dev
- **EKS + Terraform for production** — legitimate K8s + IaC experience
- **MCP server** — differentiating layer that connects CIFI to AI agent workflows
- **ghcr.io for container registry** — free for public repos, native GitHub Actions integration

---

## Further Considerations

1. **Template version pinning**: Pin to release `0.10.0` to avoid breaking changes. Pull updates selectively.
2. **Log scrubbing**: Logs may contain sensitive data — add a scrubbing layer before sending to external LLM APIs.
3. **LLM cost management**: Add per-repo rate limiting on analysis calls. LLM API calls are the primary cost center.
4. **DB migrations in K8s**: Run Alembic as init container or pre-deploy Job — needs careful handling in Phase 5.
5. **Webhook security**: GitHub HMAC signature verification on every incoming request — non-negotiable.