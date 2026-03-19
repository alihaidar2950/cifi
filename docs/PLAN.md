# Implementation Plan — Autonomous DevEx Platform (ADEP) v2

## TL;DR

Adopt the **full-stack-fastapi-template** (FastAPI + React + PostgreSQL + Docker Compose + JWT auth) as the production-realistic application, then layer Kubernetes orchestration, enhanced CI/CD, Prometheus/Grafana observability, a data ingestion pipeline, AI failure analysis, and a developer CLI on top. Each phase is independently testable with explicit human checkpoints.

**What the template gives us for free**: Full-stack app with auth, Docker Compose, Traefik reverse proxy, Postgres, pre-commit hooks, pytest + Playwright tests, basic GitHub Actions CI, Alembic migrations, email-based password recovery via Mailcatcher.

**What we build**: K8s deployment, observability stack, data pipelines, AI analyzer, developer CLI, and optional IaC.

---

## Phase 1: Adopt the Full-Stack FastAPI Template

**Goal**: Get the template running locally, verify tests pass, integrate into the ADEP repo.

**Steps**:
1. Copy the template (pinned to release `0.10.0`) into the repo — `backend/`, `frontend/`, `compose.yml`, `compose.override.yml`, `.env`, `scripts/`, etc.
2. Regenerate secrets in `.env` (`SECRET_KEY`, `POSTGRES_PASSWORD`, `FIRST_SUPERUSER_PASSWORD`)
3. Run `docker compose up -d`, verify all services start
4. Run existing tests: `docker compose exec backend pytest`
5. Add a `/api/health` endpoint (needed for K8s probes later)
6. Create a root `Makefile` with targets: `up`, `down`, `test-backend`, `test-e2e`, `logs`
7. Update `README.md`

**Verification**:
- All containers healthy (`docker compose ps` shows all services "Up")
- `make test-backend` passes
- Frontend loads at `http://localhost`; Swagger UI at `http://localhost/api/docs`
- `/api/health` returns `{"status": "ok"}`

**Human Checkpoint**: Review structure, confirm app runs end-to-end, check `.env` for secrets.

---

## Phase 2: Kubernetes Deployment

**Goal**: Deploy the full stack (backend + frontend + PostgreSQL) on a local Kind cluster.

**Steps**:
1. `k8s/namespace.yaml` — dedicated `adep` namespace
2. `k8s/postgres/` — StatefulSet + Service + PVC + Secret
3. `k8s/backend/` — Deployment (liveness/readiness → `/api/health`) + Service + init container for Alembic migrations
4. `k8s/frontend/` — Deployment + Service (built React app via nginx)
5. `k8s/ingress.yaml` — Ingress routing `/api` → backend, `/` → frontend (replaces Traefik from Docker Compose)
6. `k8s/secrets.yaml.example` — template only, never commit real values
7. `k8s/kustomization.yaml` — Kustomize base
8. Makefile targets: `k8s-cluster`, `k8s-deploy`, `k8s-status`, `k8s-port-forward`, `k8s-teardown`
9. Build and `kind load docker-image` for backend + frontend

**Verification**:
- All pods `Running` in `adep` namespace, readiness probes pass
- Login works via port-forward, DB migrations applied
- `kubectl get pods -n adep` shows healthy pods for backend, frontend, postgres

**Human Checkpoint**: Review K8s manifests (especially secrets handling), validate health probes.

---

## Phase 3: CI/CD Pipeline (Enhanced GitHub Actions)

**Goal**: Extend the template's existing CI with image builds, K8s validation, and registry push.

**Steps**:
1. Review and adapt existing `.github/workflows/` from the template
2. Add/extend jobs: **test-backend** → **test-frontend** → **build-images** → **push-images** (ghcr.io, `main` only) → **validate-k8s** (dry-run)
3. Optional manual deploy workflow
4. Document branch protection

**Verification**:
- Push triggers CI, all jobs pass
- Images pushed to ghcr.io on merge to `main`
- K8s manifests validated (no syntax errors)

**Human Checkpoint**: Review workflows, push a test commit, verify on GitHub Actions tab.

---

## Phase 4: Observability (Prometheus + Grafana)

**Goal**: Instrument backend with metrics, add structured logging, deploy monitoring stack.

**Steps**:
1. Add `prometheus-fastapi-instrumentator` to backend deps → expose `/api/metrics`
2. Add `structlog` for structured JSON logging (request_id, path, status, duration)
3. Deploy `k8s/prometheus/` (scrape config targeting `/api/metrics`) + `k8s/grafana/` (provisioned dashboard JSON)
4. Add metrics test + Makefile targets: `k8s-deploy-monitoring`, `k8s-port-forward-prometheus`, `k8s-port-forward-grafana`

