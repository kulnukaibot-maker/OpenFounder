# OpenFounder — Open-Source AI Co-Founder

**Tagline:** "Your AI co-founder. Open source. Transparent. Yours."
**Status:** Planning
**Started:** 2026-03-04

---

## What Is This?

The first open-source AI co-founder system. A nightly CEO Loop reads your venture's state, makes strategic decisions, delegates to specialist crews (strategy, engineering, marketing, research, ops), records every decision transparently, and sends a morning briefing. Built on OpenClaw.

**Key differentiators vs. Polsia (closed-source, $1M ARR):**
- Open source (Apache 2.0)
- Transparent decision log (every AI decision recorded with reasoning)
- Extensible (add your own agents/crews)
- Self-hosted (your data stays yours)

---

## Architecture

```
                    ┌──────────────────────────────────┐
                    │     HUMAN-IN-THE-LOOP LAYER      │
                    │  Discord (Phase 1) / Dashboard    │
                    │  Approval Queue / Notifications   │
                    └───────────────┬──────────────────┘
                                    │
                    ┌───────────────▼──────────────────┐
                    │     CEO LOOP (Nightly Cron)       │
                    │  Read state → Plan → Delegate     │
                    │  → Record decisions → Report      │
                    └───────────────┬──────────────────┘
                                    │
          ┌────────────┬────────────┼────────────┬────────────┐
          ▼            ▼            ▼            ▼            ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ Strategy │ │ Engineer │ │ Marketing│ │ Research  │ │   Ops    │
    │   Crew   │ │   Crew   │ │   Crew   │ │   Crew   │ │   Crew   │
    └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
                                    │
                    ┌───────────────▼──────────────────┐
                    │     COMPANY STATE (Postgres)      │
                    │  ventures / decisions / metrics   │
                    │  features / bugs / campaigns      │
                    └───────────────┬──────────────────┘
                                    │
                    ┌───────────────▼──────────────────┐
                    │     OPENCLAW GATEWAY (:18789)     │
                    │  spawn_agent / cron / MCP / exec  │
                    └───────────────┬──────────────────┘
                                    │
              ┌──────────┬──────────┼──────────┬──────────┐
              ▼          ▼          ▼          ▼          ▼
          Discord    Notion    Claude Code  Pinchtab   Brave
```

---

## Technical Decisions

| Decision | Choice | Why |
|---|---|---|
| Framework | OpenClaw native (no CrewAI/LangGraph) | spawn_agent is proven; CrewAI's delegation is broken |
| State store | PostgreSQL (isolated Docker container) | Multi-agent concurrency, queryable decisions |
| CEO Loop | Cron (nightly at 6 AM PST) | Polsia-validated; predictable cost; batched thinking |
| Language | Python | Matches existing 87 OpenClaw scripts |
| CEO model | Sonnet 4.6 (default) | Cost-efficient; can escalate to Opus per-task |
| Packaging | Standalone core + OpenClaw plugin | Works with or without OpenClaw |
| License | Apache 2.0 | Permissive, enterprise-friendly |
| Dev environment | Docker Compose | Isolated from workspace, reproducible |
| Interaction (Phase 1) | Discord | Zero new UI, already working |
| Interaction (Phase 2) | Mission Control dashboard | FastAPI + HTML, hosted on VPS |

---

## Build Order (Phase 1 MVP: ~10 days)

### Day 1: Docker + Database
- [ ] `Dockerfile` and `docker-compose.yml`
- [ ] PostgreSQL 16 container (isolated, not VPS Postgres)
- [ ] `migrations/001_initial_schema.sql` — ventures, features, bugs, decisions, metrics, campaigns, approvals

### Day 2-3: State Manager
- [ ] `openfounder/state.py` — Postgres CRUD with CLI interface, JSON I/O
- [ ] Commands: create-venture, get-state, add-feature, add-bug, add-metric, add-decision, submit-approval, resolve-approval, decisions
- [ ] Unit tests

### Day 4-5: CEO System Prompt + Loop
- [ ] `openfounder/prompts/ceo_system.md` — the core prompt (role, input format, output format)
- [ ] `scripts/openfounder_ceo.py` — reads state, injects into prompt, calls Claude, writes decisions, delegates, reports
- [ ] Manual test runs, iterate on prompt quality

### Day 5-6: Crew Prompts
- [ ] `openfounder/prompts/research_crew.md`
- [ ] `openfounder/prompts/engineering_crew.md`
- [ ] `openfounder/prompts/marketing_crew.md`
- [ ] Only 3 crews for MVP (strategy handled by CEO Loop itself)

### Day 6: Marketing Agent
- [ ] Register `marketing` agent in OpenClaw
- [ ] Exec allowlist configuration
- [ ] Test delegation from CEO Loop

