-- Migration 003: Performance indexes

CREATE INDEX IF NOT EXISTS idx_memory_ns_conf
    ON memory_entries(namespace, confidence DESC);
