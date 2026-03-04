BEGIN;

CREATE TABLE IF NOT EXISTS crew_outputs (
    id              SERIAL PRIMARY KEY,
    venture_id      INTEGER NOT NULL REFERENCES ventures(id) ON DELETE CASCADE,
    crew_name       TEXT NOT NULL,
    task            TEXT NOT NULL,
    context         TEXT,
    status          TEXT NOT NULL DEFAULT 'completed',
    output          JSONB NOT NULL DEFAULT '{}',
    execution       JSONB,
    branch_name     TEXT,
    commit_sha      TEXT,
    model           TEXT,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    duration_s      REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_crew_outputs_venture ON crew_outputs(venture_id);
CREATE INDEX idx_crew_outputs_crew ON crew_outputs(crew_name);
CREATE INDEX idx_crew_outputs_created ON crew_outputs(created_at);
CREATE INDEX idx_crew_outputs_status ON crew_outputs(status);

COMMIT;
