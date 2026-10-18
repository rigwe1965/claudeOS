-- Migration 025: bind each dashboard handle to the user_sessions row it was issued from,
-- so revoking that session also kills the handle. Older handles (NULL) are rejected.
ALTER TABLE dashboard_sessions ADD COLUMN session_id TEXT;
