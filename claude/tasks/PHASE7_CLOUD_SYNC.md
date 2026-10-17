# Phase 7 — Supabase Cloud Sync

## Goal
Push ClaudeOS SQLite data to Supabase for cloud backup, multi-device access, and remote visibility.

## Design Decisions
- **Push-only** — SQLite is source of truth. Supabase is mirror/backup.
- **Watermark sync** — `sync_state` table tracks `last_synced_at` per table. Only rows newer than watermark are pushed.
- **Upsert** — all pushes use upsert so re-runs are safe.
- **Namespace isolation** — respected; can configure which namespaces to sync.
- **Auto-sync** — APScheduler job every 15 minutes (configurable via `.env`).
- **Manual trigger** — `/api/v1/sync/push` endpoint + dashboard button.

## Tables Synced
| Table | Notes |
|-------|-------|
| `memory_entries` | Skip vector/FTS virtual tables |
| `agent_runs` | Full run logs |
| `outputs` | Metadata + content (no file_path) |
| `namespaces` | Client/project namespaces |
| `projects` | Project records |
| `system_events` | Audit events |

## Files to Create
1. `sync/__init__.py`
2. `sync/engine.py` — core push/pull logic
3. `sync/schemas.py` — SyncStatus, SyncResult Pydantic models
4. `sync/supabase_schema.sql` — SQL to run in Supabase dashboard
5. `core/api/routes/sync.py` — Flask routes
6. `dashboard/pages/_settings.py` — Settings page
7. `memory/db/migrations/002_sync_state.sql` — sync_state table

## Files to Modify
1. `core/api/app.py` — register sync blueprint
2. `dashboard/app.py` — wire Settings page instead of placeholder
3. `workflows/scheduler.py` — add periodic sync job

## Tasks
- [x] Write plan
- [x] Migration 002: sync_state table
- [x] sync/schemas.py
- [x] sync/engine.py
- [x] sync/supabase_schema.sql
- [x] core/api/routes/sync.py
- [x] Register sync blueprint in app.py
- [x] workflows/scheduler.py: add sync job
- [x] dashboard/pages/_settings.py
- [x] dashboard/app.py: wire Settings page
- [x] .claude/state.md: write phase state

## Changes Log
