-- Phase 13.4: Multi-turn agent conversation history
CREATE TABLE IF NOT EXISTS agent_conversations (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL,
    agent_name  TEXT NOT NULL,
    namespace   TEXT NOT NULL DEFAULT 'global',
    username    TEXT NOT NULL DEFAULT '',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_conversation_turns (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES agent_conversations(id) ON DELETE CASCADE,
    turn_index      INTEGER NOT NULL,
    role            TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content         TEXT NOT NULL,
    tokens_in       INTEGER DEFAULT 0,
    tokens_out      INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    run_id          TEXT,  -- links to agent_runs if assistant turn
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_conv_session_agent
    ON agent_conversations(session_id, agent_name);

CREATE INDEX IF NOT EXISTS idx_conv_turns_conv
    ON agent_conversation_turns(conversation_id, turn_index);

CREATE INDEX IF NOT EXISTS idx_conv_namespace
    ON agent_conversations(namespace, updated_at DESC);
