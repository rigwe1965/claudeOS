# ClaudeOS Phase State

## Current Phase: 9 — All Phases Complete ✅

## Completed Phases
- Phase 1: Core Infrastructure
- Phase 2: Memory Engine
- Phase 3: Agent Registry + Control Center
- Phase 4: Workflow Engine
- Phase 5: Client/Project Vault
- Phase 6: Output Manager
- Phase 7: Cloud Deployment

## Phase 7 — What Was Built

### Files Created
- `sync/__init__.py`
- `sync/engine.py` — watermark-based push-only sync engine
- `sync/schemas.py` — SyncResult, SyncStatus Pydantic models
- `sync/supabase_schema.sql` — SQL to run in Supabase dashboard
- `core/api/routes/sync.py` — 4 Flask endpoints
- `dashboard/pages/_settings.py` — Settings page with sync controls
- `memory/db/migrations/002_sync_state.sql` — sync_state + sync_log tables

### Files Modified
- `core/api/app.py` — registered sync blueprint
- `dashboard/app.py` — wired Settings page (was placeholder)
- `workflows/scheduler.py` — added _register_sync_job, _run_sync_job

### API Endpoints
- GET  /api/v1/sync/status
- POST /api/v1/sync/push          (body: {} or {"table": "outputs"})
- POST /api/v1/sync/reset-watermark
- GET  /api/v1/sync/log

### Architecture
- Push-only: SQLite is source of truth, Supabase is cloud mirror
- Watermark: tracks last_synced_at per table in sync_state
- Auto-sync: APScheduler job every 15min (activates when SUPABASE_URL+KEY set)
- Tables synced: memory_entries, agent_runs, outputs, namespaces, projects, system_events

### To Activate Cloud Sync
Add to .env:
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=service_role_key_here
```
Then run sync/supabase_schema.sql in Supabase SQL Editor.

## All 13 Phases Complete (2026-05-23)
ClaudeOS is fully upgraded to state-of-the-art AI OS.

## Phases 10–13 Summary

### Phase 10: Real-Time Intelligence
- **10.1 SSE Streaming** — `GET /api/v1/agents/<name>/stream` (text/event-stream). `execute_stream()` generator in executor. Dashboard streams token-by-token via requests SSE.
- **10.2 Observability** — New `dashboard/_pages/_observability.py` with quality trends, latency percentiles (p50/p95/p99), per-agent token cost, memory health. Admin + operator only.
- **10.3 LLM-as-Judge** — `agents/evaluator.py`. Async Haiku call after every run. Scores: task_completion×40% + factual_grounding×30% + conciseness×20% + safety×10%. Migration 014 adds eval columns to agent_runs.

### Phase 11: Advanced Memory & Retrieval
- **11.1 Consolidation** — `memory/consolidator.py`. Groups episodic entries by namespace+category, summarizes clusters via Haiku, archives sources. Runs every 4h via APScheduler.
- **11.2 Hybrid BM25+Vector** — `memory/retriever.py`. BM25 (rank-bm25) + ChromaDB in parallel, merged via RRF (k=60). Falls back to FTS5 if rank-bm25 not installed.
- **11.3 Tiered Context** — `memory/context_builder.py`. 3-tier injection: namespace summary (cached 5min) + recent interactions + query-relevant top-5. Replaces flat get_agent_context() in executor.
- **11.4 Contextual Prefixing** — Memory writes now accept context_prefix. Migration 015 adds context_prefix + is_consolidated + archived columns.

### Phase 12: Event-Driven + Protocol
- **12.1 Webhooks** — `POST /workflows/<name>/webhook/enable` generates secret. `POST /workflows/<name>/trigger` public endpoint authenticated via X-Webhook-Secret header. Migration 016 adds webhook_secret + webhook_enabled to workflows. Dashboard "Webhooks" tab.
- **12.2 MCP Server** — `mcp/server.py` exposes all 12 agents as MCP tools + memory search tool. Start via `scripts/start_mcp.ps1` (port 5100).
- **12.3 A2A Cards** — `GET /api/v1/agents/<name>/.well-known/agent.json` returns A2A Agent Card per spec.

### Phase 13: Multimodal + Dashboard
- **13.1 Voice Input** — `st.audio_input` + local Whisper model. Optional: `pip install openai-whisper`.
- **13.2 Image Analysis** — File uploader in agent chat. Base64 images injected as Claude API content blocks. Multi-file support.
- **13.3 Live Dashboard** — Overview real-time feed: error alert strip, running-now indicator, eval score pills, auto-refresh toggle (8s interval).
- **13.4 Multi-Turn Chat** — Full chat UI in Agents page (Chat tab). Per-agent conversation history in session_state. API messages list for multi-turn Claude calls. Migration 017 adds agent_conversations + agent_conversation_turns tables.

### New Files (Phases 10–13)
- `agents/evaluator.py`
- `memory/context_builder.py`
- `memory/retriever.py`
- `memory/consolidator.py`
- `mcp/__init__.py`
- `mcp/server.py`
- `dashboard/_pages/_observability.py`
- `scripts/start_mcp.ps1`
- `memory/db/migrations/014_agent_eval_scores.sql`
- `memory/db/migrations/015_memory_upgrades.sql`
- `memory/db/migrations/016_webhook_triggers.sql`
- `memory/db/migrations/017_agent_conversations.sql`

### New Packages
- `rank-bm25==0.2.2` — hybrid BM25 retrieval
- `plotly>=5.18.0` — observability charts
- `anthropic>=0.40.0` — upgraded (streaming support)
- Optional: `openai-whisper` (voice), `mcp` + `uvicorn` (MCP server)

## Post-Phase Bug Fixes (2026-05-22)

### Theme Toggle
- Restored circular icon button (44px, bottom-left fixed)
- `st.html()` is sandboxed — scripts cannot access parent DOM
- `st.markdown` strips `<script>` tags
- Fix: `st.components.v1.html(height=0)` — same-origin iframe, JS uses `window.parent.document`
- Hides Streamlit trigger button via MutationObserver + CSS

### Agent Runs Namespace Isolation (Overview)
- Bug: `/agents/runs` was in `_READ_ONLY_PREFIXES` — cached globally, `/agents` prefix matched via `startswith`
- Fix 1: removed `/agents/runs` from prefixes; added explicit bypass in `api_get_cached` before prefix check
- Fix 2: `_overview.py` now builds `_runs_url` with `namespace={user_ns}` for scoped users
- Fix 3: `effective_namespace()` in `core/auth.py` — fallback to `requested` param if `g.user_namespace` is null
- Result: client users see only their namespace runs on Overview; admin sees all namespaces
