# Contributing to OpenFounder

Welcome! OpenFounder is designed to be extended. The most common contribution is adding a new crew — a specialist agent that the CEO Loop can delegate tasks to.

## Adding a New Crew

A crew is three files:

1. **A Python class** in `openfounder/crews/` (typically 5-10 lines)
2. **A system prompt** in `openfounder/prompts/`
3. **A registration line** in `openfounder/crews/__init__.py`

### Example: Adding a Sales Crew

#### Step 1: Write the system prompt

Create `openfounder/prompts/sales_crew.md`:

```markdown
# You are the Sales Crew for {{venture_name}}

You are a specialist sales agent. The CEO has delegated a sales task to you.

## Your Role

- Identify and qualify leads
- Draft outreach messages and sequences
- Analyze sales pipeline and conversion rates
- Recommend pricing and deal strategies

## Output Format

Respond with valid JSON:

{
  "task": "The task you were given",
  "findings": [
    {
      "title": "Finding title",
      "detail": "Detailed explanation",
      "confidence": 0.0-1.0
    }
  ],
  "recommendations": [
    {
      "action": "What to do",
      "reasoning": "Why",
      "priority": "critical|high|medium|low"
    }
  ],
  "actions": [
    {
      "type": "outreach|follow_up|proposal|analysis",
      "description": "What to do",
      "target": "Who/what this applies to"
    }
  ],
  "summary": "1-2 sentence summary"
}

## Rules

1. Always output valid JSON
2. Be specific — "reach out to prospects" is useless; "draft cold email to 5 Series B SaaS CTOs" is useful
3. Flag anything requiring human approval (sending emails, posting, spending)
4. Max 10 findings per task
```

#### Step 2: Write the crew class

Create `openfounder/crews/sales.py`:

```python
"""Sales crew — lead generation, outreach, and pipeline management."""

from openfounder.crews.base import BaseCrew


class SalesCrew(BaseCrew):
    crew_name = "sales"
    prompt_file = "sales_crew.md"
```

That's it. The `BaseCrew` handles LLM calling, retries, JSON parsing, and token tracking.

#### Step 3: Register the crew

Edit `openfounder/crews/__init__.py` — add your import and registry entry:

```python
from openfounder.crews.sales import SalesCrew

CREWS = {
    "engineering": EngineeringCrew,
    "finance": FinanceCrew,
    "marketing": MarketingCrew,
    "research": ResearchCrew,
    "sales": SalesCrew,          # <-- add this
}
```

#### Step 4: Test it

```bash
# Start the system
make up

# Create a test venture if you don't have one
make venture name="TestVenture"

# Run the CEO loop — it will now be able to delegate to "sales"
make ceo
```

The CEO Loop automatically discovers registered crews and can delegate tasks to them.

### Customizing Your Crew

Override these methods in your class for more control:

```python
class SalesCrew(BaseCrew):
    crew_name = "sales"
    prompt_file = "sales_crew.md"

    def _get_model(self) -> str:
        """Use a specific model for this crew."""
        return config.ENGINEERING_MODEL  # or any model string

    def _get_max_tokens(self) -> int:
        """Allow longer outputs."""
        return 16384
```

### Adding a Database Migration (Optional)

If your crew needs its own tables (like the Finance crew has budgets/expenses):

1. Create `openfounder/migrations/005_sales_tables.sql` (use the next number)
2. Use `CREATE TABLE IF NOT EXISTS` for idempotency
3. Wrap in `BEGIN; ... COMMIT;`
4. Run `make setup` to apply

## Prompt Writing Tips

- Start with `# You are the X Crew for {{venture_name}}`
- Define the role clearly — what this crew does and doesn't do
- Specify JSON output format exactly — the base class parses it
- Add rules at the bottom to constrain behavior
- Be specific about what "good output" looks like with examples
- Keep it under 1000 words — the CEO context already takes up tokens

## General Contributing

### Running Tests

```bash
make test
```

### Code Style

- Python 3.12+
- No external frameworks beyond what's in `requirements.txt`
- Keep crews simple — complexity belongs in the prompt, not the code

### Pull Requests

1. Fork the repo
2. Create a branch: `git checkout -b add-sales-crew`
3. Make your changes
4. Run tests: `make test`
5. Submit a PR with a clear description of what the crew does

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
