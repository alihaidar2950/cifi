# CIFI — Copilot Instructions

This is **CI Failure Intelligence (CIFI)** — an AI-powered CI failure analysis agent. It uses the `fastapi/full-stack-fastapi-template` (pinned to 0.10.0) as the application foundation — FastAPI + React + PostgreSQL + Docker Compose + JWT auth.

## Key Docs
- `docs/PLAN.md` — Full phased implementation plan (6 phases)
- `docs/HLD.md` — High-level architecture
- `docs/DD.md` — Detailed design (component-level)
- `docs/NORTH_STAR.md` — Vision and success criteria
- `.github/instrctions/pr-instructions.md` — Agent workflow for commit, push, and pull request actions

## Current Phase
Phase 1 — Adopt Full-Stack FastAPI Template

## Project Structure
- `backend/` — FastAPI app (webhook receiver, API layer, from template)
- `frontend/` — React + TypeScript app (dashboard, from template)
- `cifi/` — Core engine: log ingestion, preprocessor, AI analyzer, patterns (Phase 2+)
- `cli/` — Developer CLI: `cifi analyze`, `cifi history`, etc. (Phase 6)
- `k8s/` — Kubernetes manifests (Phase 5)
- `terraform/` — IaC for AWS EKS + supporting infra (Phase 5)

## Conventions
- All commands go through the root `Makefile`
- K8s manifests use Kustomize, deployed to `cifi` namespace
- No secrets hardcoded — use env vars and K8s Secrets
- Test every phase before advancing to the next
- Python code uses FastAPI patterns from the template
- Backend tests: pytest; Frontend tests: Playwright
- Force JSON output from LLM — always validate against Pydantic schema
- Async webhook processing — return 200 immediately, analyze in background
- When user requests push or PR actions, follow `.github/instrctions/pr-instructions.md`