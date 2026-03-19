# ADEP — Copilot Instructions

This is the **Autonomous DevEx Platform (ADEP)**. It uses the `fastapi/full-stack-fastapi-template` (pinned to 0.10.0) as the base application — FastAPI + React + PostgreSQL + Docker Compose + JWT auth.

## Key Docs
- `docs/PLAN.md` — Full phased implementation plan (8 phases)
- `docs/HLD.md` — High-level architecture
- `docs/DD.md` — Detailed design
- `docs/NORTH_STAR.md` — Vision and success criteria
- `.github/instrctions/pr-instructions.md` — Agent workflow for commit, push, and pull request actions

## Current Phase
Phase 1 — Adopt Full-Stack FastAPI Template

## Project Structure
- `backend/` — FastAPI app (from template)
- `frontend/` — React + TypeScript app (from template)
- `k8s/` — Kubernetes manifests (Phase 2+)
- `pipeline/` — Data ingestion pipeline (Phase 5)
- `ai/` — AI failure analyzer (Phase 6)
- `cli/` — Developer CLI (Phase 7)
- `terraform/` — IaC (Phase 8, optional)

## Conventions
- All commands go through the root `Makefile`
- K8s manifests use Kustomize, deployed to `adep` namespace
- No secrets hardcoded — use env vars and K8s Secrets
- Test every phase before advancing to the next
- Python code uses FastAPI patterns from the template
- Backend tests: pytest; Frontend tests: Playwright
- When user requests push or PR actions, follow `.github/instrctions/pr-instructions.md`