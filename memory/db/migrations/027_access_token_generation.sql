-- Account revocation must distinguish access tokens issued in the same second.
ALTER TABLE users ADD COLUMN token_generation INTEGER NOT NULL DEFAULT 0;
