-- Migration 022: Missing indexes for namespace-stats pulse query and active-entry counts

-- Memory fresh count used in Namespace Pulse Score (system.py):
--   SELECT COUNT(*) FROM memory_entries WHERE namespace=? AND archived=0 AND updated_at>=?
CREATE INDEX IF NOT EXISTS idx_memory_ns_archived_updated
    ON memory_entries(namespace, archived, updated_at DESC);

-- Workflow runs JOIN for namespace-stats (system.py):
--   JOIN workflow_runs ON workflow_runs.workflow_id = workflows.id
--   WHERE workflows.namespace=? AND workflow_runs.created_at >= ?
CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_started
    ON workflow_runs(workflow_id, started_at DESC);

-- Active entries namespace count (store.py namespace_counts):
--   SELECT namespace, COUNT(*) FROM memory_entries
--   WHERE expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP GROUP BY namespace
CREATE INDEX IF NOT EXISTS idx_memory_ns_expires
    ON memory_entries(namespace, expires_at);
