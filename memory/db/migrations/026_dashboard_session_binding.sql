-- A dashboard handle must share the lifetime and revocation of its refresh session.
BEGIN TRANSACTION;

ALTER TABLE dashboard_sessions ADD COLUMN auth_session_id TEXT
    REFERENCES user_sessions(id) ON DELETE CASCADE;

-- Legacy handles cannot be linked safely. ALTER must precede this deletion:
-- startup replays migrations and must stop before deleting newly bound handles.
DELETE FROM dashboard_sessions WHERE auth_session_id IS NULL;

CREATE INDEX idx_dash_sessions_auth_session ON dashboard_sessions(auth_session_id);

-- Covers individual/bulk admin revocation, logout, and account-wide revocation
-- in the same transaction that revokes the authentication session.
CREATE TRIGGER revoke_dashboard_sessions
AFTER UPDATE OF revoked ON user_sessions
WHEN NEW.revoked != 0
BEGIN
    DELETE FROM dashboard_sessions WHERE auth_session_id = NEW.id;
END;

COMMIT;
