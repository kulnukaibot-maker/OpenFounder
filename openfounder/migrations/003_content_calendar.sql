BEGIN;

CREATE TABLE IF NOT EXISTS content_calendar (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    channel         TEXT NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    cta             TEXT,
    status          TEXT NOT NULL DEFAULT 'draft',
    scheduled_for   TIMESTAMPTZ,
    published_at    TIMESTAMPTZ,
    published_url   TEXT,
    campaign_id     INTEGER REFERENCES campaigns(id),
    crew_output_id  INTEGER REFERENCES crew_outputs(id),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_content_calendar_venture ON content_calendar(venture_id);
CREATE INDEX idx_content_calendar_status ON content_calendar(status);
CREATE INDEX idx_content_calendar_channel ON content_calendar(channel);
CREATE INDEX idx_content_calendar_scheduled ON content_calendar(scheduled_for);

CREATE OR REPLACE FUNCTION update_content_calendar_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_content_calendar_updated
    BEFORE UPDATE ON content_calendar
    FOR EACH ROW EXECUTE FUNCTION update_content_calendar_timestamp();

COMMIT;
