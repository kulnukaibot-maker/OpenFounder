# OpenFounder

**Your AI co-founder. Open source. Transparent. Yours.**

The first open-source AI co-founder system. A nightly CEO Loop reviews your venture's state, makes strategic decisions, delegates to specialist crews, records every decision transparently, and sends you a morning briefing.

## Why OpenFounder?

No open-source project handles the full co-founder scope: strategy + engineering + marketing + finance + research. Polsia proved the model ($1M ARR in one month) but is closed-source. MetaGPT and CrewAI only handle software dev. OpenFounder fills the gap.

| vs. | OpenFounder wins because |
|-----|------------------------|
| Polsia | Open source, transparent decision log, extensible, self-hosted |
| MetaGPT | Full venture scope, not just software development |
| CrewAI | Production-grade orchestration, not a framework you have to wire up |

## Quick Start

```bash
git clone https://github.com/kulnukaibot-maker/openfounder.git
cd openfounder
cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
make up
```

That's it. Dashboard at [http://localhost:8111](http://localhost:8111).

### Create your first venture

```bash
make venture name="My Startup"
```

### Run the CEO Loop

```bash
make ceo
```

The CEO reads your venture state, plans priorities, delegates to crews, records every decision with reasoning, and sends a briefing.

## How It Works

```
You describe a venture
        |
CEO Loop runs (nightly cron or on-demand)
        |
Reads venture state (Postgres) --> Plans priorities --> Delegates to crews
        |
+----------+----------+----------+----------+----------+
| Strategy | Engineer | Marketing| Finance  | Research |
|   Crew   |   Crew   |   Crew   |   Crew   |   Crew   |
+----------+----------+----------+----------+----------+
        |
Records every decision with reasoning --> Sends briefing
        |
You review, approve external actions, system executes
```

## Features

- **Nightly CEO Loop** — autonomous strategy, planning, and delegation on a schedule
- **Transparent Decision Log** — every AI decision recorded with reasoning, confidence score, and source
- **Human-in-the-Loop** — full autonomy on internal decisions, approvals required for external actions (posting, sending, spending)
- **5 Specialist Crews** — engineering, marketing, finance, research, and strategy (handled by CEO)
- **Mission Control Dashboard** — web UI to view ventures, decisions, metrics, and approvals
- **Multi-Venture** — manage multiple ventures from a single instance
- **Provider Agnostic** — plug in any LLM (Claude, OpenAI, Gemini, local models)
- **Self-Hosted** — your data stays on your machine, always

## Architecture

```
                    +----------------------------------+
                    |     HUMAN-IN-THE-LOOP LAYER      |
                    |  Discord / Dashboard / CLI        |
                    +-----------------+----------------+
                                      |
                    +-----------------v----------------+
                    |     CEO LOOP (Nightly Cron)       |
                    |  Read state --> Plan --> Delegate  |
                    |  --> Record decisions --> Report   |
                    +-----------------+----------------+
                                      |
          +------------+------------+-+----------+------------+
          v            v            v            v            v
    +----------+ +----------+ +----------+ +----------+ +----------+
    | Strategy | | Engineer | | Marketing| | Finance  | | Research |
    |   Crew   | |   Crew   | |   Crew   | |   Crew   | |   Crew   |
    +----------+ +----------+ +----------+ +----------+ +----------+
                                      |
                    +-----------------v----------------+
                    |     COMPANY STATE (PostgreSQL)    |
                    |  ventures / decisions / metrics   |
                    |  features / bugs / campaigns      |
                    |  budgets / expenses / revenue     |
                    +----------------------------------+
```

## Configuration

All config is via environment variables. Copy `.env.example` to `.env` and customize:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Your Anthropic API key (required for CEO loop) |
| `CEO_MODEL` | `claude-haiku-4-5-20251001` | Model for CEO loop |
| `ENGINEERING_MODEL` | `claude-sonnet-4-20250514` | Model for engineering crew |
| `DASHBOARD_PORT` | `8111` | Dashboard port |
| `DISCORD_WEBHOOK_URL` | — | Discord webhook for briefings and approvals |

See `.env.example` for the full list.

## Make Commands

| Command | What it does |
|---------|-------------|
| `make up` | Start database + dashboard |
| `make down` | Stop everything |
| `make ceo` | Run CEO loop once |
| `make venture name="X"` | Create a new venture |
| `make logs` | Tail all logs |
| `make test` | Run tests |
| `make clean` | Reset everything (deletes data) |

## Project Structure

```
openfounder/
  openfounder/
    ceo_loop.py         # Nightly CEO loop orchestrator
    state.py            # Postgres-backed company state manager
    executor.py         # Code executor (branch, apply, test, commit)
    approval.py         # Human-in-the-loop approval system
    config.py           # Environment-based config
    crews/
      engineering.py    # Code generation, testing, deployment
      marketing.py      # Content calendar, campaigns, outreach
      finance.py        # Revenue tracking, budgets, expenses
      research.py       # Market research, competitor analysis
    dashboard/
      app.py            # Mission Control web dashboard (FastAPI)
    prompts/            # System prompts for CEO and each crew
    migrations/         # PostgreSQL schema (auto-applied on first run)
  scripts/              # CLI entry points
  tests/                # Test suite
  docker-compose.yml    # One-command setup
  Makefile              # Convenience commands
```

## Adding Your Own Crew

See [CONTRIBUTING.md](CONTRIBUTING.md) for a step-by-step guide on writing a new crew (e.g., Sales, Legal, HR).

## License

Apache 2.0 — use it however you want.
