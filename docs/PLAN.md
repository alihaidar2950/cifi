# Implementation Plan — CI Failure Intelligence (CIFI)

## TL;DR

Build an AI-powered CI failure analysis tool — a real AI engineering product with hybrid intelligence, multi-provider LLM integration, and structured prompting:

- **Phase 1 — Core Engine**: Python package with hybrid AI analysis (rule engine + multi-provider LLM fallback). Structured prompting, Pydantic validation, provider-agnostic architecture. **The AI engineering showcase.**
- **Phase 2 — GitHub Action**: Package the engine as a GitHub Action. 3 lines of YAML, instant value. Publish to Marketplace. **Ship the product.**
- **Phase 3 — Deploy + API**: Lightweight FastAPI service deployed via Docker on a simple cloud platform (Fly.io / Railway / Cloud Run). Just enough to have a live endpoint.
- **Phase 4 — Adoption + Growth**: Real users, blog post, demo content, marketplace traction. **Prove it solves a real problem.**

Phases 1-2 prove you can design and build AI-powered developer tools. Phase 3 proves you can ship. Phase 4 proves the product works in the real world.

**Deferred:** Deep infrastructure (EKS, Terraform modules, Kustomize overlays, Prometheus/Grafana), React dashboard, MCP server, CLI, Slack integration. These add operational complexity without adding AI engineering signal — build later if needed.

---

## Phase 1: Core Engine — Hybrid AI Analysis

**Goal**: Build the `cifi/` Python package — an AI-powered analysis engine with a hybrid architecture that combines deterministic pattern matching with multi-provider LLM intelligence.

**Steps**:
1. Create `cifi/` package with clean module structure
2. `cifi/rules.py` — Rule engine: 50+ regex patterns covering common CI failure modes (test failures, build errors, infra errors, config errors). Each rule has: pattern, failure_type, confidence, fix_template
3. `cifi/preprocessor.py` — Intelligent log preprocessing: strip ANSI codes/timestamps, detect error boundaries, extract stack traces and assertion failures, truncate intelligently to fit LLM context window. This is where the real engineering lives — quality of analysis depends on quality of preprocessing.
4. `cifi/analyzer.py` — Hybrid analyzer: run rule engine first (free, instant), fall back to LLM if no high-confidence match. Provider-agnostic LLM integration supporting GitHub Models API, Claude, OpenAI, and Ollama via a shared protocol
5. `cifi/schemas.py` — Pydantic models: `AnalysisResult` (failure_type, confidence, root_cause, contributing_factors, suggested_fix, relevant_log_lines). Force structured JSON output from LLM — always validate against schema
6. `cifi/llm/` — Multi-provider LLM integration: `base.py` (provider protocol), `github_models.py`, `claude.py`, `openai_provider.py`, `ollama.py`. Each provider handles auth, request formatting, response parsing, and retries
7. `cifi/prompts.py` — Prompt engineering: system prompt design, context window management, few-shot examples for edge cases, output format enforcement
8. `cifi/config.py` — Configuration: LLM provider, model, API keys via env vars
9. `cifi/ingestion.py` — Log ingestion: read CI logs and source code from local filesystem
10. Tests with realistic failure fixtures (test failures, build errors, infra errors, timeouts)
11. Root `Makefile` with targets: `test`, `lint`, `analyze-local`

**AI Engineering Highlights**:
- Hybrid architecture: deterministic rules for speed + LLM for depth
- Provider-agnostic LLM integration via Python protocol classes
- Structured prompting with JSON enforcement and Pydantic validation
- Intelligent context window management (prioritize error region > stack trace > source > diff)
- Few-shot prompt design for edge cases
- Cost optimization: 70% of failures resolved without LLM call

**Verification**:
- Rule engine correctly identifies common failure patterns from fixture logs
- Preprocessor strips noise and extracts error regions
- Hybrid analyzer uses rules when possible, falls back to LLM
- LLM response validated against Pydantic schema — malformed responses caught and retried
- All tests pass with mocked LLM responses (no API key needed)
- Manual run with real API key returns valid `AnalysisResult`

**Human Checkpoint**: Review rule patterns, preprocessor quality, prompt design, LLM provider architecture, output schema.

---

## Phase 2: GitHub Action — Ship the Product

**Goal**: Package the core engine as a GitHub Action. When a CI step fails, CIFI analyzes the failure and posts a PR comment. Publish to GitHub Marketplace.

**Steps**:
1. Create `action.yml` — GitHub Action metadata (name, description, inputs, runs)
2. `action/entrypoint.py` — Main entry point: read CI logs, read source code from `$GITHUB_WORKSPACE`, run hybrid analyzer, post PR comment
3. `action/Dockerfile` — Container Action image with cifi package installed
4. PR comment formatting — Markdown template with failure type, root cause, suggested fix, relevant log lines, analysis method indicator (rule engine vs LLM)
5. GitHub API integration — Post PR comment using `GITHUB_TOKEN` (provided automatically)
6. GitHub Models API integration — Free LLM fallback using `GITHUB_TOKEN` (zero config)
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
- Published and installable from GitHub Marketplace

**Human Checkpoint**: Review Action metadata, entrypoint, PR comment format, demo on real repo. **Product shipped.**

---

## Phase 3: Deploy + API

**Goal**: Deploy a lightweight FastAPI service that exposes the hybrid analyzer as an API. Simple Docker-based deployment on a managed platform — no complex infrastructure.

**Steps**:

### 3a. Minimal API
1. Simple FastAPI app in `backend/` — `GET /api/health`, `POST /api/analyze` (accepts log payload, runs hybrid analyzer, returns result)
2. Dockerfile for the API
3. Docker Compose for local development
4. Basic request validation and rate limiting
5. Structured JSON logging
6. Makefile targets: `api-build`, `api-run`, `api-test`

