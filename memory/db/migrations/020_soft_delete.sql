-- Phase C: Soft-delete support for agent_runs and outputs
-- Adds deleted_at column — NULL means active, non-NULL means soft-deleted.
-- Hard-delete is replaced by: UPDATE ... SET deleted_at = CURRENT_TIMESTAMP
-- List queries filter WHERE deleted_at IS NULL by default.
-- Admins can pass ?include_deleted=true to see soft-deleted records.

ALTER TABLE agent_runs ADD COLUMN deleted_at DATETIME DEFAULT NULL;
ALTER TABLE outputs    ADD COLUMN deleted_at DATETIME DEFAULT NULL;

-- Index for fast filtering on deleted_at
CREATE INDEX IF NOT EXISTS idx_agent_runs_deleted_at ON agent_runs(deleted_at);
CREATE INDEX IF NOT EXISTS idx_outputs_deleted_at    ON outputs(deleted_at);
