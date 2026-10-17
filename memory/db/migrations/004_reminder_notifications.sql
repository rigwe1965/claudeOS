-- Add notified_at to memory_entries so reminder job can mark sent reminders
ALTER TABLE memory_entries ADD COLUMN notified_at TEXT;
