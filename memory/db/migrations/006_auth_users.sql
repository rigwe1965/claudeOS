-- Migration 006: User accounts, sessions, and auth audit log

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    email           TEXT UNIQUE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'viewer',
    namespace       TEXT REFERENCES namespaces(slug),
    is_active       INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    DATETIME,
    last_login_at   DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_namespace ON users(namespace);

CREATE TABLE IF NOT EXISTS user_sessions (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   TEXT NOT NULL UNIQUE,
    user_agent   TEXT DEFAULT '',
    ip_address   TEXT DEFAULT '',
    expires_at   DATETIME NOT NULL,
    revoked      INTEGER NOT NULL DEFAULT 0,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_used_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_expires ON user_sessions(expires_at);

CREATE TABLE IF NOT EXISTS auth_events (
    id          TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    user_id     TEXT REFERENCES users(id),
    username    TEXT,
    ip_address  TEXT,
    user_agent  TEXT,
    namespace   TEXT,
    detail      TEXT DEFAULT '{}',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_auth_events_type ON auth_events(event_type);
CREATE INDEX IF NOT EXISTS idx_auth_events_user ON auth_events(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_events_created ON auth_events(created_at);

CREATE TABLE IF NOT EXISTS system_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO system_config VALUES ('max_failed_attempts', '5');
INSERT OR IGNORE INTO system_config VALUES ('lockout_minutes', '15');
INSERT OR IGNORE INTO system_config VALUES ('access_token_minutes', '60');
INSERT OR IGNORE INTO system_config VALUES ('refresh_token_days', '7');
INSERT OR IGNORE INTO system_config VALUES ('allow_self_register', '0');