### Day 7: Cron + Approvals
- [ ] CEO Loop cron job in `jobs.json` (6 AM PST daily)
- [ ] Discord approval flow (notification → reply → resolve)
- [ ] Test end-to-end cron → briefing → approval cycle

### Day 8: First Venture
- [ ] Bootstrap a real venture
- [ ] Seed initial state (features, metrics, goals)
- [ ] Run CEO Loop, verify morning briefing quality
- [ ] Iterate on prompts

### Day 9-10: Polish + Decision Log
- [ ] Decision log viewer (`state.py decisions <vid> --days 7`)
- [ ] Error handling, retry logic
- [ ] Integration tests (mock venture → CEO Loop → valid plan)

---

## Phase 2 (Month 2)
- Infrastructure provisioner (GitHub, Neon, Railway auto-setup)
- [x] Multi-venture support (`scripts/openfounder_ceo_all.py` — iterates all active ventures)
- [x] Engineering crew (deep Claude Code integration) — completed in Phase 1
- [x] Full marketing crew (content calendar, social, cold outreach) — completed in Phase 1
- [x] Finance crew (`crews/finance.py` + `prompts/finance_crew.md` + `migrations/002_finance_tables.sql`)
- [x] Mission Control dashboard (`dashboard/app.py` — FastAPI + embedded HTML, port 8111)

## Phase 3 (Month 3+)
- GitHub public repo: `openclaw/openfounder`
- `docker-compose.yml` for one-command setup
- HN Show launch, Reddit, Twitter
- ClawHub package: `clawhub install openfounder`
- "Add your own agent" contributor tutorial

---

## Directory Structure

```
openfounder/
├── PLAN.md                    ← this file
├── NOTES.md                   ← ongoing development notes
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── openfounder/
│   ├── __init__.py
│   ├── config.py              # env-based config loader
│   ├── state.py               # Postgres-backed company state
│   ├── ceo_loop.py            # Nightly CEO loop orchestrator
│   ├── executor.py            # Code executor (branch, apply, test, commit)
│   ├── approval.py            # Human-in-the-loop approval system
│   ├── crews/
│   │   ├── base.py
│   │   ├── engineering.py
│   │   ├── finance.py         # Phase 2: revenue tracking, budget enforcement
│   │   ├── marketing.py
│   │   └── research.py
│   ├── dashboard/
│   │   ├── app.py             # Phase 2: FastAPI + embedded HTML dashboard
│   │   └── static/            # Optional static file overrides
│   ├── prompts/
│   │   ├── ceo_system.md
│   │   ├── research_crew.md
│   │   ├── engineering_crew.md
│   │   ├── marketing_crew.md
│   │   └── finance_crew.md    # Phase 2
│   └── migrations/
│       ├── 001_initial_schema.sql
│       └── 002_finance_tables.sql  # Phase 2: budgets, expenses, revenue
├── scripts/
│   ├── openfounder_ceo.py     # CLI entry for CEO Loop (single venture)
│   ├── openfounder_ceo_all.py # Phase 2: multi-venture CEO loop
│   ├── openfounder_dashboard.py # Phase 2: launch Mission Control
│   ├── openfounder_setup.py   # One-time DB setup
│   └── openfounder_venture.py # Venture management CLI
├── tests/
│   ├── test_state.py
│   ├── test_ceo_loop.py
│   └── test_approval.py
└── openclaw-plugin/           # OpenClaw-specific integration
    ├── SKILL.md
    ├── mcp_extensions.py
    └── cron_jobs.json
```

---

## Research References

- **Polsia:** polsia.com — Solo founder (Ben Broca), Claude Opus 4.6, nightly CEO loop, 1100+ companies, $1M ARR in 1 month. Closed source.
- **MetaGPT:** github.com/FoundationAgents/MetaGPT — 64.7k stars, SOP-driven dev team simulation. Software dev only.
- **CrewAI:** github.com/crewAIInc/crewAI — 45.1k stars, $24.5M funded, best framework but hierarchical delegation broken in prod.
- **ChatDev:** github.com/OpenBMB/ChatDev — 31.4k stars, virtual dev company with drag-and-drop canvas.
- **Market:** AI agent market $7.6B (2025) → $52.6B (2030). 95% of AI pilots fail. Only 11% of enterprises have agents in production.
- **Gap:** No open-source project handles full co-founder scope (strategy + marketing + ops + fundraising + engineering).

---

## Decisions (Resolved)
- [x] **First venture:** OpenFounder itself (meta — AI co-founder manages its own development)
- [x] **Autonomy level:** Full autonomy, approvals required for posting/sending externally
- [x] **GitHub org:** `openfounder` (independent branding, clean)
- [x] **LLM providers:** General endpoint to hook any provider (Claude, OpenAI, Gemini, local models)

## Open Questions
- [ ] GitHub repo setup (pending Sir Abhi's login credentials)
- [x] VPS port for Mission Control dashboard → **8111** (configurable via `DASHBOARD_PORT`)
