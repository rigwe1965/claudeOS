-- Phase 11: Memory upgrades
-- 11.4: Contextual prefixing for better RAG retrieval
ALTER TABLE memory_entries ADD COLUMN context_prefix TEXT;

-- 11.1: Memory consolidation tracking
ALTER TABLE memory_entries ADD COLUMN is_consolidated INTEGER DEFAULT 0;
ALTER TABLE memory_entries ADD COLUMN consolidated_from TEXT;  -- JSON array of source entry IDs
ALTER TABLE memory_entries ADD COLUMN archived INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_memory_consolidation
    ON memory_entries(namespace, is_consolidated, archived);

CREATE INDEX IF NOT EXISTS idx_memory_context_prefix
    ON memory_entries(id) WHERE context_prefix IS NOT NULL;
