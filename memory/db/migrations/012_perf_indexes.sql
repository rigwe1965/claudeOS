-- Migration 012: index for unfiltered system_events ORDER BY created_at DESC
-- Without this, listing events with no severity/namespace filter does a full scan + sort.
CREATE INDEX IF NOT EXISTS idx_events_created
    ON system_events(created_at DESC);
