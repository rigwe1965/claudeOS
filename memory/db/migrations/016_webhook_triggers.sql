-- Phase 12.1: Webhook triggers for workflows
ALTER TABLE workflows ADD COLUMN webhook_secret TEXT;
ALTER TABLE workflows ADD COLUMN webhook_enabled INTEGER DEFAULT 0;

-- Index for webhook lookup
CREATE UNIQUE INDEX IF NOT EXISTS idx_workflows_webhook_secret
    ON workflows(webhook_secret) WHERE webhook_secret IS NOT NULL;
