# North Star — CI Failure Intelligence (CIFI)

## Vision

Build an AI-powered agent that autonomously diagnoses CI pipeline failures, identifies root causes, and delivers actionable fix suggestions — eliminating the manual log-triage loop that drains engineering time across every team running CI at scale.

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

CIFI watches CI pipelines. When a failure occurs, it:

- Pulls the raw logs, test output, and diff from the triggering commit
- Sends them through an AI analysis pipeline
- Returns a structured, human-readable root cause summary
- Posts the summary directly to the PR or Slack channel
- Tracks recurring failure patterns over time

Engineers stop triaging logs. They read a three-line summary and fix the issue.

---

## Why This Project — Career Context

This project exists to solve a real problem **and** to serve a deliberate career purpose.

| Career Goal | How CIFI Serves It |
|---|---|
| Escape QA/embedded framing | Demonstrates platform-level ownership, not test execution |
| Add cloud/infra keywords legitimately | Deployed on AWS EKS, provisioned via Terraform |
| Showcase AI tooling depth | MCP server integration, LLM-powered analysis pipeline |
| Public proof of skills | Fully open-source, demoable, yours to own in interviews |
| Target DevEx/Platform roles | Directly solves a Developer Experience problem |

This is not a resume checkbox project. It is a real tool that solves a real problem, built in a way that happens to cover the skills gap precisely.

---

## Success Criteria

### Minimum Viable (Week 6)
- [ ] Monitors a GitHub Actions pipeline
- [ ] Triggers analysis on failure
- [ ] Returns a structured root cause summary (failure type, likely cause, suggested fix)
- [ ] Posts output to PR comment
- [ ] Clean README with demo GIF

### Full Version (Week 12)
- [ ] Deployed on AWS EKS via Terraform
- [ ] Failure pattern tracking across runs (recurring failures flagged)
- [ ] Slack integration
- [ ] Simple web dashboard showing failure history and trends
- [ ] CLI tool (`cifi analyze`, `cifi history`, `cifi status`)
- [ ] Support for Jenkins (in addition to GitHub Actions)

### Stretch
- [ ] Self-hosted LLM option (Ollama) for teams that can't send logs to external APIs
- [ ] Auto-creates GitHub issue with triage summary when failure recurs 3+ times
- [ ] Embeddings-based similarity search across historical failures

---

## What This Project Is Not

- Not a full observability platform (Prometheus/Grafana belongs elsewhere)
- Not a general-purpose AI coding assistant
- Not a replacement for writing good tests
- Not a microservices demo — intentionally single-service focused

Scope discipline is a feature. A sharp tool beats a sprawling one every time.

---

## Guiding Principles

**Real over impressive.** Every component should solve an actual problem, not exist to pad the architecture diagram.

**Depth over breadth.** One well-understood system beats five half-understood ones.

**Deployable beats theoretical.** If it doesn't run, it doesn't exist.

**Your story, your code.** This is public, owned by you, and something you can speak to completely in any interview.

---

## Target Audience (for the tool itself)

- Engineering teams of 10–200 engineers running CI on GitHub Actions or Jenkins
- Platform/DevEx engineers responsible for CI reliability
- Any team where CI failure triage is a recurring time sink

---

## Technology Choices — Why

| Tool | Why |
|---|---|
| GitHub Actions | Most portable, most familiar to hiring teams, free for public repos |
| Python | Your strongest language, dominant in AI/tooling space |
| FastAPI | Lightweight, async, well-suited for a webhook receiver |
| Claude / OpenAI API | Best-in-class log analysis, easy to swap between |
| MCP Server | Differentiating — connects CIFI to AI agent workflows, a skill you already have |
| Kubernetes (kind/minikube → EKS) | Legitimate K8s experience, deployable locally first |
| Terraform | Infrastructure-as-code for EKS + supporting resources |
| PostgreSQL | Simple, proven persistence for failure history |
| Docker | Containerization, already in your skillset |

---

## Timeline

| Phase | Weeks | Deliverable |
|---|---|---|
| 1 — Core Engine | 1–2 | Log ingestion + AI analysis pipeline working locally |
| 2 — GitHub Integration | 3–4 | Webhook receiver, PR comment posting, demo on real repo |
| 3 — Persistence + Patterns | 5–6 | DB layer, failure history, recurring pattern detection — **MVP complete** |
| 4 — Infrastructure | 7–8 | Dockerized, deployed on EKS via Terraform |
| 5 — Observability + CLI | 9–10 | Basic dashboard, CLI tool, Slack integration |
| 6 — Polish + Launch | 11–12 | README, demo video, blog post, LinkedIn post |

---

## Definition of Done

CIFI is done when:
- A developer can install it in under 10 minutes
- It catches and summarizes a real CI failure without human intervention
- It is deployed on real cloud infrastructure
- You can demo it live in an interview and explain every design decision
- The GitHub repo has a README that makes a hiring manager stop scrolling
