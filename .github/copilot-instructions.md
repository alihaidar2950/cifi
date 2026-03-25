# CIFI — Copilot Instructions

This is **CI Failure Intelligence (CIFI)** — an AI-powered CI failure analysis agent with a two-tier architecture:

- **Tier 1 — GitHub Action**: Embedded in target repos. Reads logs + source code from the checkout, runs hybrid analysis (rule engine first, LLM fallback), posts PR comments. Zero infrastructure.
- **Tier 2 — Central Server** (optional): FastAPI + PostgreSQL on EKS. Aggregates data across repos, dashboard, MCP server, CLI.

## Key Docs
- `docs/PLAN.md` — Full phased implementation plan (6 phases)
- `docs/HLD.md` — Two-tier architecture design
- `docs/DD.md` — Detailed design (component-level)
- `docs/NORTH_STAR.md` — Vision and success criteria
- `.github/instrctions/pr-instructions.md` — Agent workflow for commit, push, and pull request actions

## Current Phase
Phase 1 — Core Engine (rule engine + preprocessor + analyzer)

## Project Structure
- `cifi/` — Core engine: rule engine, preprocessor, analyzer, schemas (shared by both tiers)
- `action/` — GitHub Action: entrypoint, Dockerfile, action.yml (Tier 1)
- `backend/` — Tier 2 FastAPI server (Phase 3+)
- `frontend/` — Tier 2 React dashboard (Phase 4+)
- `cli/` — Developer CLI: `cifi history`, `cifi patterns`, etc. (Phase 4+)
- `k8s/` — Kubernetes manifests (Phase 5)
- `terraform/` — IaC for AWS EKS + supporting infra (Phase 5)

## Conventions
- All commands go through the root `Makefile`
- Two-tier: Tier 1 (GitHub Action) works alone, Tier 2 (Central Server) is optional
- Hybrid analysis: rule engine first (free, instant), LLM fallback for complex failures
- K8s manifests use Kustomize, deployed to `cifi` namespace
- No secrets hardcoded — use env vars, GitHub Actions secrets, and K8s Secrets
- Test every phase before advancing to the next
- Force JSON output from LLM — always validate against Pydantic schema
- When user requests push or PR actions, follow `.github/instrctions/pr-instructions.md`