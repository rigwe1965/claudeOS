-- Agents inherit the current default model (core/models.py) instead of pinning a concrete id.
-- An empty `model` resolves to default_model() at read time, so a model bump needs no DB edit.
-- Rows pinned to any other model are left untouched.
UPDATE agents SET model = ''
WHERE model IN (
    'claude-sonnet-5-5',
    'claude-sonnet-4-6', 'claude-sonnet-4-5', 'claude-sonnet-4-20250514',
    'claude-3-5-sonnet-20241022', 'claude-3-7-sonnet-20250219',
    'claude-haiku-4-5', 'claude-haiku-4-5-20251001', 'claude-3-5-haiku-20241022'
);
