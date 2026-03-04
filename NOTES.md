# OpenFounder — Development Notes

## 2026-03-04: Project Kickoff

### Research Phase Complete
- Deep-dived Polsia, MetaGPT, CrewAI, market trends
- Identified the gap: no open-source full-scope AI co-founder
- Designed architecture leveraging existing OpenClaw infra (70% reuse)

### Key Decisions Made
- Build on OpenClaw native orchestration (no CrewAI/LangGraph)
- PostgreSQL for state (isolated Docker container)
- Nightly CEO Loop via cron
- Discord for Phase 1 interaction, dashboard for Phase 2
- Docker isolation for development (don't touch workspace)
- Apache 2.0 license

### Architecture Insight
The whole thing is ~10 scripts and a database schema. No frameworks, no abstractions. State + prompts + delegation. The CEO prompt is the product — everything else is plumbing.

### Sir Abhi's Questions (Answered)
1. **Discord vs dashboard?** — Discord Phase 1, Mission Control Phase 2
2. **CI/CD?** — GitHub Actions (lint, tests against Postgres container), simple deploy via git pull
3. **Open source how?** — Public GitHub repo, Docker Compose for one-command setup
4. **Docker isolation?** — Yes, separate Postgres container, dev in Docker
5. **Notes folder?** — This file + PLAN.md

### Decisions Locked In
1. **First venture:** OpenFounder itself (meta — tracks its own development)
2. **Autonomy:** Full autonomy, approvals for posting/sending externally
3. **GitHub:** `openfounder` org (independent branding)
4. **LLM:** General endpoint, provider-agnostic (Claude, OpenAI, Gemini, local)

### Next Steps
- Get Sir Abhi's GitHub credentials → create `openfounder/openfounder` repo
- Start Day 1: Docker + database schema
