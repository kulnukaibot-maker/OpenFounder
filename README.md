# OpenFounder

**Your AI co-founder. Open source. Transparent. Yours.**

The first open-source AI co-founder system. A nightly CEO Loop reviews your venture's state, makes strategic decisions, delegates to specialist crews, records every decision transparently, and sends you a morning briefing.

## Why OpenFounder?

No open-source project handles the full co-founder scope: strategy + engineering + marketing + research + operations. Polsia proved the model ($1M ARR) but is closed-source. MetaGPT and CrewAI only handle software dev. OpenFounder fills the gap.

| vs. | OpenFounder wins because |
|-----|------------------------|
| Polsia | Open source, transparent decision log, extensible, self-hosted |
| MetaGPT | Full venture scope, not just software development |
| CrewAI | Production-grade orchestration, not a framework you have to wire up |

## How It Works

```
You describe a venture
        ↓
CEO Loop runs nightly (cron)
        ↓
Reads venture state (Postgres) → Plans priorities → Delegates to crews
        ↓
┌──────────┬──────────┬──────────┬──────────┐
│ Strategy │ Engineer │ Marketing│ Research │
│   Crew   │   Crew   │   Crew   │   Crew   │
└──────────┴──────────┴──────────┴──────────┘
        ↓
Records every decision with reasoning → Sends morning briefing
        ↓
You review, approve what needs approval, and the system executes
```

## Key Features

- **Nightly CEO Loop** — periodic autonomous strategy and delegation
- **Transparent Decision Log** — every AI decision recorded with reasoning and confidence
- **Human-in-the-Loop** — full autonomy on internal decisions, approvals for external actions (posting, sending, spending)
- **Specialist Crews** — strategy, engineering, marketing, research, ops
- **Provider Agnostic** — plug in any LLM (Claude, OpenAI, Gemini, local models)
- **Self-hosted** — your data stays yours

## Quick Start

```bash
git clone https://github.com/kulnukaibot-maker/openfounder.git
cd openfounder
docker compose up -d
python3 scripts/openfounder_setup.py
python3 openfounder/state.py create-venture "MyStartup" --description "..." --goal "..."
python3 scripts/openfounder_ceo.py --venture MyStartup
```

## Architecture

```
                    ┌──────────────────────────────────┐
                    │     HUMAN-IN-THE-LOOP LAYER      │
                    │  Discord / Dashboard / CLI        │
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
                    │     COMPANY STATE (PostgreSQL)    │
                    │  ventures / decisions / metrics   │
                    │  features / bugs / campaigns      │
                    └──────────────────────────────────┘
```

## Project Status

**Stage:** Phase 1 MVP (in development)

See [PLAN.md](PLAN.md) for the full roadmap.

## License

Apache 2.0
