-- ClaudeOS Initial Schema
-- Migration 001

-- ═══════════════════════════════════════════════
-- MEMORY ENGINE
-- ═══════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS memory_entries (
    id          TEXT PRIMARY KEY,
    namespace   TEXT NOT NULL DEFAULT 'global',
    category    TEXT NOT NULL DEFAULT 'fact',
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    source      TEXT DEFAULT 'user',
    agent_id    TEXT,
    session_id  TEXT,
    tags        TEXT DEFAULT '[]',
    confidence  REAL DEFAULT 1.0,
    expires_at  DATETIME,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memory_namespace ON memory_entries(namespace);
CREATE INDEX IF NOT EXISTS idx_memory_category ON memory_entries(category);
CREATE INDEX IF NOT EXISTS idx_memory_ns_key ON memory_entries(namespace, key);
CREATE INDEX IF NOT EXISTS idx_memory_expires ON memory_entries(expires_at);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    key, value, tags,
    content='memory_entries',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS memory_fts_insert AFTER INSERT ON memory_entries BEGIN
    INSERT INTO memory_fts(rowid, key, value, tags) VALUES (new.rowid, new.key, new.value, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS memory_fts_delete AFTER DELETE ON memory_entries BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, key, value, tags) VALUES ('delete', old.rowid, old.key, old.value, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS memory_fts_update AFTER UPDATE ON memory_entries BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, key, value, tags) VALUES ('delete', old.rowid, old.key, old.value, old.tags);
    INSERT INTO memory_fts(rowid, key, value, tags) VALUES (new.rowid, new.key, new.value, new.tags);
END;

CREATE TABLE IF NOT EXISTS memory_vectors (
    id          TEXT PRIMARY KEY,
    memory_id   TEXT REFERENCES memory_entries(id) ON DELETE CASCADE,
    chroma_id   TEXT NOT NULL,
    model       TEXT DEFAULT 'all-MiniLM-L6-v2',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════
-- AGENT REGISTRY
-- ═══════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS agents (
    id              TEXT PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    description     TEXT DEFAULT '',
    category        TEXT DEFAULT 'general',
    system_prompt   TEXT NOT NULL,
    model           TEXT DEFAULT 'claude-sonnet-4-6',
    max_tokens      INTEGER DEFAULT 4096,
    temperature     REAL DEFAULT 0.7,
    tools           TEXT DEFAULT '[]',
    namespace_lock  TEXT,
    tags            TEXT DEFAULT '[]',
    enabled         INTEGER DEFAULT 1,
    version         TEXT DEFAULT '1.0.0',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT REFERENCES agents(id),
    session_id      TEXT,
    namespace       TEXT DEFAULT 'global',
    input           TEXT NOT NULL,
    output          TEXT,
    status          TEXT DEFAULT 'pending',
    tokens_in       INTEGER DEFAULT 0,
    tokens_out      INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    error           TEXT,
    triggered_by    TEXT DEFAULT 'user',
    workflow_run_id TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at    DATETIME
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_namespace ON agent_runs(namespace);
CREATE INDEX IF NOT EXISTS idx_agent_runs_created ON agent_runs(created_at);

-- ═══════════════════════════════════════════════
-- WORKFLOW ENGINE
-- ═══════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS workflows (
    id              TEXT PRIMARY KEY,
    name            TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    description     TEXT DEFAULT '',
    trigger_type    TEXT NOT NULL DEFAULT 'manual',
    trigger_spec    TEXT NOT NULL DEFAULT '{}',
    steps           TEXT NOT NULL DEFAULT '[]',
    namespace       TEXT DEFAULT 'global',
    enabled         INTEGER DEFAULT 1,
    last_run_at     DATETIME,
    next_run_at     DATETIME,
    run_count       INTEGER DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    id              TEXT PRIMARY KEY,
    workflow_id     TEXT REFERENCES workflows(id),
    status          TEXT DEFAULT 'pending',
    triggered_by    TEXT DEFAULT 'scheduler',
    context         TEXT DEFAULT '{}',
    steps_log       TEXT DEFAULT '[]',
    output          TEXT,
    error           TEXT,
    duration_ms     INTEGER,
    started_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at    DATETIME
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow ON workflow_runs(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs(status);

-- ═══════════════════════════════════════════════
-- CLIENT/PROJECT VAULT
-- ═══════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS namespaces (
    id              TEXT PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    display_name    TEXT NOT NULL,
    description     TEXT DEFAULT '',
    type            TEXT DEFAULT 'client',
    color           TEXT DEFAULT '#407E3C',
    icon            TEXT DEFAULT '🏢',
    parent_id       TEXT REFERENCES namespaces(id),
    metadata        TEXT DEFAULT '{}',
    enabled         INTEGER DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id              TEXT PRIMARY KEY,
    namespace_id    TEXT REFERENCES namespaces(id),
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    status          TEXT DEFAULT 'active',
    priority        INTEGER DEFAULT 2,
    tech_stack      TEXT DEFAULT '[]',
    path            TEXT DEFAULT '',
    metadata        TEXT DEFAULT '{}',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(namespace_id, slug)
);

-- ═══════════════════════════════════════════════
-- OUTPUT MANAGER
-- ═══════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS outputs (
    id              TEXT PRIMARY KEY,
    namespace       TEXT NOT NULL DEFAULT 'global',
    project_id      TEXT REFERENCES projects(id),
    agent_run_id    TEXT REFERENCES agent_runs(id),
    workflow_run_id TEXT REFERENCES workflow_runs(id),
    type            TEXT NOT NULL DEFAULT 'report',
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    format          TEXT DEFAULT 'markdown',
    tags            TEXT DEFAULT '[]',
    file_path       TEXT DEFAULT '',
    size_bytes      INTEGER DEFAULT 0,
    summary         TEXT DEFAULT '',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_outputs_namespace ON outputs(namespace);
CREATE INDEX IF NOT EXISTS idx_outputs_type ON outputs(type);
CREATE INDEX IF NOT EXISTS idx_outputs_created ON outputs(created_at);

CREATE VIRTUAL TABLE IF NOT EXISTS outputs_fts USING fts5(
    title, content, tags, summary,
    content='outputs',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS outputs_fts_insert AFTER INSERT ON outputs BEGIN
    INSERT INTO outputs_fts(rowid, title, content, tags, summary) VALUES (new.rowid, new.title, new.content, new.tags, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS outputs_fts_delete AFTER DELETE ON outputs BEGIN
    INSERT INTO outputs_fts(outputs_fts, rowid, title, content, tags, summary) VALUES ('delete', old.rowid, old.title, old.content, old.tags, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS outputs_fts_update AFTER UPDATE ON outputs BEGIN
    INSERT INTO outputs_fts(outputs_fts, rowid, title, content, tags, summary) VALUES ('delete', old.rowid, old.title, old.content, old.tags, old.summary);
    INSERT INTO outputs_fts(rowid, title, content, tags, summary) VALUES (new.rowid, new.title, new.content, new.tags, new.summary);
END;

-- ═══════════════════════════════════════════════
-- SYSTEM / AUDIT
-- ═══════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS system_events (
    id          TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    source      TEXT DEFAULT 'system',
    namespace   TEXT DEFAULT 'global',
    payload     TEXT DEFAULT '{}',
    severity    TEXT DEFAULT 'info',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_type ON system_events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_created ON system_events(created_at);

CREATE TABLE IF NOT EXISTS api_keys (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    key_hash    TEXT NOT NULL UNIQUE,
    permissions TEXT DEFAULT '["read","write"]',
    namespace   TEXT DEFAULT 'global',
    last_used   DATETIME,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at  DATETIME
);