**Verification**:
- `/api/metrics` returns Prometheus format
- Prometheus UI shows backend as "UP" target
- Grafana dashboard loads with request rate, latency percentiles, error rate panels
- Structured JSON logs visible in `kubectl logs`

**Human Checkpoint**: Review instrumentation, scrape config, Grafana dashboard, log output.

---

## Phase 5: Data Ingestion Pipeline

**Goal**: Modular pipeline integrated with the existing PostgreSQL database.

**Steps**:
1. Create `pipeline/` — `ingest.py` (fetch → validate → transform → store), `config.py`, tests, sample data
2. Pipeline writes to the same Postgres DB → data visible through the existing API/UI
3. `pipeline/Dockerfile` + `k8s/pipeline/job.yaml` (K8s Job for on-demand runs)
4. Makefile targets: `pipeline-run`, `pipeline-test`, `k8s-pipeline-run`

**Verification**:
- Unit tests pass
- Pipeline stores data in Postgres, queryable via the backend API
- K8s Job completes successfully

**Human Checkpoint**: Review pipeline architecture, DB schema impact, test coverage.

---

## Phase 6: AI Failure Analyzer

**Goal**: LLM-powered root-cause analysis from logs + metrics.

**Steps**:
1. Create `ai/` — `analyzer.py`, `prompts.py`, `config.py` (OpenAI-compatible, configurable base URL for Ollama/local)
2. Returns structured JSON: `root_cause`, `severity`, `suggested_fixes`, `confidence`
3. Tests with mocked HTTP responses, realistic failure fixtures (OOM, 5xx, timeout)
4. Makefile targets: `ai-test`, `ai-analyze`

**Verification**:
- Mocked tests pass in CI (no API key needed)
- Manual run with real API key returns structured analysis
- `grep -r "API_KEY\|SECRET" --include="*.py"` → only env-var references

**Human Checkpoint**: Review prompts, output schema, error handling, security.

---

## Phase 7: Developer CLI

**Goal**: Unified `adep` CLI tying all subsystems together.

**Steps**:
1. Click-based CLI with commands: `adep up`, `adep deploy`, `adep status`, `adep logs`, `adep ingest`, `adep analyze`, `adep test`
2. Each command wraps the corresponding subsystem
3. Tests via Click test runner, installable via `pyproject.toml`
4. Makefile targets: `cli-install`, `cli-test`

**Verification**:
- `adep --help` shows all commands
- Full integration: `adep deploy && adep status && adep ingest && adep analyze`

**Human Checkpoint**: Review CLI UX, help text, test coverage.

---

## Phase 8 (Optional): Infrastructure as Code (Terraform)

**Goal**: Terraform for provisioning K8s cluster + supporting infra.

**Steps**:
1. `terraform/main.tf`, `variables.tf`, `outputs.tf`
2. Modules for cluster + registry provisioning

**Verification**: `terraform validate` + `terraform plan` pass. Human approves before `apply`.

---

## Execution Principles

| Principle | How |
|---|---|
| **Incremental delivery** | Each phase produces a working artifact. Never advance with broken tests. |
| **Human-in-the-loop** | Pause after each phase for review/approval before advancing. |
| **Test continuously** | Every phase adds tests. After Phase 3, CI runs them automatically on every push. |
| **Start local, go remote** | Phases 1-2 are local. Phase 3 adds CI. Phase 8 (optional) adds cloud. |
| **One concern at a time** | Don't mix K8s setup with observability. Isolation reduces debugging surface. |

---

## Decisions

- **full-stack-fastapi-template as the app** — production-realistic (FastAPI + React + PostgreSQL + JWT auth + email)
- **Copy (not fork) the template** — own the code, modify freely, pin to `0.10.0`
- **Kind over Minikube** — lighter, Docker-native, better CI compatibility
- **ghcr.io for container registry** — free for public repos, native GitHub Actions integration
- **Replace Traefik with K8s Ingress** in Phase 2 (nginx-ingress, K8s-native routing)
- **Alembic migrations as init container** in K8s (before backend starts)
- **Pipeline writes to same Postgres** — data visible through existing API/UI
- **Click for CLI** — composable commands, built-in test runner
- **OpenAI-compatible API with configurable base URL** — supports Ollama for local dev

---

## Further Considerations

1. **Template version pinning**: Pin to release `0.10.0` to avoid breaking changes. Pull updates selectively.
2. **Traefik → Ingress transition**: Key architectural shift in Phase 2. Docker Compose uses Traefik; K8s uses nginx-ingress controller.
3. **DB migrations in K8s**: Run Alembic as init container or pre-deploy Job — needs careful handling in Phase 2.