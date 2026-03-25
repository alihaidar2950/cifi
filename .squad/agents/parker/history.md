# Parker — History

## Project Context

CIFI (CI Failure Intelligence) — AI-powered CI failure analysis agent.
- **User:** Ali
- **Stack:** Docker, GitHub Actions, Kubernetes (Kustomize), Terraform
- **Current Phase:** Phase 1 — Core Engine (Action packaging comes in Phase 2)
- **Tier 1:** GitHub Action — reads CI logs + source code from checkout, posts PR comments
- **Tier 2:** FastAPI + PostgreSQL on EKS (Phase 3+)
- **Infra principle:** No secrets hardcoded, K8s uses Kustomize in `cifi` namespace

## Learnings

(none yet)
