# CLAUDE.md — ClaudeOS Project Rules

## Project
ClaudeOS — AI Operating System. Coordination layer unifying all Claude Code skills, agents, and workflows into a single authenticated control center.
Brand: #407E3C green + white. Target: Windows 10 / PowerShell.

## Architecture
```
Browser (Streamlit :8501)
  └─ Login gate → st.session_state["jwt_token"]
      └─ api_get/api_post → Authorization: Bearer <token>
          └─ Flask :5000
              ├─ require_auth (JWT or X-API-Key fallback)
              ├─ require_role("admin") → /api/v1/admin/*
              └─ All routes (memory, agents, outputs, tickets, workflows, etc.)

Layer 0:  Streamlit dashboard (:8501) — login-gated, role-filtered nav, 11 pages
Layer 1:  Flask REST API (:5000) — JWT + X-API-Key auth on all routes
Layer 2:  Memory Engine (SQLite FTS5 + ChromaDB + hybrid BM25 retrieval)
Layer 3:  Agent Registry (12 agents, YAML definitions)
Layer 4:  Workflow Engine (APScheduler, 7 pipelines, webhook triggers)
Layer 5:  Client Vault (namespace isolation)
Layer 6:  Output Manager (auto-tag, FTS, export)
Layer 7:  Supabase Cloud Sync (push-only, 15-min auto)
Layer 8:  Auth & Security (JWT, bcrypt, roles, audit log)
Layer 9:  Ticketing System (SLA tiers, staff role, bulk ops)
Layer 10: Real-Time Intelligence (SSE streaming, LLM-as-Judge eval, Observability)
Layer 11: Advanced Memory (hybrid RAG, tiered context, consolidation, contextual prefixing)
Layer 12: Protocols (MCP Tool Server :5100, A2A Agent Cards, webhook triggers)
Layer 13: Multimodal (multi-turn chat, image analysis, voice input, live dashboard)
Layer 14: Commercial (namespace white-labeling, client usage dashboard, email notifications, rate limiting, security headers)
```

