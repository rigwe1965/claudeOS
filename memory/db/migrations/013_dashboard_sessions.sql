-- Dashboard session store: persist login across page refreshes via URL session key
CREATE TABLE IF NOT EXISTS dashboard_sessions (
    session_key          TEXT PRIMARY KEY,
    user_id              TEXT NOT NULL,
    username             TEXT NOT NULL,
    user_role            TEXT NOT NULL,
    user_namespace       TEXT,
    must_change_password INTEGER DEFAULT 0,
    access_token         TEXT NOT NULL,
    refresh_token        TEXT NOT NULL,
    expires_at           TEXT NOT NULL,
    created_at           TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_dash_sessions_expires
    ON dashboard_sessions(expires_at);
