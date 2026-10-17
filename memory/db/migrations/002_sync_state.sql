-- Migration 002: Sync state tracking for Phase 7 Supabase Cloud Sync

CREATE TABLE IF NOT EXISTS sync_state (
    table_name      TEXT PRIMARY KEY,
    last_synced_at  DATETIME,
    rows_pushed     INTEGER DEFAULT 0,
    rows_failed     INTEGER DEFAULT 0,
    last_error      TEXT,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Seed rows for all synced tables
INSERT OR IGNORE INTO sync_state (table_name, last_synced_at)
VALUES
    ('memory_entries', NULL),
    ('agent_runs',     NULL),
    ('outputs',        NULL),
    ('namespaces',     NULL),
    ('projects',       NULL),
    ('system_events',  NULL);

CREATE TABLE IF NOT EXISTS sync_log (
    id          TEXT PRIMARY KEY,
    table_name  TEXT NOT NULL,
    direction   TEXT NOT NULL DEFAULT 'push',
    rows_ok     INTEGER DEFAULT 0,
    rows_fail   INTEGER DEFAULT 0,
    duration_ms INTEGER,
    error       TEXT,
    started_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME
);

CREATE INDEX IF NOT EXISTS idx_sync_log_table ON sync_log(table_name);
CREATE INDEX IF NOT EXISTS idx_sync_log_started ON sync_log(started_at);
