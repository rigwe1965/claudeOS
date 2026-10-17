-- Migration 008: performance indexes for outputs and event tables

-- outputs: composite covering index for the most common list query pattern
-- (namespace filter + ORDER BY created_at DESC)
CREATE INDEX IF NOT EXISTS idx_outputs_ns_created
    ON outputs(namespace, created_at DESC);

-- system_events: composite index for severity+namespace filter used by /system/events
CREATE INDEX IF NOT EXISTS idx_events_severity_ns_created
    ON system_events(severity, namespace, created_at DESC);

-- auth_events: composite index for audit route filter (event_type + username + sort)
CREATE INDEX IF NOT EXISTS idx_auth_events_compound
    ON auth_events(event_type, username, created_at DESC);
