# CIFI — CI Failure Intelligence

AI-powered CI failure analysis that lives inside your GitHub Actions workflow. Add 3 lines, get instant root cause analysis on every failure. No infrastructure required.

---

## What It Does

When a CI step fails, CIFI:

1. **Reads** logs and source code directly from the checkout (full repo context)
2. **Matches** against 50+ known failure patterns via rule engine (~70% of failures, instant, free)
3. **Falls back** to LLM analysis for complex failures (GitHub Models API — free with `GITHUB_TOKEN`)
4. **Posts** a structured PR comment with root cause + suggested fix
5. **Tracks** (optional) recurring failure patterns via a central server

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

## Architecture — Two Tiers

### Tier 1 — GitHub Action (Embedded)
Runs inside your CI pipeline. Has full access to source code, logs, and test output. Performs hybrid analysis (rules first, LLM fallback) and posts PR comments. This is all most teams need.

### Tier 2 — Central Server (Optional)
Aggregates failure data across repos, tracks recurring patterns, serves a web dashboard, and exposes an MCP server + CLI. Deployed on AWS EKS via Terraform.

```
Target Repo CI ──► CIFI Action ──► PR Comment
                       │
                       ▼ (optional)
                  Central Server ──► Dashboard / CLI / MCP / Slack
```

---

## How It Works

### Hybrid Analysis
| Stage | Speed | Cost | Coverage |
|---|---|---|---|
| Rule Engine (50+ patterns) | Instant | Free | ~70% of failures |
| LLM Fallback (GitHub Models) | 3-10s | Free | ~95% of failures |

The rule engine handles common failures (assertion errors, missing dependencies, syntax errors, etc.) without any API call. The LLM is only invoked for complex failures the rules don't cover.

---

## Tech Stack

| Component | Technology |
|---|---|
| Core Engine | Python, regex rule engine, Pydantic |
| Tier 1 | GitHub Action (Docker container) |
| LLM Providers | GitHub Models API (free), Claude, OpenAI, Ollama |
| Tier 2 Backend | FastAPI, SQLAlchemy, Alembic |
| Tier 2 Frontend | React, TypeScript |
| Database | PostgreSQL |
| Infrastructure | AWS EKS + Terraform |
| CLI | Python + typer |
| AI Agent Integration | MCP Server |

---

## Project Structure

```
cifi/               # Core engine: rules, preprocessor, analyzer, schemas
action/             # GitHub Action: entrypoint, Dockerfile, action.yml
backend/            # Tier 2 — FastAPI server (Phase 3+)
frontend/           # Tier 2 — React dashboard (Phase 4+)
cli/                # Developer CLI (Phase 4+)
k8s/                # Kubernetes manifests (Phase 5)
terraform/          # AWS EKS + supporting infra (Phase 5)
docs/               # Design docs: HLD, DD, Plan, North Star
```

---

## Roadmap

- [ ] Phase 1 — Core Engine (rule engine + preprocessor + analyzer)
- [ ] Phase 2 — GitHub Action (Tier 1 — posts PR comments)
- [ ] Phase 3 — Central API + Persistence (Tier 2 foundation)
- [ ] Phase 4 — Dashboard + CLI + MCP Server
- [ ] Phase 5 — Infrastructure (EKS + Terraform)
- [ ] Phase 6 — Polish + Launch

---

## Documentation

- [Implementation Plan](docs/PLAN.md) — Phased delivery plan with verification steps
- [High-Level Design](docs/HLD.md) — Two-tier architecture and component breakdown
- [Detailed Design](docs/DD.md) — Implementation-level component specifications
- [North Star](docs/NORTH_STAR.md) — Vision, success criteria, and guiding principles

---

## License

See [LICENSE](LICENSE) for details.
