-- Migration 023: access tokens issued before this epoch (seconds) are rejected
ALTER TABLE users ADD COLUMN tokens_valid_after INTEGER NOT NULL DEFAULT 0;
