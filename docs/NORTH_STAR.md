# North Star — CI Failure Intelligence (CIFI)

## Vision

Build an AI-powered CI failure analysis agent that lives inside your GitHub Actions workflow — add 3 lines, get instant root cause analysis on every failure. No infrastructure. No configuration. No log triage.

Optionally, deploy a central server to track patterns across repos, serve a dashboard, and integrate with AI agent workflows via MCP.

---

## The Problem Worth Solving

Every engineer who runs CI pipelines knows this loop:

1. Pipeline fails
2. Engineer opens logs — 3,000 lines of noise
3. Engineer searches for the actual error buried in the middle
4. Engineer context-switches, loses flow, spends 20–40 minutes triaging
5. The fix takes 5 minutes. The diagnosis took 40.

This happens dozens of times per day across any engineering team. It is solved nowhere well. It is ripe for automation.

---

## What CIFI Does

CIFI runs **inside** your CI pipeline as a GitHub Action. When a step fails, it:

- Reads the CI logs and source code directly from the checkout (full repo context)
- Runs a rule engine against 50+ known failure patterns (instant, free)
- Falls back to LLM analysis for complex failures (GitHub Models API / Claude / OpenAI)
- Posts a structured root cause summary + suggested fix as a PR comment
- Optionally sends results to a central server for pattern tracking and dashboards

Engineers stop triaging logs. They read a three-line summary and fix the issue.

### The Key Insight
By running inside the CI pipeline (not as an external webhook receiver), CIFI has the full checkout — source code, dependencies, config files, test fixtures. This solves the context problem that limits external CI analysis tools.

---

## Why This Project — Career Context

This project exists to solve a real problem **and** to serve a deliberate career purpose.

| Career Goal | How CIFI Serves It |
|---|---|
| Escape QA/embedded framing | Demonstrates platform-level ownership, not test execution |
| Add cloud/infra keywords legitimately | Tier 2 deployed on AWS EKS, provisioned via Terraform |
| Showcase AI tooling depth | Hybrid analysis, MCP server, structured prompting |
| GitHub Actions expertise | Custom Action published to marketplace |
| Public proof of skills | Fully open-source, demoable, yours to own in interviews |
| Target DevEx/Platform roles | Directly solves a Developer Experience problem |
| Progressive architecture | Simple → complex, demonstrating system design maturity |

---

## Success Criteria

### Minimum Viable (Tier 1 — GitHub Action)
- [ ] GitHub Action that analyzes CI failures with 3 lines of config
- [ ] Rule engine handles ~70% of common failures instantly (no LLM cost)
- [ ] LLM fallback for complex failures via GitHub Models API (free)
- [ ] Posts structured PR comment with root cause + suggested fix
- [ ] Works on any repo — just add the Action to a workflow
- [ ] Clean README with demo GIF

### Full Version (Tier 1 + Tier 2)
- [ ] Central FastAPI server receiving results from Tier 1 across repos
- [ ] Deployed on AWS EKS via Terraform
- [ ] Failure pattern tracking (recurring failures flagged)
- [ ] Web dashboard showing failure history and trends
- [ ] CLI tool (`cifi history`, `cifi patterns`, `cifi status`)
- [ ] MCP server for AI agent integration
- [ ] Slack integration

### Stretch
- [ ] Self-hosted LLM option (Ollama) for teams that can't send logs externally
- [ ] Auto-creates GitHub issue when a failure recurs 3+ times
- [ ] Custom rule definitions per repo (`.cifi/rules.yml`)
- [ ] Support for GitLab CI and Jenkins

---

## What This Project Is Not

- Not a full observability platform (Prometheus/Grafana belongs elsewhere)
- Not a general-purpose AI coding assistant
- Not a replacement for writing good tests
- Not over-engineered — Tier 1 is a single Action, Tier 2 is a single service

Scope discipline is a feature. A sharp tool beats a sprawling one every time.

---

## Guiding Principles

**Real over impressive.** Every component should solve an actual problem, not exist to pad the architecture diagram.

**Depth over breadth.** One well-understood system beats five half-understood ones.

**Deployable beats theoretical.** If it doesn't run, it doesn't exist.

**Progressive complexity.** Tier 1 works alone with zero infra. Tier 2 adds value when you're ready.

**Your story, your code.** This is public, owned by you, and something you can speak to completely in any interview.

---

## Target Audience (for the tool itself)

- Any developer with a GitHub Actions workflow who's tired of triaging CI logs
- Engineering teams of 10–200 engineers running CI at scale
- Platform/DevEx engineers responsible for CI reliability

---

## Technology Choices — Why

| Tool | Why |
|---|---|
| GitHub Actions | Tier 1 runs here — full repo context, marketplace distribution, free for public repos |
| Python | Strongest language, dominant in AI/tooling space |
| Rule Engine (regex) | Handles 70% of failures instantly, for free, no API key needed |
| GitHub Models API | Free LLM access via GITHUB_TOKEN — default fallback |
| Claude / OpenAI | Higher quality LLM analysis, swappable via config |
| Ollama | Self-hosted option for privacy-sensitive teams |
| FastAPI | Tier 2 backend — lightweight, async, well-suited for API + dashboard |
| MCP Server | Differentiating — connects CIFI to AI agent workflows |
| Kubernetes (EKS) | Tier 2 deployment — legitimate K8s experience |
| Terraform | Infrastructure-as-code for EKS + supporting resources |
| PostgreSQL | Simple, proven persistence for failure history |
| Docker | Containerization for Tier 2 |

---

## Timeline

| Phase | Deliverable |
|---|---|
| 1 — Core Engine | Rule engine + preprocessor + analyzer working locally |
| 2 — GitHub Action | Tier 1 published, works on real repos, posts PR comments |
| 3 — Central API | Tier 2 FastAPI server, receives results, persistence layer |
| 4 — Patterns + Dashboard | Recurring pattern detection, web dashboard |
| 5 — Infrastructure | EKS + Terraform deployment for Tier 2 |
| 6 — CLI + MCP + Polish | CLI tool, MCP server, Slack, README, demo |

---

## Definition of Done

CIFI is done when:
- A developer can add it to any repo in 3 lines and get CI failure analysis on the next failure
- The rule engine catches common failures without any API key or LLM cost
- Complex failures get accurate LLM analysis via free GitHub Models API
- A central server tracks patterns across repos, deployed on real cloud infrastructure
- You can demo it live in an interview and explain every design decision
- The GitHub repo has a README that makes a hiring manager stop scrolling
