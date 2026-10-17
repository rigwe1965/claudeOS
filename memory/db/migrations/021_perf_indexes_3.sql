-- Migration 021: Performance indexes for context_builder + soft-delete query paths
-- All CREATE INDEX IF NOT EXISTS — safe to re-run

-- agent_runs: context_builder queries namespace+status+created_at
-- Existing idx_agent_runs_namespace_created covers (namespace, created_at) but
-- the status='done' filter forces a post-filter scan. Composite index eliminates it.
CREATE INDEX IF NOT EXISTS idx_agent_runs_ns_status_date
    ON agent_runs(namespace, status, created_at DESC);

-- agent_runs: soft-delete filter (deleted_at IS NULL) added to all list queries
-- Partial indexes not supported in SQLite < 3.38 so use covering index instead
CREATE INDEX IF NOT EXISTS idx_agent_runs_ns_deleted
    ON agent_runs(namespace, deleted_at, created_at DESC);

-- outputs: soft-delete filter on list queries
CREATE INDEX IF NOT EXISTS idx_outputs_ns_deleted
    ON outputs(namespace, deleted_at, created_at DESC);

-- memory_entries: context_builder fetches by namespace+archived+confidence
CREATE INDEX IF NOT EXISTS idx_memory_ns_archived_conf
    ON memory_entries(namespace, archived, confidence DESC);
