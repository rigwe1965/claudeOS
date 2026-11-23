-- Skills page: which skills the owner has reviewed and approved, and the content fingerprint at that moment.
-- A skill whose fingerprint no longer matches shows as "changed since approved".
CREATE TABLE IF NOT EXISTS skill_approvals (
    skill_id    TEXT PRIMARY KEY,              -- first 16 hex of sha256(resolved folder path)
    name        TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT '',
    location    TEXT NOT NULL DEFAULT '',
    fingerprint TEXT NOT NULL,                 -- sha256 over every file in the skill (line endings ignored)
    verdict     TEXT NOT NULL DEFAULT 'ok',    -- scan verdict at the time: ok | review | risky
    note        TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT '',
    approved_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
