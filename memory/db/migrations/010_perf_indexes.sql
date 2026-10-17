-- Migration 010: composite index on agent_runs for namespace+time queries
-- Overview page queries agent_runs filtered by namespace, ordered by created_at DESC.
-- Single-column indexes require a sort pass; this composite avoids it.
CREATE INDEX IF NOT EXISTS idx_agent_runs_ns_created
    ON agent_runs(namespace, created_at DESC);
