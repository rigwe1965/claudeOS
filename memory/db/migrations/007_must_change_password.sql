-- Migration 007: add must_change_password flag to users
ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0;
