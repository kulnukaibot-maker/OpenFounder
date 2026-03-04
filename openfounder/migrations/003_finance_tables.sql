-- OpenFounder Phase 2: Finance tables
-- Run manually: psql $DATABASE_URL -f openfounder/migrations/002_finance_tables.sql

BEGIN;

-- Budget tracking per venture per category
CREATE TABLE IF NOT EXISTS budgets (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    category        TEXT NOT NULL,  -- infra, llm, marketing, payroll, tools, other
    monthly_limit   REAL NOT NULL,  -- USD per month
    alert_threshold REAL NOT NULL DEFAULT 0.8,  -- alert when spend exceeds this fraction of limit
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(venture_id, category)
);

-- Expense records (individual line items)
CREATE TABLE IF NOT EXISTS expenses (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    category        TEXT NOT NULL,
    amount          REAL NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    description     TEXT,
    source          TEXT,  -- manual, api_usage, invoice, crew_cost
    reference_id    TEXT,  -- external reference (invoice ID, etc.)
    period_start    DATE NOT NULL DEFAULT CURRENT_DATE,
    period_end      DATE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Revenue records
CREATE TABLE IF NOT EXISTS revenue (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    source          TEXT NOT NULL,  -- product, subscription, consulting, other
    amount          REAL NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'USD',
    description     TEXT,
    recurring       BOOLEAN NOT NULL DEFAULT false,
    period_start    DATE NOT NULL DEFAULT CURRENT_DATE,
    period_end      DATE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_budgets_venture ON budgets(venture_id);
CREATE INDEX IF NOT EXISTS idx_expenses_venture ON expenses(venture_id);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(venture_id, category);
CREATE INDEX IF NOT EXISTS idx_expenses_period ON expenses(period_start);
CREATE INDEX IF NOT EXISTS idx_revenue_venture ON revenue(venture_id);
CREATE INDEX IF NOT EXISTS idx_revenue_period ON revenue(period_start);

-- Updated_at trigger for budgets
CREATE TRIGGER trg_budgets_updated BEFORE UPDATE ON budgets FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMIT;
