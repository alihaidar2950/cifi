# Squad Team

> CIFI — AI-powered CI failure analysis agent (Python)

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work, enforces handoffs and reviewer gates. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| Ripley | Lead | .squad/agents/ripley/charter.md | 🏗️ Active |
| Dallas | Core Dev | .squad/agents/dallas/charter.md | 🔧 Active |
| Parker | DevOps | .squad/agents/parker/charter.md | ⚙️ Active |
| Lambert | Tester | .squad/agents/lambert/charter.md | 🧪 Active |
| Scribe | Scribe | .squad/agents/scribe/charter.md | 📋 Active |
| Ralph | Work Monitor | .squad/agents/ralph/charter.md | 🔄 Active |

## Project Context

- **User:** Ali
- **Project:** CIFI (CI Failure Intelligence)
- **Description:** AI-powered CI failure analysis agent with two-tier architecture
- **Stack:** Python, Pydantic, pytest, FastAPI, React/TypeScript, Docker, Kubernetes (Kustomize), Terraform
- **Current Phase:** Phase 1 — Core Engine (log preprocessor, LLM analyzer, schemas)
- **Tier 1:** GitHub Action — embedded in target repos, multi-provider LLM analysis, posts PR comments
- **Tier 2 (optional):** FastAPI + PostgreSQL on EKS — aggregation, dashboard, MCP server, CLI
- **Key Docs:** docs/PLAN.md, docs/HLD.md, docs/DD.md, docs/NORTH_STAR.md
- **Created:** 2026-03-25
- **Universe:** Alien
