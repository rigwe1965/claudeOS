-- Migration 018: persist onboarding completion per user
ALTER TABLE users ADD COLUMN onboarding_done INTEGER NOT NULL DEFAULT 0;
