# CIFI — CI Failure Intelligence

AI-powered CI failure analysis agent. CIFI watches your pipelines, diagnoses failures, and delivers actionable root cause summaries — so you fix the issue in 5 minutes instead of spending 40 triaging logs.

---

## What It Does

When a CI pipeline fails, CIFI:

1. **Detects** the failure via GitHub Actions webhook
2. **Fetches** raw logs, test output, and the git diff
3. **Preprocesses** — strips noise, extracts the actual error region
4. **Analyzes** — sends structured context to an LLM, gets a validated JSON root cause analysis
5. **Delivers** — posts a summary to the PR comment, Slack, and/or the web dashboard
6. **Tracks** — stores results, detects recurring failure patterns over time

---

## Architecture

```
GitHub Actions
       |
  [Failure Event]
       ▼
  Webhook Receiver (FastAPI)
       ▼
  Log Ingestion Engine (GitHub API)
       ▼
  Preprocessor (strip noise, extract errors)
       ▼
  AI Analysis Pipeline (Claude / OpenAI → structured JSON)
       ▼
  ┌─────────┬──────────┬───────────┐
  │ Postgres │ PR Comment│   Slack   │
  │(history) │(GitHub API)│(webhook) │
  └─────────┴──────────┴───────────┘
       ▼
  Web Dashboard (React)
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | React, TypeScript |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| AI | Claude API (primary), OpenAI-compatible (swappable) |
| Infrastructure | Docker Compose (local), AWS EKS + Terraform (prod) |
| CI/CD | GitHub Actions |
| Auth | JWT (from FastAPI template) |

Built on top of [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) (v0.10.0).

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+ (for frontend)

### Run Locally

```bash
# Clone and start all services
git clone https://github.com/alihaidar2950/autonomous-devex-platform.git
cd autonomous-devex-platform
cp .env.example .env   # Configure your secrets
make up

# Run backend tests
make test-backend

# Run frontend E2E tests
make test-e2e
```

- Frontend: http://localhost
- API docs: http://localhost/api/docs
- Health check: http://localhost/api/health

---

## Project Structure

```
backend/        # FastAPI app — webhook receiver, API, auth
frontend/       # React dashboard — failure history, patterns, trends
cifi/           # Core engine — ingestion, preprocessor, analyzer, patterns
cli/            # Developer CLI — cifi analyze, cifi history, etc.
k8s/            # Kubernetes manifests (Kustomize)
terraform/      # AWS EKS + supporting infrastructure
docs/           # Design docs — HLD, DD, Plan, North Star
```

---

## Roadmap

- [x] Phase 1 — Adopt Full-Stack FastAPI Template
- [ ] Phase 2 — Core Engine (log ingestion + AI analysis)
- [ ] Phase 3 — GitHub Integration (webhooks + PR comments)
- [ ] Phase 4 — Persistence + Pattern Detection (MVP complete)
- [ ] Phase 5 — Infrastructure (EKS + Terraform)
- [ ] Phase 6 — Dashboard + CLI + MCP Server + Polish

---

## Documentation

- [Implementation Plan](docs/PLAN.md) — Phased delivery plan with verification steps
- [High-Level Design](docs/HLD.md) — System architecture and component breakdown
- [Detailed Design](docs/DD.md) — Implementation-level component specifications
- [North Star](docs/NORTH_STAR.md) — Vision, success criteria, and guiding principles

---

## License

See [LICENSE](LICENSE) for details.
