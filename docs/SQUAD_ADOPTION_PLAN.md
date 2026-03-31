# Squad Adoption Plan for CIFI

## What is Squad?

[Squad](https://github.com/bradygaster/squad) is an AI development team orchestrator for GitHub Copilot. It creates persistent, named AI agents that live in your repo as markdown files (`.squad/` directory). Each agent has its own charter (role, expertise, voice), history (what it learned about your project), and routing rules. Agents persist across sessions, share decisions, and compound knowledge over time — it's version-controlled team memory.

**Key difference from plain Copilot**: Instead of a single stateless assistant, you get specialized agents that remember your codebase conventions, past decisions, and architectural context.

---

## Why Squad Fits CIFI

CIFI has properties that make it an ideal Squad candidate:

| CIFI Property | Squad Benefit |
|---|---|
| **6 phases** spanning months of work | Agents accumulate project memory across sessions; no re-explaining decisions |
| **Multi-domain** (Python engine, GitHub Actions, FastAPI, React, K8s, Terraform) | Each agent specializes in one domain — avoids context pollution |
| **Two-tier architecture** with shared core | Routing rules ensure the right agent handles tier-specific vs shared code |
| **Solo developer** building a complex system | Squad acts as a persistent team — reviewer, tester, infra engineer |
| **Formal design docs** (HLD, DD, PLAN) | Agents reference these docs in their charters, staying aligned with the architecture |

---

## Proposed Squad Team

### 1. **Lead** — Architecture & Coordination
- **Role**: Technical lead. Owns the two-tier architecture, phase transitions, and cross-cutting decisions.
- **Expertise**: System design, Python packaging, API contracts between tiers.
- **Reads**: `docs/HLD.md`, `docs/DD.md`, `docs/PLAN.md`, `docs/NORTH_STAR.md`
- **Handles**: Architecture questions, phase readiness reviews, component interface design.

### 2. **Engine** — Core Python Engine (`cifi/`)
- **Role**: Core engine developer. Owns the preprocessor, LLM analyzer, and schemas.
- **Expertise**: Python, log parsing, Pydantic, LLM prompt engineering.
- **Reads**: `cifi/` source, `docs/DD.md` (Tier 1 components section)
- **Handles**: Preprocessor logic, LLM analyzer, schema changes, LLM integration.

### 3. **Action** — GitHub Action (`action/`)
- **Role**: GitHub Action developer. Owns the Tier 1 packaging and delivery.
- **Expertise**: GitHub Actions, Docker, `action.yml` metadata, PR comment formatting, GitHub API.
- **Reads**: `action/`, `.github/workflows/`, `docs/DD.md` (Action entry point section)
- **Handles**: Dockerfile, entrypoint, action.yml inputs, workflow integration, marketplace publishing.

### 4. **Backend** — Tier 2 Server (`backend/`)
- **Role**: API developer. Owns the FastAPI server, database, and aggregation logic.
- **Expertise**: FastAPI, SQLAlchemy, Alembic, PostgreSQL, JWT auth, async Python.
- **Reads**: `backend/`, `docs/DD.md` (Tier 2 components section)
- **Handles**: API endpoints, database migrations, pattern detection, MCP server.
- **Active from**: Phase 3+

### 5. **Frontend** — Dashboard (`frontend/`)
- **Role**: Dashboard developer. Owns the React UI.
- **Expertise**: React, TypeScript, Tailwind, charting libraries, API consumption.
- **Reads**: `frontend/`
- **Handles**: Dashboard components, failure visualization, filtering, trend charts.
- **Active from**: Phase 4+

### 6. **Ops** — Infrastructure (`k8s/`, `terraform/`)
- **Role**: Platform engineer. Owns deployment, infrastructure, and CI/CD pipelines.
- **Expertise**: Kubernetes, Kustomize, Terraform, AWS EKS, Helm, GitHub Actions CI.
- **Reads**: `k8s/`, `terraform/`, `.github/workflows/`
- **Handles**: K8s manifests, Terraform modules, CI pipeline, container builds, secrets management.
- **Active from**: Phase 5+

### 7. **Tester** — Quality Assurance
- **Role**: Test engineer. Owns test strategy and test fixtures across all components.
- **Expertise**: pytest, test fixtures, mocking (LLM responses), E2E testing, coverage.
- **Reads**: `tests/`, fixture files, `Makefile` test targets
- **Handles**: Unit tests, integration tests, failure fixture creation, CI test pipeline validation.

---

## Phase-by-Phase Activation

Not every agent is needed from day one. Squad supports a growing team:

| Phase | Active Agents | Why |
|---|---|---|
| **Phase 1** — Core Engine | Lead, Engine, Tester | Focus on `cifi/` package: rules, preprocessor, analyzer |
| **Phase 2** — GitHub Action | + Action | Package engine as container action, PR comment formatting |
| **Phase 3** — Central API | + Backend | FastAPI server, PostgreSQL, pattern detection |
| **Phase 4** — Dashboard + CLI | + Frontend | React dashboard, CLI tool |
| **Phase 5** — Infrastructure | + Ops | EKS deployment, Terraform, Kustomize |
| **Phase 6** — Polish & Launch | All | Cross-cutting polish, docs, marketplace listing |

Squad makes it easy to add agents later — just create a new charter. Agents you don't need yet don't create noise.

---

## Setup Steps

### 1. Install Squad CLI

```bash
npm install -g @bradygaster/squad-cli
```

### 2. Initialize Squad in CIFI repo

```bash
cd /home/ali/repos/autonomous-devex-platform
squad init
```

This creates `.squad/` with team scaffolding, `squad.agent.md` at the root, and initial templates.

### 3. Customize the Team

After init, edit the generated files:

- `.squad/team.md` — Update roster with the 3 Phase 1 agents (Lead, Engine, Tester)
- `.squad/routing.md` — Map file patterns to agents:
  ```
  cifi/**          → Engine
  tests/**         → Tester
  docs/**          → Lead
  action/**        → Action
  backend/**       → Backend
  frontend/**      → Frontend
  k8s/**,terraform/** → Ops
  Makefile         → Lead
  ```
- `.squad/agents/{name}/charter.md` — Define each agent's identity, expertise, and the CIFI docs they should reference

### 4. Seed Agent Knowledge

Each agent's `charter.md` should reference the relevant CIFI docs so the agent starts with architectural context:

```markdown
# Engine — Charter

## Identity
You are the core engine developer for CIFI, an AI-powered CI failure analysis tool.

## Expertise
- Python, log parsing
- Pydantic schema design
- LLM prompt engineering (structured JSON output)
- Multi-provider LLM integration

## Key References
- `docs/DD.md` — Detailed design, especially Tier 1 components
- `docs/PLAN.md` — Phase 1 requirements
- `cifi/` — Your primary workspace

## Conventions
- All changes go through the root Makefile
- Force JSON output from LLM — validate against Pydantic schemas
- LLM-powered analysis with multi-provider support
- No hardcoded secrets — use environment variables
```

### 5. Start Using Squad

In VS Code, open Copilot Chat and invoke the Squad agent:

```
@squad I'm building the Phase 1 core engine. Let's start with the preprocessor in cifi/preprocessor.py.
Engine, implement the log preprocessing pipeline.
```

Or use the CLI:
```bash
squad shell
squad > @Engine, implement the preprocessor module in cifi/preprocessor.py
squad > @Tester, write pytest fixtures for common CI failure logs
```

### 6. Commit `.squad/` to Git

```bash
git add .squad/ squad.agent.md
git commit -m "feat: initialize Squad AI development team"
```

Anyone who clones the repo gets the full team with accumulated knowledge.

---

## Workflows That Map Well to CIFI

### 1. Parallel Phase 1 Development
```
You: "Team, let's build Phase 1. Engine — start with the preprocessor.
      Tester — create failure log fixtures. Lead — review the DD and flag any gaps."

  🏗️ Lead — reviewing DD.md for completeness...
  🔧 Engine — writing cifi/preprocessor.py...
  🧪 Tester — creating test fixtures...
```

### 2. Cross-Tier Interface Design (Phase 3)
```
You: "Lead, define the API contract between Tier 1 and Tier 2.
      Engine, update the analyzer to support optional Tier 2 posting.
      Backend, scaffold the FastAPI endpoint that receives analysis results."
```

### 3. Issue Triage with `squad triage`
When CIFI has GitHub issues, Squad can auto-triage them to the right agent based on labels/content:
```bash
squad triage --interval 10
```
An issue about "LLM analysis inaccuracy" gets routed to Engine; "dashboard chart broken" goes to Frontend.

### 4. Decision Logging
Every architectural decision gets recorded in `.squad/decisions.md`:
- "Using Pydantic v2 for schema validation"
- "GitHub Models API as default LLM provider (free with GITHUB_TOKEN)"

This becomes a living ADR (Architecture Decision Record) that agents reference.

### 5. Context Hygiene with `squad nap`
As the project grows and agent histories get long:
```bash
squad nap --deep
```
Compresses and prunes old context while preserving key learnings.

---

## What to Watch Out For

| Concern | Mitigation |
|---|---|
| **Squad is Node.js/TypeScript-oriented** | CIFI is Python, but Squad is language-agnostic — it orchestrates Copilot, not compilers. Agent charters just need to specify Python expertise. |
| **Alpha software** | Pin to a specific version (`npm install -g @bradygaster/squad-cli@0.9.1`). Run `squad doctor` regularly. |
| **`.squad/` adds repo size** | The files are small markdown. `squad nap` compresses history. Worth it for persistent context. |
| **Learning curve** | Start with 3 agents (Lead, Engine, Tester). Add more as phases activate. Don't over-engineer the initial team. |
| **Agent quality depends on charter quality** | Invest time in good charters. Reference specific CIFI docs. Update charters as the project evolves. |

---

## Recommended First Session

After setup, run this as your first Squad session to validate everything works:

```
@squad status
@Lead, read docs/PLAN.md and docs/DD.md. Summarize the Phase 1 deliverables
      and flag any gaps or ambiguities.
@Engine, look at the cifi/ directory structure from DD.md and propose the
      module layout with file stubs.
@Tester, propose a test strategy for Phase 1 — what fixtures do we need,
      what should we mock, what's the coverage target?
```

Review the output, confirm the proposals, and Squad starts building with shared context.
