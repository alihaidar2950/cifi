# CIFI — CI Failure Intelligence

AI-powered CI failure analysis that lives inside your GitHub Actions workflow. Add 3 lines, get instant root cause analysis on every failure. No infrastructure required.

---

## What It Does

When a CI step fails, CIFI:

1. **Reads** logs and source code directly from the checkout (full repo context)
2. **Analyzes** failures using multi-provider LLM (GitHub Models API — free with `GITHUB_TOKEN`)
3. **Validates** all output against Pydantic schemas — structured, reliable results
4. **Posts** a structured PR comment with root cause + suggested fix
5. **Tracks** (optional) recurring failure patterns via the backend API

---

## Quick Start

```yaml
# Add to your workflow file
- uses: alihaidar2950/cifi@v1
  if: failure()
  with:
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

That's it. No API keys, no infrastructure, no configuration.

---

## Architecture

CIFI uses a **two-tier architecture** with a **multi-provider LLM analysis core**:

```mermaid
flowchart TB
    subgraph repo["Target Repo (GitHub)"]
        push["Developer pushes commit"] --> ci["GitHub Actions runs"]
        ci -->|on failure| action

        subgraph action["Tier 1 — CIFI GitHub Action"]
            ingest["Log Ingestion\n(local files)"] --> preprocess["Preprocessor"]
            source["Source Code\nContext"] --> preprocess
            preprocess --> llm

            subgraph llm["Multi-Provider LLM Analyzer"]
                providers["Claude | OpenAI | GitHub Models | Ollama"]
                prompt["Structured Prompting\nJSON Enforcement\nPydantic Validation"]
            end

            llm --> comment["PR Comment\n(GitHub API)"]
            llm -->|optional| api_post["POST to API"]
        end
    end

    api_post -->|optional| tier2

    subgraph tier2["Tier 2 — Backend API (Docker)"]
        fastapi["FastAPI + PostgreSQL"]
        endpoints["POST /api/analyze\nGET /api/failures\nGET /api/patterns\nGET /api/health"]
        auth["API Key Auth · SQLAlchemy · Alembic"]
    end

    style action fill:#1a1a2e,stroke:#e94560,color:#fff
    style llm fill:#16213e,stroke:#0f3460,color:#fff
    style tier2 fill:#0f3460,stroke:#e94560,color:#fff
```

### Tier 1 — GitHub Action (Embedded)
Runs inside your CI pipeline. Has full access to source code, logs, and test output. Analyzes failures using multi-provider LLM with structured prompting and posts PR comments. **This is all most teams need.**

### Tier 2 — Backend API (Optional)
A FastAPI backend with PostgreSQL persistence. Stores failure history, detects recurring patterns across repos, and exposes a RESTful API with pagination, filtering, and authentication.

---

## LLM Analysis

```mermaid
flowchart LR
    logs["CI Logs"] --> pre["Preprocessor\nStrip noise · Extract errors"]
    pre --> llm["LLM Provider\n(multi-provider)"]
    llm --> validate["Pydantic\nValidation"]
    validate -->|valid| result["AnalysisResult"]
    validate -->|invalid| retry["Retry"]
    retry --> llm

    style llm fill:#e76f51,stroke:#264653,color:#fff
    style result fill:#264653,stroke:#2a9d8f,color:#fff
```

| Provider | Speed | Cost |
|---|---|---|
| GitHub Models (default) | 3-10s | Free |
| Claude | 3-10s | Pay-per-use |
| OpenAI | 3-10s | Pay-per-use |
| Ollama (self-hosted) | 3-10s | Free (local) |

GitHub Models API is the default provider — free via `GITHUB_TOKEN`, zero configuration needed.

---

## Tech Stack

| Component | Technology |
|---|---|
| Core Engine | Python 3.11+, Pydantic |
| Tier 1 | GitHub Action (Docker container) |
| LLM Providers | GitHub Models API (free), Claude, OpenAI, Ollama |
| Backend API | FastAPI, async Python |
| Database | PostgreSQL, SQLAlchemy 2.0 (async), Alembic |
| Auth | API key middleware |
| Deployment | Docker, Fly.io / Railway / Cloud Run |
| CI/CD | GitHub Actions |

---

## Project Structure

```
cifi/               # Core engine: preprocessor, analyzer, schemas
  llm/              # Multi-provider LLM (claude, openai, github-models, ollama)
action/             # GitHub Action: entrypoint, Dockerfile, action.yml
backend/            # Backend API service (Phase 3)
  routers/          # FastAPI route handlers
  services/         # Business logic layer
  models/           # SQLAlchemy ORM models
  database.py       # DB connection + session management
  auth.py           # API key authentication
  alembic/          # Database migrations
docs/               # Design docs: HLD, DD, Plan, North Star
```

---

## Roadmap

```mermaid
gantt
    title CIFI Development Phases
    dateFormat YYYY-MM-DD
    axisFormat %b %Y

    section Phase 1
    Core Engine (preprocessor + LLM analyzer)  :p1, 2026-03-29, 21d

    section Phase 2
    GitHub Action (Tier 1 — PR comments, Marketplace)     :p2, after p1, 14d

    section Phase 3
    Backend API + PostgreSQL + Auth + Patterns             :p3, after p2, 21d

    section Phase 4
    Adoption (real users, blog, demo, marketplace)         :p4, after p3, 14d
```

- [ ] **Phase 1** — Core Engine: preprocessor + LLM analyzer + multi-provider LLM
- [ ] **Phase 2** — GitHub Action: package as Action, PR comments, publish to Marketplace
- [ ] **Phase 3** — Backend API: FastAPI + PostgreSQL + auth + failure history + pattern detection
- [ ] **Phase 4** — Adoption: real users, blog post, demo content, marketplace traction

---

## Documentation

| Document | Description |
|---|---|
| [HLD](docs/HLD.md) | High-level architecture and design decisions |
| [DD](docs/DD.md) | Detailed design with code-level interfaces |
| [Plan](docs/PLAN.md) | 4-phase implementation plan |
| [North Star](docs/NORTH_STAR.md) | Vision, success criteria, definition of done |

---

## License

[MIT](LICENSE)
