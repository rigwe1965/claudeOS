-- Migration 011: multi-assignee support + extended ticket status workflow
-- New statuses: assigned, work_in_progress, completed (open/closed kept)
-- ticket_assignees junction table replaces single assigned_to for multi-user support

CREATE TABLE IF NOT EXISTS ticket_assignees (
    id          TEXT PRIMARY KEY,
    ticket_id   TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    username    TEXT NOT NULL,
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    assigned_by TEXT NOT NULL,
    UNIQUE(ticket_id, username)
);

CREATE INDEX IF NOT EXISTS idx_ticket_assignees_ticket ON ticket_assignees(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_assignees_user   ON ticket_assignees(username, assigned_at DESC);
