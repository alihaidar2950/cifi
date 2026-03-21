High-Level Design — CI Failure Intelligence (CIFI)
System Overview
CIFI is an AI-powered CI failure analysis agent. It listens for pipeline failures, ingests logs and context, runs them through an LLM-based analysis pipeline, and delivers structured root cause summaries to developers where they already work — GitHub PRs, Slack, or a web dashboard.
---
Architecture Diagram
```
GitHub Actions / Jenkins
         |
    [Failure Event]
         |
         ▼
  ┌─────────────────┐
  │  Webhook         │  ← FastAPI service, receives pipeline events
  │  Receiver        │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Log Ingestion   │  ← Fetches raw logs, test output, git diff
  │  Engine          │     via GitHub API / Jenkins API
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  Preprocessor    │  ← Strips noise, extracts relevant sections,
  │                  │     truncates to LLM context window safely
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  AI Analysis     │  ← LLM call (Claude / OpenAI)
  │  Pipeline        │     Structured prompt → structured JSON output
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  MCP Server      │  ← Exposes CIFI tools to AI agent workflows
  │  (optional)      │     analyze_failure / get_history / get_patterns
  └────────┬────────┘
           │
     ┌─────┴──────┐
     │            │
     ▼            ▼
┌─────────┐  ┌──────────┐
│Postgres  │  │ Output   │
│(history) │  │ Router   │
└─────────┘  └────┬─────┘
                  │
       ┌──────────┼──────────┐
       ▼          ▼          ▼
  PR Comment   Slack Msg  Dashboard
  (GitHub API) (Webhook)  (FastAPI +
                           simple UI)
```
---
Component Breakdown
1. Webhook Receiver
What it does: Entry point for the system. Receives POST events from GitHub Actions or Jenkins when a pipeline fails.
Tech: FastAPI, runs in Docker, exposed via a public endpoint (ngrok locally, Load Balancer on EKS in prod)
Inputs:
GitHub Actions: `workflow_run` webhook event (status: failure)
Jenkins: Post-build webhook plugin
Outputs: Triggers the Log Ingestion Engine asynchronously
Key design decision: Async processing — the webhook returns 200 immediately and queues the analysis job. Avoids timeout issues with slow LLM calls.
---
2. Log Ingestion Engine
What it does: Given a failed run ID, fetches all relevant context needed for analysis.
Tech: Python, GitHub REST API (`PyGithub`), Jenkins API
Fetches:
Raw CI logs (stdout/stderr of failed steps)
Test output (pytest results, JUnit XML if available)
Git diff of the triggering commit
PR description and title (if triggered by a PR)
Previous run result (was this passing before?)
Key design decision: Fetch only what's needed. Logs can be 50k+ lines — the ingestion layer is responsible for identifying the failing step and pulling only that step's logs, not the entire run.
---
3. Preprocessor
What it does: Cleans and structures raw log data before it hits the LLM.
Responsibilities:
Strip ANSI escape codes and timestamps
Identify the specific failing step (error boundary detection)
Extract stack traces, assertion failures, error messages
Truncate intelligently to fit within LLM context window (with priority given to the error region)
Build a structured context object for the analysis prompt
Key design decision: The quality of the LLM output is directly proportional to the quality of the input. The preprocessor is where most of the engineering work lives — not the LLM call itself.
---
4. AI Analysis Pipeline
What it does: Sends preprocessed context to an LLM and extracts a structured analysis.
Tech: Anthropic Claude API (primary), OpenAI-compatible (swappable via config)
Prompt structure:
```
System: You are a CI failure analyst. Given pipeline logs, a git diff,
and test output, identify the root cause of the failure and suggest a fix.
Always respond in valid JSON matching the schema provided.

User: [structured context from preprocessor]
```
Output schema (JSON):
```json
{
  "failure_type": "test_failure | build_error | infra_error | timeout | unknown",
  "confidence": "high | medium | low",
  "root_cause": "One sentence summary of what went wrong",
  "contributing_factors": ["factor 1", "factor 2"],
  "suggested_fix": "Specific actionable suggestion",
  "relevant_log_lines": ["line 1", "line 2"],
  "recurring": true | false,
  "similar_past_failures": ["run_id_1", "run_id_2"]
}
```
Key design decision: Force JSON output via system prompt + response format enforcement. Never parse free-form LLM text — always validate against schema.
---
5. MCP Server
What it does: Exposes CIFI's capabilities as tools consumable by AI agents and developer workflows.
Tech: Python MCP SDK
Exposed tools:
```
analyze_failure(run_id)         → Run analysis on a specific CI run
get_failure_history(repo, days) → Return recent failure trends
get_recurring_patterns(repo)    → Return failures that repeat across runs
get_fix_suggestions(run_id)     → Return suggested fixes for a given failure
```
Why this matters: This is the differentiating layer. It turns CIFI from a standalone tool into something pluggable into any AI agent workflow — including the kind of developer automation you already built at Ford. It's also a direct demonstration of your MCP server experience to any hiring manager reading the repo.
---
6. Persistence Layer
What it does: Stores failure history, analysis results, and pattern data.
Tech: PostgreSQL, SQLAlchemy ORM
Schema (simplified):
```sql
-- Core failure record
failures (
  id, repo, run_id, branch, commit_sha,
  triggered_at, failure_type, confidence,
  root_cause, suggested_fix, raw_analysis_json
)

-- Pattern tracking
failure_patterns (
  id, repo, pattern_hash, failure_type,
  first_seen, last_seen, occurrence_count,
  example_run_ids[]
)
```
Key design decision: `pattern_hash` is generated by hashing the normalized error message + failure type. This is how recurring failures are detected without LLM calls for every comparison.
---
7. Output Router
What it does: Takes the analysis result and delivers it to the right destination(s).
Destinations:
Destination	Trigger	Format
GitHub PR Comment	Failure on a PR branch	Markdown summary with code blocks
Slack Message	All failures	Short summary + link to dashboard
Dashboard	All failures	Stored and rendered in web UI
Terminal (CLI)	Manual invocation	Rich terminal output
---
8. Web Dashboard
What it does: Provides a simple UI showing failure history, trends, and pattern analysis.
Tech: FastAPI (backend) + HTMX or simple React (frontend)
Views:
Recent failures list with root cause summaries
Recurring pattern tracker (failures seen 3+ times)
Per-repo failure rate over time (simple chart)
Single failure detail view with full analysis
Key design decision: Keep this genuinely simple. The value is in the data, not the UI. Resist the urge to make it a full dashboard product.
---
9. CLI Tool
What it does: Lets developers interact with CIFI from the terminal.
Tech: Python + `typer` or `click`
Commands:
```bash
cifi analyze <run_id>         # Analyze a specific failed run
cifi history <repo>           # Show recent failure history
cifi patterns <repo>          # Show recurring failure patterns
cifi status                   # Check CIFI service health
cifi watch                    # Stream live failure events
```
---
Infrastructure Design
Local Development
```
Docker Compose
├── cifi-api          (FastAPI app)
├── postgres          (failure history)
├── ngrok             (expose webhook endpoint for GitHub)
└── redis             (optional: job queue for async processing)
```
Production (AWS)
```
Terraform provisions:
├── VPC + subnets
├── EKS cluster (1 node group, t3.medium)
├── RDS PostgreSQL (db.t3.micro)
├── ECR (container registry)
├── ALB (Application Load Balancer → webhook endpoint)
└── IAM roles + policies

Kubernetes manifests:
├── cifi-api Deployment (2 replicas)
├── cifi-api Service + Ingress
├── ConfigMap (non-secret config)
└── Secret (API keys, DB credentials)
```
---
Data Flow — End to End
```
1. Developer pushes commit to GitHub
2. GitHub Actions pipeline runs and fails
3. GitHub sends webhook POST to CIFI ALB endpoint
4. Webhook Receiver returns 200, queues analysis job
5. Log Ingestion Engine fetches logs + diff via GitHub API
6. Preprocessor extracts error region, builds context object
7. AI Analysis Pipeline calls Claude API, receives JSON analysis
8. Persistence layer stores result, checks for recurring pattern
9. Output Router posts PR comment + Slack message
10. Dashboard updated with new failure record
11. Developer reads 3-line summary, fixes issue in 5 minutes
```
---
Security Considerations
Webhook signature verification (GitHub HMAC secret) — validate every incoming request
API keys stored in Kubernetes Secrets / AWS Secrets Manager — never in code or env files
Logs may contain sensitive data — add a scrubbing layer before sending to external LLM APIs
Rate limiting on the webhook endpoint — prevent abuse
LLM API calls are the cost center — add per-repo rate limiting
---
Observability (Minimal but Real)
Structured JSON logging throughout (no print statements)
`/health` and `/metrics` endpoints on the FastAPI service
Basic Prometheus metrics: `failures_analyzed_total`, `analysis_latency_seconds`, `llm_errors_total`
These can be scraped by Grafana if desired — but this is not the focus of the project
---
Key Design Decisions — Summary
Decision	Choice	Rationale
Async processing	Yes (background tasks)	LLM calls are slow; can't block webhook response
Force JSON from LLM	Yes	Reliable parsing; no prompt-output ambiguity
Pattern detection method	Hash-based, not LLM-based	Fast, cheap, deterministic
Infrastructure	EKS + Terraform	Legitimate K8s + IaC experience for resume
MCP layer	Yes	Differentiating; reuses existing skillset
Frontend	Minimal (HTMX or simple React)	Value is in analysis, not UI
LLM provider	Swappable via config	Not locked to one vendor
---
What This Project Proves to a Hiring Manager
Skill	Evidence in CIFI
CI/CD systems	Deep understanding of pipeline failure modes
Python	FastAPI, SQLAlchemy, async patterns, CLI tooling
AI / LLM integration	Structured prompting, JSON output enforcement, MCP server
Kubernetes	EKS deployment, manifests, service/ingress
Terraform	Full AWS infrastructure provisioned as code
System design	Async processing, separation of concerns, scalable architecture
Developer empathy	Built to solve a real problem real engineers have every day
