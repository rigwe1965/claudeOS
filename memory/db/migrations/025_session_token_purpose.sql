-- Separate server-controlled credential purpose from client-supplied User-Agent.
BEGIN TRANSACTION;

ALTER TABLE user_sessions ADD COLUMN token_purpose TEXT NOT NULL DEFAULT 'refresh'
    CHECK (token_purpose IN ('refresh', 'password_reset'));

-- Legacy reset tokens and forged refresh tokens have the same marker, so revoke both.
-- Keep this after ALTER: startup reruns migrations, and a duplicate column must stop
-- the script before it can revoke newly issued credentials with this User-Agent.
UPDATE user_sessions SET revoked = 1 WHERE user_agent = 'password_reset';

COMMIT;
