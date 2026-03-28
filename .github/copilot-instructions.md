# CIFI — Copilot Instructions

This is **CI Failure Intelligence (CIFI)** — an AI-powered CI failure analysis agent with a hybrid AI analysis core:

- **Tier 1 — GitHub Action**: Embedded in target repos. Reads logs + source code from the checkout, runs hybrid AI analysis (rule engine first, multi-provider LLM fallback), posts PR comments. Zero infrastructure.
- **Tier 2 — Lightweight API** (Phase 3): Simple FastAPI service deployed via Docker on a managed platform (Fly.io / Railway / Cloud Run).

## Key Docs
- `docs/PLAN.md` — 4-phase implementation plan (AI engine → ship → deploy → adopt)
- `docs/HLD.md` — Architecture design
- `docs/DD.md` — Detailed design (component-level)
- `docs/NORTH_STAR.md` — Vision and success criteria
- `.github/instrctions/pr-instructions.md` — Agent workflow for commit, push, and pull request actions

## Current Phase
Phase 1 — Core Engine (hybrid AI analysis: rule engine + multi-provider LLM + structured prompting)

## Build Priority
- Phase 1-2: Core AI Engine + GitHub Action (the AI engineering showcase — ship the product)
- Phase 3: Deploy + API — lightweight FastAPI service via Docker on a managed platform
- Phase 4: Adoption + Growth — real users, blog post, marketplace traction
- Deferred: Deep infrastructure (EKS/Terraform/Kustomize), React dashboard, MCP server, CLI, Slack

## Project Structure
- `cifi/` — Core AI engine: rule engine, preprocessor, hybrid analyzer, schemas, multi-provider LLM integration
- `cifi/llm/` — Multi-provider LLM: base protocol, claude, openai, github-models, ollama
- `action/` — GitHub Action: entrypoint, Dockerfile, action.yml (Tier 1)
- `backend/` — Lightweight API for Docker deployment (Phase 3)

## Conventions
- All commands go through the root `Makefile`
- Two-tier: Tier 1 (GitHub Action) works alone, API deployment is Phase 3
- Hybrid AI analysis: rule engine first (free, instant), multi-provider LLM fallback for complex failures
- Provider-agnostic LLM integration via Python protocol classes
- Force JSON output from LLM — always validate against Pydantic schema
- No secrets hardcoded — use env vars and GitHub Actions secrets
- Test every phase before advancing to the next
- Simple deployment: Docker + managed platform. No infrastructure rabbit holes.
- When user requests push or PR actions, follow `.github/instrctions/pr-instructions.md`