## Critical Files
- `core/api/app.py` — Flask factory, all routes bootstrap here
- `core/auth.py` — JWT, bcrypt, session management, decorators, audit log
- `core/api/routes/auth_routes.py` — /api/v1/auth/* (login, register, refresh, logout, me)
- `core/api/routes/admin_routes.py` — /api/v1/admin/* (users, sessions, API keys, audit, security config)
- `core/api/routes/tickets.py` — /api/v1/tickets/* (ticketing REST API)
- `core/api/routes/agents.py` — agents REST + SSE stream + A2A cards
- `core/api/routes/workflows.py` — workflows REST + webhook trigger endpoints
- `core/api/routes/memory.py` — memory CRUD + hybrid-search + consolidate endpoints
- `memory/engine.py` — memory facade, all agents call this
- `memory/retriever.py` — hybrid BM25+vector RRF retrieval (Phase 11.2)
- `memory/context_builder.py` — tiered context injection for agent prompts (Phase 11.3)
- `memory/consolidator.py` — episodic→semantic consolidation engine (Phase 11.1)
- `agents/executor.py` — Claude API wrapper, streaming, multi-turn, image support, eval trigger
- `agents/evaluator.py` — LLM-as-Judge async quality scoring (Phase 10.3)
- `agents/dispatcher.py` — routes requests to executor, namespace lock enforcement
- `workflows/pipeline.py` — step executor for all 7 workflows
- `workflows/scheduler.py` — APScheduler: cron workflows + consolidation + sync + reminders
- `dashboard/app.py` — Streamlit entry point, auth gate, role nav (10 pages)
- `dashboard/components/login_form.py` — branded login + self-registration form (st.form)
- `dashboard/components/brand.py` — CSS injection, theme toggle, all visual primitives
- `dashboard/_pages/_agents.py` — Chat/Catalog/Runs tabs, streaming, image, voice, eval; clickable catalog cards; tab persistence via sessionStorage
- `dashboard/_pages/_overview.py` — Live feed, auto-refresh, error alerts, eval score pills
- `dashboard/_pages/_observability.py` — Quality trends, latency, tokens, memory health, namespace usage
- `dashboard/_pages/_workflows.py` — Workflows + Webhooks tab
- `dashboard/_pages/_admin.py` — Admin Panel UI (users, API keys, audit, sessions, security, client onboarding)
- `dashboard/components/onboarding.py` — First-time user onboarding tour (persists to DB via migration 018)
- `dashboard/_pages/_usage.py` — Client Usage Dashboard: Namespace Pulse Score gauge, KPI grid, activity feed, memory summary (client/viewer only)
- `core/notifications.py` — Email notification engine: stdlib smtplib, fire-and-forget, branded HTML templates; ticket assignment + completion events
- `core/api/routes/system.py` — /system/status, /system/stats, /system/namespace-stats (Namespace Pulse Score composite)
- `mcp/server.py` — MCP Tool Server, exposes 12 agents as MCP tools (port 5100)
- `scripts/create_admin.py` — first-run admin seed script
- `scripts/seed_client_schema.py` — pre-populate 14 onboarding fields for a client namespace (skips existing keys)
- `scripts/build_package.py` — builds `dist/FaiykeOS-v17.2.zip` (158 files, excludes .env/data/logs/__pycache__/dev scripts)
- `scripts/start.ps1` — kills ports, starts Flask + Streamlit
- `scripts/start_mcp.ps1` — starts MCP server on port 5100
- `scripts/stop.ps1` — stops Flask + Streamlit processes
- `core/backup.py` — VACUUM INTO backup, 7-backup retention, `data/backups/`; daily APScheduler job at 02:00
- `docs/FaiykeOS_Handbook_faiyke-ai.pdf` — full client-facing handbook (20 sections, regenerated via gen_handbook_pdf.py)
- `docs/PRODUCT_README.md` — buyer-facing package README with feature tables and quick start
- `docs/SETUP_GUIDE_NONTECHNICAL.md` — 10-part setup guide for non-technical buyers
- `docs/AGENCY_LICENSE.md` — agency/reseller license terms (v17.0)
- `docs/landing/index.html` — marketing landing page (standalone HTML, no build system)
- `docs/landing/pricing.html` — pricing page with 3-tier cards, comparison table, Formspree booking form
- `dist/FaiykeOS-v17.2.zip` — distributable buyer package (gitignored — rebuild with build_package.py)

## Stack
- Python: Flask (API), Streamlit (dashboard)
- AI: anthropic SDK ≥0.40.0. Models come ONLY from `core/models.py` (`default_model()` = claude-sonnet-5-5 for agents, `fast_model()` = claude-haiku-5-5 for eval/consolidation; override via `CLAUDE_MODEL` / `CLAUDE_FAST_MODEL` in .env). Never hardcode a model id; agent YAMLs omit `model:`, and legacy ids stored in the DB are upgraded at read time.
- Auth: PyJWT≥2.10.1, bcrypt==4.2.0
- Memory: SQLite FTS5, ChromaDB, sentence-transformers, rank-bm25
- Charts: plotly
- Dashboard runtime: **streamlit==1.56.0** + **pyarrow<22** in `.venv` (the code uses 1.5x APIs such as `width='stretch'`; pyarrow>=22 needs NumPy 2 but chromadb==0.5.5 needs NumPy 1.x — keep both pins). `scripts/start.ps1` uses `.venv`, not the global Python.
- Scheduler: APScheduler BackgroundScheduler
- WSGI: waitress (not gunicorn — Windows)
- Optional: openai-whisper (voice), mcp + uvicorn (MCP server)
- Testing: pytest

## Auth & Security Rules
- All API routes require auth (`@require_auth`) — JWT Bearer or X-API-Key fallback
- `/api/v1/health` is the ONLY public endpoint (webhook trigger uses X-Webhook-Secret, not JWT)
- Roles: admin (all access) | operator (all namespaces, no user mgmt) | client (own namespace only) | viewer (own namespace, read-only) | staff (assigned tickets only)
- JWT access tokens: 60 min TTL. Refresh tokens: 24 hours (session window), stored as SHA-256 hash
- Passwords: bcrypt 12 rounds, min 10 chars, upper+lower+digit required
- Account lockout: 5 failed attempts → 15-min lock (configurable via system_config)
- `must_change_password` flag: user forced to change on next login
- Client one-per-namespace enforced in application layer
- Never expose raw refresh tokens in logs or responses beyond initial issue
- `effective_namespace()` in auth.py enforces client scoping — never trust client-supplied namespace
  - Falls back to `requested` param if `g.user_namespace` is null
- Username lookup uses `LOWER()` match — login is case-insensitive
- Webhook endpoints use `hmac.compare_digest` to validate X-Webhook-Secret — no JWT needed

## Database Tables
**Auth Layer:**
- `users` — id, username, email, password_hash, role, namespace, is_active, failed_attempts, locked_until, must_change_password
- `user_sessions` — refresh token hashes, ip, ua, expires_at, revoked
- `auth_events` — full audit log: login_success/failure, logout, token_refresh, user_created, lockout_triggered, etc.
- `system_config` — key/value security settings

**Agent Layer:**
- `agent_runs` — all run records + eval_score, eval_reasoning, eval_dimensions, eval_at (migration 014)
- `agent_conversations` — multi-turn conversation sessions (migration 017)
- `agent_conversation_turns` — individual turns with role, content, tokens (migration 017)
- `users.onboarding_done` — column added by migration 018; POST /auth/onboarding-done marks it true

**Memory Layer:**
- `memory_entries` — all memory + context_prefix, is_consolidated, archived, consolidated_from (migration 015)
- `memory_fts` — FTS5 virtual table for keyword search
- `memory_vectors` — ChromaDB chroma_id mapping

**Workflow Layer:**
- `workflows` — definitions + webhook_secret, webhook_enabled (migration 016)
- `workflow_runs` — pipeline execution history

## Dashboard Rules
- `inject()` and `theme_toggle()` MUST be called BEFORE the auth gate — they render on login page
- Theme toggle: fixed bottom-left, 44px circular icon, implemented via `components.v1.html(height=0)`
- Sidebar renders AFTER auth gate — only visible to logged-in users
- Role-based nav: clients/viewers hide Settings, Workflows, Observability, Admin but gain Usage page; staff sees Tickets only (Memory, Workflows, Projects, Settings, Admin, Observability hidden)
- Auto token refresh: decode locally, if expiry < 5 min → call `/auth/refresh` silently
- 401 response → clear session_state + `st.rerun()` (returns to login)
- Login form uses `st.form` — Enter-to-submit
- Streaming: use `requests.get(..., stream=True)` + `resp.iter_lines()` for SSE consumption
- Multi-turn chat: conversation stored in `st.session_state[f"conv_{agent}_{ns}"]` list of dicts
- File attach: `chat_input(accept_file=True)` returns `ChatInputValue` (`.text`, `.files`) or plain str — normalise before use; sidebar uploader merged via `_all_files`
- Observability page visible to admin + operator only (hidden from client, viewer, staff)
- Observability has 5 tabs: Quality Scores, Latency, Token Cost, Memory Health, Namespace Usage
- Admin Panel has 7 tabs: Users, API Keys, Audit Log, Sessions, Security, Client Onboarding, Branding
- Admin Branding tab: per-namespace color picker, accent color, company name, icon, live preview — stored in namespace metadata
- Usage page: visible to client/viewer only — KPI grid (runs, tokens, cost, quality, outputs), Namespace Pulse Score (composite 0–100 gauge), recent activity feed, memory summary
- Namespace white-labeling: sidebar logo shows company_name + icon from namespace metadata; aurora_hero() pill uses namespace brand color; `get_ns_brand()` in brand.py reads from session_state; loaded on login for client/viewer
- Email notifications: `core/notifications.py` — stdlib smtplib, fire-and-forget pool; ticket assignment notifies assignee, ticket completion/closure notifies creator; config via .env SMTP_* vars
- Admin unlock: Unlock button only shown when user is actually locked (context-aware UI since commit eba9751)
- Admin Edit User: `@st.dialog` modal — change role, namespace, email, active status, force-pw flag (commit 528346c)
- Admin Delete User: `@st.dialog` permanent-delete modal — hard-deletes user + sessions + auth events; guarded against deleting last admin (commit 528346c)
- Admin Users action bar: 5 columns — Unlock/Status | Deactivate/Reactivate | Reset Password | Edit | Delete
- `_ALLOWED_USER_UPDATES` in admin_routes.py: whitelist includes `role`, `namespace`, `is_active`, `email`, `must_change_password` — SQL column names never taken from request keys directly
- Onboarding tour: only shown to `client` and `viewer` roles — `admin`, `operator`, `staff` skip it entirely
- Agents catalog cards: rendered via `st.components.v1.html` per card (isolated iframe — Streamlit brand CSS cannot reach inside); JS onclick clicks hidden `st.button` (`card_chat_{safe}` key); buttons hidden with `[class*="st-key-card_chat_"]` height:0 CSS
- Agent pre-select from catalog: set `st.session_state["chat_agent"] = name` BEFORE `st.selectbox()` instantiation — never use `index=` workaround, it is silently ignored when the key already exists
- Agents tab persistence: nonce-stamped `components.html` on every render (forces fresh iframe so JS always runs); JS reads `sessionStorage["claudeos_agents_tab"]` to restore tab; `aria-selected !== 'true'` guard prevents clicking already-active tab (prevents infinite rerun loop); `_goto_chat=True` → target=0 written to storage; all other reruns pass target=-1 (restore from storage)

## Phase 14 — Commercial Upgrade Rules
- Rate limiting: agent /run 30/min, /stream 20/min, workflow /trigger 10/min, workflow /run 20/min (flask-limiter)
- CORS: ALLOWED_ORIGINS env var replaces wildcard — never use `*` in production
- Security response headers on every Flask response: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Content-Security-Policy (`default-src 'none'; frame-ancestors 'none'`), HSTS (production only)
- Namespace slug enumeration: self-registration returns single generic error for missing vs wrong-type namespaces (no enumeration)
- Admin audit endpoint: `?since=` and `?until=` validated against ISO datetime pattern (returns 400 on invalid)
- Namespace Pulse Score: composite 0–100 = quality_score×40% + ticket_resolve×30% + memory_fresh×20% + workflow_ok×10%
- `GET /system/namespace-stats?namespace=<ns>` returns tokens_in/out, cost_usd, run_count, output_count, eval_avg, pulse_score, recent_runs, ticket_total/closed, memory_count/fresh, workflow_total/ok
- `_ns_brand_css()` in brand.py: injects namespace color/accent into CSS custom properties when client/viewer is logged in
- Output delete: uses SELECT-then-DELETE not DELETE...RETURNING (RETURNING requires SQLite 3.35+)
- Output timestamps: displayed as YYYY-MM-DD HH:MM in expander header, meta row, and search results
- Activity feed agent names: dispatcher.list_runs JOINs agents table; overview uses agent_name > agent_display_name > agent_id[:12] fallback chain
- Agent hallucination guard: analysis, briefing, research, writing agents ask clarifying questions and decline to fill data gaps — never fabricate findings, names, timestamps, or system state
- Agent NO TRAINING KNOWLEDGE rule (2026-05-28): analysis-agent and client-manager-agent have explicit CRITICAL block prohibiting use of training data for business-specific facts (cities, clients, revenue, routes). Empty context → MISSING INPUT PROTOCOL, not a fabricated answer. client-manager-agent out-of-scope requests (e.g. drafting emails) → one-line redirect, no claims.
- Context builder timeout: executor wraps build_context() in 4s timeout via bg pool — slow ChromaDB never blocks agent response; falls back to fast FTS context

## Phase 10-13 Rules
- SSE streaming: `execute_stream()` in executor.py is a generator — yields text chunks. Flask wraps with `stream_with_context`. Never buffer the full response.
- Output save on stream: handled entirely in `stream_agent()` (`core/api/routes/agents.py`) — NOT in `_stream_response()` in `_agents.py`. `agent.name` comes from URL path registry lookup; never use selectbox state for attribution. Save uses `threading.Thread(daemon=True)` — NOT `_bg_pool` — because `_bg_pool` (max_workers=2) can be fully occupied by concurrent eval jobs, blocking the save indefinitely.
- Stream error persistence: SSE/exception errors stored in `st.session_state["_stream_error"]` in `_stream_response()`, then appended to conversation history as an assistant message in `_render_chat_tab`. Survives `st.rerun()`. Never call `st.error()` inside streaming context — it disappears on the next rerun.
- `_parse_stream_inputs()` returns 6 values: `(prompt, namespace, context, messages, images, save_output)`. GET param: `save_output=true`; POST body: `"save_output": true`.
- Eval scoring: always async via `_bg_pool.submit(_trigger_eval, ...)` — never block agent run on eval
- Eval uses `fast_model()` (cheap+fast). Score = tc×0.40 + fg×0.30 + cc×0.20 + sf×0.10
- Eval rubric (2026-05-28): correct scope refusals score task_completion=5.0 — agents that decline out-of-scope requests without fabricating anything are not penalised; factual_grounding=5.0 when no claims made (commit 11f51e5)
- Tiered context: `memory/context_builder.py:build_context(namespace, query)` replaces `get_agent_context()` in executor. Falls back to flat context if context_builder fails.
- Hybrid retrieval: `memory/retriever.py:hybrid_search()` — BM25 + ChromaDB in ThreadPoolExecutor, merged via RRF (k=60). Falls back to FTS5 if rank-bm25 not installed.
- Consolidation job: every 4h via APScheduler. Archives originals (archived=1), never hard-deletes.
- Webhooks: `POST /workflows/<name>/trigger` is the only non-JWT endpoint besides /health. Secured by HMAC comparison of X-Webhook-Secret header.
- MCP server: runs independently on port 5100. Start via `scripts/start_mcp.ps1`. Optional — not required for core operation.
- Image support: executor `_build_messages()` accepts `images=[{data: base64, media_type: str}]` — injected as Claude API image content blocks.
- Voice input: requires `openai-whisper`. Uses `@st.cache_resource` to load model once per session.
- A2A cards: `GET /agents/<name>/.well-known/agent.json` — pure JSON generation, no extra deps.

## Performance Patterns
- Parallel API calls via `ThreadPoolExecutor` — all overview data fetched in one shot (5 concurrent)
- N+1 → parallel: namespace workspace + projects fetched concurrently in Client Vault
- Ticket assignees batch-fetched in a single `WHERE id IN (...)` query
- Ticket comments lazy-loaded: only fetched on "💬 Comments" toggle
- `_cached_api_get` cache key includes JWT token — prevents cross-user cache pollution
- `/agents/runs` excluded from `_READ_ONLY_PREFIXES` — always bypasses cache
- Bulk session revoke: single `UPDATE ... WHERE id IN (...)`
- `_api_key_last_updated` bounded to 500 entries with TTL eviction
- Security settings update uses `executemany`
- TTL config cache in `core/auth.py:_cfg()` — 60s in-process cache
- Hybrid retrieval: BM25 + vector run in parallel (ThreadPoolExecutor), not sequential
- Tiered context: namespace summary cached 5 min in-process — not rebuilt per request
- Eval pool: 2-worker ThreadPoolExecutor, non-blocking — never delays agent response
- Consolidation: only processes entries older than 24h, capped at 200 per namespace per run
- Memory consolidation caches BM25 corpus per namespace (rebuilt only on write)
- `executor.py` stores `mem_context` (capped 3000 chars) in agent_runs.input JSON on completion — fixes truncated activity log
- Agent failures logged to global `error_log` memory entry async — audit trail without blocking runs
- Namespace Usage tab: fetches up to 500 runs, stacked bar chart (plotly), cross-namespace token/cost/quality comparison
- Agents page: uses `api_get_cached` for /namespaces fetch — 30s cache saves 300–800ms per tab render
- Context builder: wrapped in 4s timeout via bg pool in executor.py — ChromaDB/hybrid-search slowness never blocks agent response
- ChromaDB probe cached 30s (`core/api/routes/system.py`) — no `PersistentClient` re-init per `/system/status` call
- `namespace_stats` compound SELECT: 7 sequential round-trips → 1 query (scalar subqueries)
- Bulk memory delete: batch SELECT for permissions + single `DELETE WHERE id IN (...)` + grouped ChromaDB deletes per namespace
- Agent run completion: no SELECT before UPDATE — builds JSON from in-scope vars directly
- Streaming INSERT: `create_run_record(status='running')` skips separate `_update_run_status` call
- Context builder `_ns_summary_cache`: stores `(result, seen_keys_set, expiry)` — eliminates string re-parse on cache hit
- Overview live refresh: `st.fragment(run_every=8)` replaces `time.sleep(8)` — session thread never frozen
- Agent list cache unified: `/agents?enabled_only=false` used by all callers — both Overview and Agents page now share same cache key

## Theme System
- Dark/light mode: `st.session_state["theme"]` ("dark"/"light")
- `get_theme_vars()` in brand.py returns CSS vars dict
- `_build_css(t)` generates full CSS from theme vars — one call, entire app styled
- `inject()` must be called on every page render
- Theme toggle: `st.components.v1.html(height=0)` — JS uses `window.parent.document`
  - `st.html()` is sandboxed (scripts blocked); `st.markdown` strips scripts
  - Position: `fixed; bottom:24px; left:220px` — clears sidebar text (commit 86bbade)
- Aurora background removed — no animated gradients, no will-change: transform
- **SVG fill override rule**: header toolbar `svg path` selectors must use `:not([fill="none"])` — Streamlit's MoreVert icon includes a 24×24 bounding-box path with `fill="none"` that becomes a solid colored square if overridden. JS guard: `if (p.getAttribute('fill') === 'none') return` before setting fill.
- **`stToolbarActionButtonIcon`** is a styled div with `background: url(...) no-repeat center/contain` (CSS background-image, not SVG). Do NOT set `background: transparent` on it — that destroys the image. Use `display: none` to hide or `filter:` to colorize.
- Streamlit 1.56 toolbar testids: `stAppDeployButton`, `stAppToolbar`, `stToolbarActionButton`, `stToolbarActionButtonIcon`, `stToolbarActionButtonLabel`, `stToolbarItems`

## Design System (marketplace-style redesign, both themes)
- Fonts: Inter (body), Source Serif 4 (h1–h3 + hero), JetBrains Mono (meta/labels). Loaded once via `<link>` in `inject()`. Never reintroduce Poppins (`tests/test_design_tokens.py` fails on it).
- Light theme is warm off-white (`BG #FBF8F3`, white `SURFACE`); dark keeps the deep-forest greens. Both get a static brand-green top glow (`GLOW` token) — no animation.
- Cards: 10px radius, 1px brand-green outline (~55%), small padding. Hero (`aurora_hero`) is centered serif; Overview adds a search box (`command_palette.search_trigger`) that opens the Ctrl/⌘+K palette.
- Text colours must keep WCAG AA (4.5:1; icons 3:1) — `tests/test_contrast.py` enforces theme tokens, `nav_palette()` and status pills. Change a palette value → run it.
- **Hidden proxy buttons** (nav, KPI cards, catalog cards, palette): never select by `st-key-*` classes. Use `dashboard/components/proxy.py` — `proxy_button(label, key=…)` renders the button inside a marked container, `PROXY_CSS` hides it, JS clicks it by label via `cosClickProxy(doc, label)` (labels: `nav:<page>`, `kpi:<key>`, `card:<key>`). Works on Streamlit 1.38 and 1.5x.
- Zero-height script iframes / `<style>`-only markdown blocks / the hidden theme-flip button are taken out of layout flow in `_build_css` — otherwise each adds a row plus a 16px gap (≈200px dead space at the top of every page).
- Verify visually, not only with pytest: tests cannot see CSS. Log in with a headless browser (puppeteer-core + Edge) and navigate with Ctrl+K — a URL reload drops the session.

## Rules
- Never use gunicorn — use waitress on Windows
- Always `encoding='utf-8'` on file reads/writes
- Never commit .env, vault workspace files, or data/claudeos.db
- Never commit dist/ ZIP files — dist/ is gitignored; only commit build_package.py; rebuild ZIP with `python scripts/build_package.py`
- Namespace isolation is mandatory — no cross-namespace memory reads
- Every agent run logs to agent_runs table
- Every output saves to outputs table + file system
- Port detection: read .env FLASK_PORT/STREAMLIT_PORT/MCP_PORT first
- Never use `&&` in shell — use `;` or separate calls (PowerShell)
- Eval is async — never block on it. If evaluator.py import fails, log warning and continue.
- Consolidation archives, never deletes — `archived=1` not `DELETE`
- Webhook secrets: always use `secrets.token_hex(32)`, always compare with `hmac.compare_digest`

## Server Start
```powershell
.\scripts\start.ps1                 # Flask + Streamlit (required)
.\scripts\start_mcp.ps1             # MCP server (optional, port 5100)
```

## First-Run Setup (new install)
```powershell
pip install -r requirements.txt
python scripts/migrate.py
python scripts/seed_agents.py
python scripts/seed_workflows.py
python scripts/seed_namespaces.py
python scripts/create_admin.py --username admin --password Admin123!
python scripts/seed_client_schema.py --namespace <client-slug>   # optional: pre-fill 14 onboarding fields
.\scripts\start.ps1
```

## Phase Status — ALL COMPLETE (+ Handover Hardening)

### Handover Hardening — Security, Performance & Test Coverage
- **Auth fix**: validate_refresh_token excludes password_reset tokens (user_agent != 'password_reset')
- **Vault security**: path traversal prevention via `_validate_filename()` + `Path.resolve()` comparison
- **Soft-delete**: agent_runs + outputs use `deleted_at` column (migration 020); hard-delete replaced everywhere; list/search/stats filter `deleted_at IS NULL`; `include_deleted=True` param on dispatcher.list_runs
- **DB backup**: `core/backup.py` — VACUUM INTO, 7-backup retention, `data/backups/`; daily APScheduler job at 02:00; `POST /admin/backup` + `GET /admin/backup` endpoints
- **DB indexes**: 15 new indexes on high-traffic columns (migration 019)
- **API key regenerate**: `POST /admin/api-keys/<id>/regenerate`; UI button in Admin → API Keys tab
- **Audit date filters**: `?since=&until=` on GET /admin/audit
- **Supabase sync extended**: users, tickets, workflows tables added to sync (sensitive columns excluded)
- **Rate limiter storage**: SQLite-backed with ImportError fallback to in-memory
- **Scheduler timezone**: configurable via SCHEDULER_TIMEZONE env var (default: Europe/Berlin)
- **ChromaDB health**: /system/status now uses real `client.heartbeat()` instead of hardcoded "ok"
- **Webhook hardening**: 64KB body limit + context dict validation
- **Role enforcement**: projects namespace endpoints require admin/operator; memory consolidate requires admin/operator
- **Test suite**: 115 tests passing across test_auth, test_admin, test_tickets, test_sync, test_workflows, test_agents, test_memory, test_phase1 + shared conftest.py with `fresh_db`, `app`, `client`, `admin_token` fixtures; legacy test files now have auth fixtures + scheduler mock (commit 3c25eec)
- Phase 1:  Core Infrastructure ✅
- Phase 2:  Memory Engine ✅
- Phase 3:  Agent Registry + Control Center ✅
- Phase 4:  Workflow Engine ✅
- Phase 5:  Client/Project Vault ✅
- Phase 6:  Output Manager ✅
- Phase 7:  Cloud Deployment (Supabase Sync) ✅
- Phase 8:  Auth, Admin Backend & Multi-User Login ✅
- Phase 9:  Ticketing System + Bulk Delete ✅
- Phase 10: Real-Time Intelligence ✅
  - SSE streaming: GET /agents/<name>/stream (execute_stream generator)
  - LLM-as-Judge: async Haiku eval after every run (migration 014)
  - Observability dashboard: quality, latency p50/p95/p99, token cost, memory health, namespace usage (5 tabs)
- Phase 11: Advanced Memory & Retrieval ✅
  - Hybrid BM25+Vector RAG with RRF (memory/retriever.py, rank-bm25)
  - Tiered context injection (memory/context_builder.py, ~40% token reduction)
  - Memory consolidation engine (memory/consolidator.py, 4h APScheduler job)
  - Contextual memory prefixing (context_prefix column, migration 015)
- Phase 12: Event-Driven Workflows & Protocols ✅
  - Webhook triggers (POST /workflows/<name>/trigger, X-Webhook-Secret auth, migration 016)
  - MCP Tool Server (mcp/server.py, port 5100, 12 agents as MCP tools)
  - A2A Agent Cards (GET /agents/<name>/.well-known/agent.json)
- Phase 13: Multimodal Input & Live Dashboard ✅
  - Multi-turn chat UI (conversation history, migration 017)
  - Image/screenshot analysis (base64 content blocks via executor); multiple images supported
  - File attachment: `chat_input(accept_file=True, file_type=[...])` — native inline attach for images + .md/.txt; sidebar file_uploader kept as fallback; both merged; text files injected as fenced prompt block, images as base64 content blocks
  - Voice input (st.audio_input + local Whisper, optional); voice widget resets on Clear Conversation
  - Live Overview (auto-refresh toggle, eval score pills, error/running alerts)
  - Onboarding tour (first login only, persists via migration 018 onboarding_done column)
  - Client Onboarding tab in Admin Panel: 14-field schema seed per namespace
  - Admin unlock: context-aware button only shown when user is actually locked
  - Admin Edit User + Delete User: `@st.dialog` modals, 5-column action bar (commit 528346c)
  - Onboarding tour role-gated: `client` and `viewer` only
- Phase 14: Commercial Upgrade ✅
  - Security hardening: CORS ALLOWED_ORIGINS env var, security response headers, rate limiting (flask-limiter)
  - Namespace white-labeling: per-namespace color/accent/company_name/icon in metadata; sidebar logo; aurora_hero() branded pills
  - Client Usage Dashboard (_usage.py): Namespace Pulse Score gauge, KPI grid, activity feed, memory summary (client/viewer only)
  - GET /system/namespace-stats: composite pulse score + all usage metrics per namespace
  - Email notifications (core/notifications.py): ticket assignment + completion events, branded HTML, fire-and-forget smtplib
  - Admin Branding tab (7th tab): per-namespace color picker, accent, company name, live preview
  - Agent hallucination guard: analysis/briefing/research/writing agents ask clarifying questions; never fabricate data
  - Agent NO TRAINING KNOWLEDGE rule: analysis-agent + client-manager-agent block use of training data for business facts; empty context triggers MISSING INPUT PROTOCOL; client-manager-agent out-of-scope requests get one-line redirect only (commit 87815fb)
  - Output delete compat: SELECT-then-DELETE replaces RETURNING (supports SQLite < 3.35)
  - Output timestamps: YYYY-MM-DD HH:MM shown in all output views
  - Activity feed agent names: dispatcher JOINs agents table; human-readable names always shown
  - Performance: agents page uses api_get_cached; context builder has 4s timeout fallback
  - Sync log delete: DELETE /sync/log/<id> (single entry) + DELETE /sync/log with {"ids":[...]} (bulk, max 200); Settings renders log via st.data_editor with checkbox column + "Delete Selected (N)" button + per-row 🗑 button
- Phase 15: Commercial Package ✅
  - Product rebranded as **FaiykeOS** (commercial name) — all handbook references updated; internal codebase retains ClaudeOS name
  - Handbook renamed `docs/FaiykeOS_Handbook_faiyke-ai.pdf` — regenerated via `python scripts/gen_handbook_pdf.py`
  - Sales template: `docs/landing/index.html` (landing page) + `docs/landing/pricing.html` (3-tier pricing + Formspree booking form)
  - Buyer collateral: `docs/PRODUCT_README.md` (package overview + feature tables), `docs/SETUP_GUIDE_NONTECHNICAL.md` (10-part zero-experience setup guide), `docs/AGENCY_LICENSE.md` (agency reseller license, governed by Nigerian law)
  - 3-tier pricing: Developer $197 one-time | Business $997 + $147/mo | Agency $497 + $97/mo or $997 flat unlimited
  - Distribution script: `scripts/build_package.py` → `dist/FaiykeOS-v17.2.zip` (507 KB, 158 files); excludes .env, data/, logs/, vault/workspaces/, outputs/store/, dev scripts, __pycache__
  - dist/ is gitignored — ZIP not committed; rebuild with `python scripts/build_package.py`
- v17.1 Patch ✅
  - Clickable agent catalog cards: `st.components.v1.html` per card (isolated iframe, native CSS hover, single-color states); JS onclick clicks hidden `st.button` (key `card_chat_{safe}`) to fire Python callback; hidden via `[class*="st-key-card_chat_"]` CSS height:0
  - Agent pre-selection fix: set `st.session_state["chat_agent"] = _pending` BEFORE selectbox instantiation — `index=` param silently ignored when key already exists in session state
  - Tab persistence: nonce-stamped `components.html` on every render forces fresh iframe; JS reads/writes `sessionStorage["claudeos_agents_tab"]`; `aria-selected` guard prevents clicking already-active tab (breaks infinite rerun loop); `_goto_chat=True` → target=0, all other reruns → target=-1 (restore from storage)
  - Handbook bumped to v17.1: updated Section 6 (clickable cards, file attachment table), Section 16 (image+doc analysis), Section 1 intro, TOC new-features note
- v17.2 — Performance, Security & Architecture Hardening ✅ (commit b5436df)
  - **Performance**: SELECT-before-UPDATE eliminated in executor; streaming INSERT starts as `running`; ChromaDB probe cached 30s; namespace_stats 7→1 query; bulk memory delete batched; duplicate `_entry_dict` removed; context_builder seen_keys cached in tuple; Overview sleep→st.fragment; duplicate cv1 import removed from render loop; agent list cache key unified
  - **Security**: MCP server bound to 127.0.0.1 (was 0.0.0.0); workflow delete/scheduler/webhook routes require admin/operator; workflow limit params wrapped in try/except (400 on bad int, max 200); bulk delete capped at 200; XSS fix in Admin Branding (html.escape on company name + icon); system/status DB path/platform gated by admin/operator; CSP header (`default-src 'none'; frame-ancestors 'none'`) on all Flask responses; HSTS in production; Settings repr masks credentials; worktree weak secret default removed; audit date params validated (ISO pattern); session TTL 7d→24h; namespace slug enumeration closed
  - **Architecture**: stale run cleanup on startup (`_cleanup_stale_runs()` resets pending/running>1h to failed); memory write endpoint rejects values >64KB (422); SCHEDULER_TIMEZONE default changed Africa/Lagos→Europe/Berlin