### 3b. Deployment
1. Deploy Docker container to Fly.io, Railway, or Cloud Run (pick simplest)
2. Environment variables for LLM provider config
3. Health check endpoint for platform monitoring
4. HTTPS via platform (automatic on Fly.io/Railway/Cloud Run)
5. GitHub Actions workflow: test → build → deploy on push to main

### 3c. CI/CD
1. GitHub Actions workflow for the API: lint → test → Docker build → deploy
2. Automated deployment on merge to main
3. Health check verification after deploy

**Verification**:
- API accessible at public URL
- `POST /api/analyze` accepts log payload and returns `AnalysisResult`
- Health check passes
- CI/CD pipeline deploys automatically on push
- API handles concurrent requests without issues

**Human Checkpoint**: Review API code, deployment config, CI/CD pipeline. **Live service.**

---

## Phase 4: Adoption + Growth

**Goal**: Get real users, create demo content, and establish CIFI as a legitimate open-source tool.

**Steps**:
1. **README**: Architecture diagram, demo GIF, install instructions (3-line quick start), badges
2. **Action README**: Marketplace listing with clear value prop, all inputs/outputs documented, examples
3. **Blog post**: Write about the hybrid AI analysis approach — how rule engines and LLMs complement each other
4. **Demo video**: Record a real CI failure → CIFI analysis → PR comment flow
5. **Real-world testing**: Add CIFI to 3-5 public repos (your own + open source contributions)
6. **Security hardening**: Log scrubbing before LLM, input validation audit
7. **Marketplace optimization**: Good description, screenshots, categories for discoverability

**Verification**:
- README makes a developer want to try it immediately
- Demo GIF shows real failure → analysis → fix cycle
- At least 3 repos using CIFI with real failure analyses
- Blog post published
- All tests pass in CI

**Human Checkpoint**: Review README quality, demo, real-world usage. **Portfolio-ready.**

---

## Deferred — Future Enhancements

These features add value but don't help demonstrate AI engineering skills. Build them after Phases 1-4 are complete, if desired.

| Feature | What It Does | Notes |
|---|---|---|
| **Deep Infrastructure (EKS/Terraform)** | Production-grade K8s deployment with Terraform modules | Only if targeting infra/platform roles specifically |
| **Kustomize + Prometheus/Grafana** | Multi-environment K8s + observability stack | Same — infra career signal |
| **Central API + Persistence** | FastAPI server receiving results from Tier 1, PostgreSQL storage, failure pattern detection | Product feature, not AI engineering signal |
| **React Dashboard** | Web UI showing failure history, trends, recurring patterns | Frontend, not AI signal |
| **CLI Tool** | `cifi history`, `cifi patterns`, `cifi status` via typer | Nice-to-have |
| **MCP Server** | Expose CIFI tools to AI agent workflows | AI-adjacent, good for later |
| **Slack Integration** | Failure summaries posted to Slack channels | Product feature |

The lightweight API in Phase 3 is designed so that these features can be added incrementally later without rearchitecting.

---

## Execution Principles

| Principle | How |
|---|---|
| **AI engineering is the star** | The hybrid analysis architecture, LLM integration, and prompt design are the core showcase |
| **Ship the product first** | Phases 1-2 prove you can build and ship AI-powered software |
| **Deploy simply** | Phase 3 uses Docker + managed platform. No infrastructure rabbit holes. |
| **Get real users** | Phase 4 proves the product solves a real problem |
| **Incremental delivery** | Each phase produces a working artifact. Never advance with broken tests. |
| **Human-in-the-loop** | Pause after each phase for review/approval before advancing. |
| **Test continuously** | Every phase adds tests. CI runs them automatically on every push. |
| **Real over impressive** | Every component solves an actual problem. No padding. |

---

## Decisions

| Decision | Rationale |
|---|---|
| **AI engineering > infrastructure** | Multi-provider LLM integration, hybrid analysis, structured prompting = AI Engineer profile. Deep Terraform/EKS doesn't help with AI roles. |
| **Hybrid analysis (rules + LLM)** | Demonstrates AI engineering judgment: know when to use deterministic code vs. when to use LLM. Cost-optimized. |
| **Multi-provider LLM architecture** | Provider-agnostic design via Python protocols. Shows real LLM integration experience, not just "call OpenAI API". |
| **Structured prompting + Pydantic** | Force JSON output, validate against schema. Production-grade LLM integration, not notebook demos. |
| **Simple deployment (Docker + managed platform)** | Deploy is a means, not the goal. Fly.io/Railway gives you a live URL without infrastructure complexity. |
| **GitHub Marketplace** | Real distribution channel. Real users. Proves the product ships. |
| **GitHub Action as Tier 1** | Zero infra, marketplace distribution, 3-line adoption. The right distribution model. |
| **Deferred deep infra** | EKS/Terraform/Kustomize are valuable but are a separate career signal. Don't dilute the AI engineering story. |

---

## Project Structure

```
cifi/               # Core engine: rules, preprocessor, analyzer, schemas
  llm/              # Multi-provider LLM integration (claude, openai, github-models, ollama)
  prompts.py        # Prompt engineering: system prompts, few-shot examples
  rules.py          # Rule engine: 50+ patterns
  preprocessor.py   # Log preprocessing and context extraction
  analyzer.py       # Hybrid analyzer: rules first, LLM fallback
  schemas.py        # Pydantic models for structured output
action/             # GitHub Action: entrypoint, Dockerfile, action.yml
backend/            # Lightweight API for deployment (Phase 3)
docs/               # Design docs: HLD, DD, Plan, North Star
.github/            # Copilot instructions, CI/CD pipelines
```
