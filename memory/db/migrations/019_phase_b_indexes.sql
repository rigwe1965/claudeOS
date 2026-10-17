-- Phase B: Performance indexes for high-traffic query paths
-- All CREATE INDEX IF NOT EXISTS — safe to re-run

-- agent_runs: most queried by namespace+created_at (overview feed, observability)
CREATE INDEX IF NOT EXISTS idx_agent_runs_namespace_created
    ON agent_runs(namespace, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_runs_status
    ON agent_runs(status);

CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at
    ON agent_runs(created_at DESC);

-- memory_entries: queried by namespace constantly (every agent context build)
CREATE INDEX IF NOT EXISTS idx_memory_entries_namespace
    ON memory_entries(namespace);

CREATE INDEX IF NOT EXISTS idx_memory_entries_namespace_archived
    ON memory_entries(namespace, archived);

CREATE INDEX IF NOT EXISTS idx_memory_entries_key
    ON memory_entries(key);

-- tickets: queried by status + namespace (badge count, ticket list)
CREATE INDEX IF NOT EXISTS idx_tickets_namespace_status
    ON tickets(namespace, status);

CREATE INDEX IF NOT EXISTS idx_tickets_created_at
    ON tickets(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to
    ON tickets(assigned_to);

-- auth_events: queried by created_at for audit log (admin panel)
CREATE INDEX IF NOT EXISTS idx_auth_events_created_at
    ON auth_events(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_events_user_id
    ON auth_events(user_id);

-- outputs: queried by namespace (output manager list)
CREATE INDEX IF NOT EXISTS idx_outputs_namespace_created
    ON outputs(namespace, created_at DESC);

-- sync_log: queried by started_at DESC (settings page)
CREATE INDEX IF NOT EXISTS idx_sync_log_started_at
    ON sync_log(started_at DESC);

-- ticket_assignees: foreign key lookups (batch fetch in list_tickets)
CREATE INDEX IF NOT EXISTS idx_ticket_assignees_ticket_id
    ON ticket_assignees(ticket_id);

CREATE INDEX IF NOT EXISTS idx_ticket_assignees_username
    ON ticket_assignees(username);
