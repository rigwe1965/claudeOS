-- Migration 005: Composite covering indexes for high-frequency query patterns

-- UNIQUE constraint on (namespace, key) required for the UPSERT in store.write()
CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_ns_key_unique
    ON memory_entries(namespace, key);

-- Covering index for get_context_for_agent():
--   WHERE namespace IN (?, 'global') AND confidence >= ? AND expires_at ...
--   ORDER BY confidence DESC, updated_at DESC
CREATE INDEX IF NOT EXISTS idx_memory_context_lookup
    ON memory_entries(namespace, confidence DESC, expires_at, updated_at DESC);

-- Compound index for agent_runs list/history queries:
--   WHERE agent_id = ? AND status = ? ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_agent_runs_compound
    ON agent_runs(agent_id, status, created_at DESC);

-- Compound index for workflow_runs ORDER BY started_at DESC
CREATE INDEX IF NOT EXISTS idx_workflow_runs_compound
    ON workflow_runs(workflow_id, status, started_at DESC);
