# CIFI — CI Failure Intelligence

AI-powered CI failure analysis that lives inside your GitHub Actions workflow. Add 3 lines, get instant root cause analysis on every failure. No infrastructure required.

---

## What It Does

When a CI step fails, CIFI:

1. **Reads** logs and source code directly from the checkout (full repo context)
2. **Matches** against 50+ known failure patterns via rule engine (~70% of failures, instant, free)
3. **Falls back** to LLM analysis for complex failures (GitHub Models API — free with `GITHUB_TOKEN`)
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

CIFI uses a **two-tier architecture** with a **hybrid AI analysis core**:

```mermaid
flowchart TB
    subgraph repo["Target Repo (GitHub)"]
        push["Developer pushes commit"] --> ci["GitHub Actions runs"]
        ci -->|on failure| action

        subgraph action["Tier 1 — CIFI GitHub Action"]
            ingest["Log Ingestion\n(local files)"] --> preprocess["Preprocessor"]
            source["Source Code\nContext"] --> preprocess
            preprocess --> hybrid

            subgraph hybrid["Hybrid AI Analyzer"]
                rules["Stage 1: Rule Engine\n50+ patterns · instant · free\n~70% coverage"]
                rules -->|miss?| llm

                subgraph llm["Stage 2: Multi-Provider LLM"]
                    providers["Claude | OpenAI | GitHub Models | Ollama"]
                    prompt["Structured Prompting\nJSON Enforcement\nPydantic Validation"]
                end
            end

            hybrid --> comment["PR Comment\n(GitHub API)"]
            hybrid -->|optional| api_post["POST to API"]
        end
    end

    api_post -->|optional| tier2

    subgraph tier2["Tier 2 — Backend API (Docker)"]
        fastapi["FastAPI + PostgreSQL"]
        endpoints["POST /api/analyze\nGET /api/failures\nGET /api/patterns\nGET /api/health"]
        auth["API Key Auth · SQLAlchemy · Alembic"]
    end

    style action fill:#1a1a2e,stroke:#e94560,color:#fff
    style hybrid fill:#16213e,stroke:#0f3460,color:#fff
    style tier2 fill:#0f3460,stroke:#e94560,color:#fff
```

### Tier 1 — GitHub Action (Embedded)
Runs inside your CI pipeline. Has full access to source code, logs, and test output. Performs hybrid analysis (rules first, LLM fallback) and posts PR comments. **This is all most teams need.**

### Tier 2 — Backend API (Optional)
A FastAPI backend with PostgreSQL persistence. Stores failure history, detects recurring patterns across repos, and exposes a RESTful API with pagination, filtering, and authentication.

---

## Hybrid Analysis

```mermaid
flowchart LR
    logs["CI Logs"] --> pre["Preprocessor\nStrip noise · Extract errors"]
    pre --> re{"Rule Engine\n50+ patterns"}
    re -->|"match (70%)"| result["AnalysisResult\n(instant, free)"]
    re -->|"no match (30%)"| llm["LLM Provider\n(3-10s)"]
    llm --> validate["Pydantic\nValidation"]
    validate -->|valid| result
    validate -->|invalid| retry["Retry"]
    retry --> llm

    style re fill:#2d6a4f,stroke:#1b4332,color:#fff
    style llm fill:#e76f51,stroke:#264653,color:#fff
    style result fill:#264653,stroke:#2a9d8f,color:#fff
```

| Stage | Speed | Cost | Coverage |
|---|---|---|---|
| Rule Engine (50+ patterns) | Instant | Free | ~70% of failures |
| LLM Fallback (GitHub Models) | 3-10s | Free | ~95% of failures |

The rule engine handles common failures (assertion errors, missing dependencies, syntax errors, etc.) without any API call. The LLM is only invoked for complex failures the rules don't cover.

---

## Tech Stack

| Component | Technology |
|---|---|
| Core Engine | Python 3.11+, regex rule engine, Pydantic |
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
cifi/               # Core engine: rules, preprocessor, analyzer, schemas
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
    Core Engine (rules + preprocessor + hybrid analyzer)  :p1, 2026-03-29, 21d

    section Phase 2
    GitHub Action (Tier 1 — PR comments, Marketplace)     :p2, after p1, 14d

    section Phase 3
    Backend API + PostgreSQL + Auth + Patterns             :p3, after p2, 21d

    section Phase 4
    Adoption (real users, blog, demo, marketplace)         :p4, after p3, 14d
```

- [ ] **Phase 1** — Core Engine: rule engine + preprocessor + hybrid analyzer + multi-provider LLM
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

---

## Documentation

- [Implementation Plan](docs/PLAN.md) — Phased delivery plan with verification steps
- [High-Level Design](docs/HLD.md) — Two-tier architecture and component breakdown
- [Detailed Design](docs/DD.md) — Implementation-level component specifications
- [North Star](docs/NORTH_STAR.md) — Vision, success criteria, and guiding principles

---

## License

See [LICENSE](LICENSE) for details.
