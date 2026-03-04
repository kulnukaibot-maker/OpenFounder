-- OpenFounder Initial Schema
-- Auto-runs on first docker compose up via /docker-entrypoint-initdb.d/

BEGIN;

-- Ventures: the companies/projects being managed
CREATE TABLE ventures (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    goal            TEXT,
    stage           TEXT NOT NULL DEFAULT 'idea',  -- idea, mvp, growth, scale
    status          TEXT NOT NULL DEFAULT 'active', -- active, paused, archived
    config          JSONB NOT NULL DEFAULT '{}',   -- per-venture settings (model, autonomy level, etc.)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Features: product features being tracked
CREATE TABLE features (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    priority        TEXT NOT NULL DEFAULT 'medium', -- critical, high, medium, low
    status          TEXT NOT NULL DEFAULT 'backlog', -- backlog, planned, in_progress, done, cut
    assigned_crew   TEXT,                           -- engineering, marketing, research, etc.
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Bugs: issues and problems being tracked
CREATE TABLE bugs (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    description     TEXT,
    severity        TEXT NOT NULL DEFAULT 'medium', -- critical, high, medium, low
    status          TEXT NOT NULL DEFAULT 'open',   -- open, investigating, fixing, resolved, wontfix
    assigned_crew   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Decisions: every AI decision recorded with reasoning (the core differentiator)
CREATE TABLE decisions (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    decision_type   TEXT NOT NULL,                  -- strategic, feature, bug, marketing, resource, delegation
    title           TEXT NOT NULL,
    reasoning       TEXT NOT NULL,                  -- why this decision was made
    outcome         TEXT,                           -- what was decided
    confidence      REAL NOT NULL DEFAULT 0.5,      -- 0.0 to 1.0
    source          TEXT NOT NULL DEFAULT 'ceo',    -- ceo, engineering, marketing, research, human
    status          TEXT NOT NULL DEFAULT 'executed', -- proposed, approved, executed, rejected, reversed
    metadata        JSONB NOT NULL DEFAULT '{}',    -- extra context (model used, tokens, cost, etc.)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Metrics: KPIs and numbers being tracked
CREATE TABLE metrics (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    value           REAL NOT NULL,
    unit            TEXT,                            -- users, dollars, percent, etc.
    source          TEXT,                            -- where the metric came from
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Campaigns: marketing campaigns and initiatives
CREATE TABLE campaigns (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    channel         TEXT NOT NULL,                   -- twitter, reddit, hn, email, blog, discord
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'draft',   -- draft, scheduled, active, completed, cancelled
    scheduled_at    TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    results         JSONB NOT NULL DEFAULT '{}',     -- engagement metrics, reach, conversions
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Approvals: human-in-the-loop approval queue
CREATE TABLE approvals (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    decision_id     INTEGER REFERENCES decisions(id) ON DELETE SET NULL,
    action_type     TEXT NOT NULL,                   -- post, send, spend, deploy, delete
    title           TEXT NOT NULL,
    description     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected, expired
    requested_by    TEXT NOT NULL DEFAULT 'ceo',     -- which crew/agent requested
    resolved_by     TEXT,                            -- who approved/rejected (human name or 'auto')
    resolved_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',     -- action payload, context
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_features_venture ON features(venture_id);
CREATE INDEX idx_features_status ON features(status);
CREATE INDEX idx_bugs_venture ON bugs(venture_id);
CREATE INDEX idx_bugs_status ON bugs(status);
CREATE INDEX idx_decisions_venture ON decisions(venture_id);
CREATE INDEX idx_decisions_created ON decisions(created_at);
CREATE INDEX idx_decisions_type ON decisions(decision_type);
CREATE INDEX idx_metrics_venture ON metrics(venture_id);
CREATE INDEX idx_metrics_name ON metrics(venture_id, name);
CREATE INDEX idx_metrics_recorded ON metrics(recorded_at);
CREATE INDEX idx_campaigns_venture ON campaigns(venture_id);
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_approvals_venture ON approvals(venture_id);
CREATE INDEX idx_approvals_status ON approvals(status);
CREATE INDEX idx_approvals_pending ON approvals(status) WHERE status = 'pending';

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to tables with updated_at
CREATE TRIGGER trg_ventures_updated BEFORE UPDATE ON ventures FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_features_updated BEFORE UPDATE ON features FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_bugs_updated BEFORE UPDATE ON bugs FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_campaigns_updated BEFORE UPDATE ON campaigns FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMIT;
