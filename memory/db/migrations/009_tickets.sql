-- Migration 009: Ticketing system (tickets + comments, staff role support)

CREATE TABLE IF NOT EXISTS tickets (
    id           TEXT PRIMARY KEY,
    namespace    TEXT NOT NULL REFERENCES namespaces(slug),
    created_by   TEXT NOT NULL,        -- username
    title        TEXT NOT NULL,
    description  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open',   -- open|in_progress|resolved|closed
    category     TEXT NOT NULL DEFAULT 'other',  -- bug|billing|access|feature|other
    priority     INTEGER NOT NULL DEFAULT 3,      -- 1=critical,2=high,3=medium,4=low
    sla_tier     TEXT,           -- P1|P2|P3|P4 (set by admin/staff after creation)
    sla_due_at   DATETIME,       -- auto-calculated: created_at + SLA hours
    assigned_to  TEXT,           -- username of assigned staff or admin
    resolution   TEXT,           -- filled when closing ticket
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tickets_namespace   ON tickets(namespace, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tickets_status      ON tickets(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tickets_created_by  ON tickets(created_by);
CREATE INDEX IF NOT EXISTS idx_tickets_assigned_to ON tickets(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_tickets_sla_due     ON tickets(sla_due_at);

CREATE TABLE IF NOT EXISTS ticket_comments (
    id         TEXT PRIMARY KEY,
    ticket_id  TEXT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author     TEXT NOT NULL,   -- username
    body       TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ticket_comments_ticket ON ticket_comments(ticket_id, created_at);
