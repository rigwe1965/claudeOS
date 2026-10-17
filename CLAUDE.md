# CLAUDE.md — ClaudeOS Project Rules

ClaudeOS (commercial name **FaiykeOS**) — AI operating system: one authenticated control center over Claude agents, memory, workflows and tickets. Brand #407E3C green + white. Target: Windows 10 / PowerShell. Release history: `CHANGELOG.md`.

## Architecture
```
Streamlit :8501 (login gate → session_state["jwt_token"]; api_get/api_post send Bearer)
  └─ Flask :5000 (waitress) — require_auth (JWT or X-API-Key), require_role("admin") on /api/v1/admin/*
       ├─ memory (SQLite FTS5 + ChromaDB, hybrid BM25 RRF, tiered context, consolidation)
       ├─ agents (12 YAML agents, executor, dispatcher, async LLM-as-Judge eval, SSE)
       ├─ workflows (APScheduler, webhook triggers) · outputs · vault · tickets · Supabase push sync
       └─ MCP server :5100 (optional, loopback) · A2A cards
```
Start: `.\scripts\start.ps1` (Flask + Streamlit, uses `.venv`), `.\scripts\start_mcp.ps1` (optional), `.\scripts\stop.ps1`. Port detection: read `.env` FLASK_PORT / STREAMLIT_PORT / MCP_PORT first. First-run setup: see `README.md` / `docs/SETUP_GUIDE_NONTECHNICAL.md`.

## Key files (non-obvious ones)
- `core/api/app.py` — Flask factory; imports `memory/vector_store.py` (numpy) BEFORE warmup threads
- `core/auth.py` — JWT, bcrypt, decorators, `effective_namespace()`, audit log
- `core/models.py` — only source of model ids, labels, prices (`default_model()`, `fast_model()`, `estimate_cost()`, `model_label()`)
- `core/utils.py` — `first_text(response)`
- `memory/engine.py` facade · `retriever.py` hybrid search · `context_builder.py` tiered context · `consolidator.py`
- `agents/executor.py` — Claude wrapper, streaming, multi-turn, images, eval trigger · `agents/evaluator.py` judge · `agents/dispatcher.py` namespace lock
- `workflows/pipeline.py`, `workflows/scheduler.py` — step executor; cron + consolidation + sync + backup jobs
- `core/api/routes/agents.py` — agents REST, SSE stream, output save on stream
- `dashboard/app.py` auth gate + role nav · `components/brand.py` CSS/theme · `components/proxy.py` hidden proxy buttons · `_pages/_agents.py` chat/catalog/runs
- `core/notifications.py` — smtplib, fire-and-forget; `core/backup.py` — daily VACUUM INTO, 7 kept
- `scripts/`: `build_package.py` (→ gitignored `dist/FaiykeOS-v17.3.zip`), `reindex_vectors.py`, `seed_client_schema.py`, `create_admin.py`

## Hard rules
- Windows: waitress (never gunicorn); no `&&` in PowerShell (use `;`); always `encoding='utf-8'` on file I/O.
- Never commit `.env`, vault workspace files, `data/claudeos.db`, or `dist/` ZIPs.
- Namespace isolation is mandatory — no cross-namespace memory reads. Every agent run logs to `agent_runs`; every output saves to `outputs` table + filesystem.
- Eval is async and must never block a run; if the evaluator import fails, log a warning and continue.
- Consolidation archives (`archived=1`), never deletes.
- Webhook secrets: `secrets.token_hex(32)`, compare with `hmac.compare_digest`.
- Don't hardcode model ids, prices or "Sonnet x.y" labels (`tests/test_models.py` fails); don't reintroduce Poppins (`tests/test_design_tokens.py`).

## Auth & security
- Every route needs `@require_auth` (JWT Bearer or X-API-Key). Public: `/api/v1/health` only; webhook trigger uses X-Webhook-Secret.
- Roles: admin (all) · operator (all namespaces, no user mgmt) · client (own namespace) · viewer (own namespace, read-only) · staff (assigned tickets only).
- Access token 60 min; refresh token stored as SHA-256 hash, never logged or returned after issue. Intended session window 24 h — DB default is currently 7 days (audit L-3).
- Passwords: bcrypt 12 rounds, min 10 chars, upper+lower+digit. 5 failed logins → 15-min lock (system_config). `must_change_password` forces change. Username lookup is `LOWER()`.
- Client one-per-namespace (app layer). `effective_namespace()` enforces client scoping — never trust a client-supplied namespace (falls back to `requested` if `g.user_namespace` is null).
- Password-reset tokens (`user_agent='password_reset'`) are excluded from `validate_refresh_token`.
- Vault paths: `_validate_filename()` + `Path.resolve()` comparison. Soft-delete via `deleted_at` on `agent_runs` and `outputs` (list/search/stats filter it; `include_deleted=True` on `dispatcher.list_runs`).
- Responses: CORS from `ALLOWED_ORIGINS` (never `*`), X-Content-Type-Options / X-Frame-Options / X-XSS-Protection, CSP `default-src 'none'; frame-ancestors 'none'`, HSTS in production. Rate limits (flask-limiter, SQLite storage): agent /run 30/min, /stream 20/min, workflow /trigger 10/min, /run 20/min.
- Self-registration returns one generic error for missing vs wrong-type namespaces. Webhooks: 64KB body cap + context dict validation. Memory writes >64KB → 422. Bulk deletes capped at 200. Audit `?since=`/`?until=` validated as ISO. Admin PATCH user fields come from `_ALLOWED_USER_UPDATES` whitelist only.
- Role gates: workflow delete/scheduler/webhook, projects namespace endpoints, memory consolidate → admin/operator; `/system/status` DB path/platform → admin/operator; last admin can't be deleted.
- Output delete: SELECT-then-DELETE (no `RETURNING`, SQLite <3.35).
- Known gaps, not yet fixed — see `audits/security-audit-2026-10-17.md`: Supabase sync leaks `workflows.webhook_secret` (H-2); operators can mint API keys (M-14).

## Database
- Auth: `users` (+`onboarding_done`), `user_sessions`, `auth_events`, `system_config`.
- Agents: `agent_runs` (+eval_*, `deleted_at`), `agent_conversations`, `agent_conversation_turns`.
- Memory: `memory_entries` (+context_prefix, is_consolidated, archived, consolidated_from), `memory_fts`, `memory_vectors`.
- Workflows: `workflows` (+webhook_secret, webhook_enabled), `workflow_runs`.
- Migrations in `memory/db/migrations/`; run `python scripts/migrate.py`.

## Models, eval & memory
- `.env` is re-read on mtime change: `CLAUDE_MODEL` (default `claude-sonnet-5-5`) and `CLAUDE_FAST_MODEL` (`claude-haiku-5-5`, eval/consolidation) apply to the next run, no restart. Precedence: `.env` > process env > Settings > default. Price overrides: `CLAUDE_PRICE_IN_PER_MTOK` / `CLAUDE_PRICE_OUT_PER_MTOK`. `GET /system/models` shows what's in force.
- Agents inherit the default: YAMLs omit `model:`, `registry.upsert` stores `model = ''` when it equals the default, `resolve_model('')` returns the live default; pinned non-default models are respected.
- Never read `response.content[0].text` (thinking blocks come first) — use `first_text()`. Judge and consolidator use `max_tokens=1024`.
- Eval: `_bg_pool.submit(_trigger_eval, ...)`, sampled at 50%, score = tc×0.40 + fg×0.30 + cc×0.20 + sf×0.10. Correct scope refusals score task_completion=5.0; factual_grounding=5.0 when no claims made.
- Activity log: `executor._write_activity_log` uses category `context` (valid: fact, decision, context, preference, reminder, insight), confidence 0.5, key `activity_log:<agent>:<YYYYmmddHHMM>` — below the 0.8–0.85 injection floors on purpose. `mem_context` (≤3000 chars) is stored in `agent_runs.input`. Failures go async to a global `error_log` entry.
- Context: `context_builder.build_context(namespace, query)` runs in a 4s bg-pool timeout in the executor and falls back to flat FTS context. Namespace summary cached 5 min. Hybrid retrieval runs BM25 + vector in parallel, RRF k=60, falls back to FTS5 without rank-bm25. Consolidation: every 4h, entries >24h old, ≤200 per namespace per run.
- numpy 1.26 breaks if first-imported from several threads — keep the numpy import in `vector_store.py` and the early import in `create_app()`. Warmup logs `FAILED` on `_init()` failure.
- ChromaDB is derived data (SQLite is the source of truth). `KeyError '_type'` = index from another chromadb version. Rebuild: `python scripts/reindex_vectors.py` → stop API → move `data/chromadb` to `data/backups/chromadb-<ts>` → rename `data/chromadb_rebuild` to `data/chromadb` → start API. Rows written straight into SQLite aren't embedded until reindexed.
- Agent guards: analysis/briefing/research/writing agents ask clarifying questions and never fabricate. analysis-agent and client-manager-agent must not use training knowledge for business facts (empty context → MISSING INPUT PROTOCOL); client-manager out-of-scope requests get a one-line redirect.

## Streaming, chat & protocols
- `execute_stream()` is a generator; Flask wraps it in `stream_with_context`; never buffer. Output save on stream lives in `stream_agent()` (`agents.py`), not `_stream_response()`; attribution comes from the URL-path agent, never selectbox state; save uses `threading.Thread(daemon=True)` because `_bg_pool` (2 workers) can be starved by eval jobs.
- `_parse_stream_inputs()` returns `(prompt, namespace, context, messages, images, save_output)`; GET `save_output=true`, POST `"save_output": true`.
- Stream errors go in `st.session_state["_stream_error"]` and are appended to history as an assistant message in `_render_chat_tab` — never `st.error()` inside streaming (vanishes on rerun). Dashboard consumes SSE with `requests.get(..., stream=True)` + `iter_lines()`.
- Multi-turn history: `st.session_state[f"conv_{agent}_{ns}"]` (list of dicts). `chat_input(accept_file=True)` returns `ChatInputValue` (`.text`, `.files`) or str — normalise; sidebar uploader merged via `_all_files`. Images → base64 content blocks via `_build_messages(images=[{data, media_type}])`; text files → fenced prompt block. Voice: optional `openai-whisper`, `@st.cache_resource`.
- Webhooks: `POST /workflows/<name>/trigger` (X-Webhook-Secret) is the only non-JWT route besides `/health`. A2A: `GET /agents/<name>/.well-known/agent.json`. MCP server binds 127.0.0.1:5100, 12 agents as tools.

## Dashboard
- Order matters: `inject()` and `theme_toggle()` BEFORE the auth gate (they render on the login page); sidebar AFTER it. `inject()` runs every render. Login uses `st.form`.
- Token: decode locally, refresh via `/auth/refresh` if expiry <5 min; a 401 clears session_state + `st.rerun()`.
- Nav by role: client/viewer hide Settings, Workflows, Observability, Admin and gain Usage; staff sees Tickets only; Observability is admin/operator only. Onboarding tour only for client/viewer.
- Namespace white-labeling: brand color/accent/company_name/icon live in namespace metadata; `get_ns_brand()` (session_state, loaded on login for client/viewer) feeds sidebar logo, `aurora_hero()` and `_ns_brand_css()`. Colors must be strict hex (see audit M-16).
- `GET /system/namespace-stats?namespace=<ns>` backs the Usage page; Pulse Score = quality×40% + ticket_resolve×30% + memory_fresh×20% + workflow_ok×10%.
- Admin: Users action bar = Unlock (only if locked) | Deactivate/Reactivate | Reset Password | Edit | Delete (`@st.dialog` modals). Escape user-supplied text with `html.escape` before `unsafe_allow_html`.
- Agents catalog cards: per-card `components.v1.html` iframe whose JS clicks a hidden proxy button (`card:<key>`). Pre-select an agent by setting `st.session_state["chat_agent"]` BEFORE `st.selectbox()` — `index=` is ignored once the key exists. Tab persistence: a nonce-stamped `components.html` each render; JS restores `sessionStorage["claudeos_agents_tab"]`; skip clicking a tab whose `aria-selected === 'true'` (prevents rerun loop); `_goto_chat=True` → target 0, otherwise -1 (restore).
- Performance: parallel fetches via `ThreadPoolExecutor`; `api_get_cached` (30s; key includes JWT; `/agents/runs` bypasses cache; use `/agents?enabled_only=false` everywhere); Overview refresh via `st.fragment(run_every=8)`; ticket comments lazy-loaded; ticket assignees batch-fetched.
- Emails: `SMTP_*` env; ticket assignment notifies assignee, completion/closure notifies creator.

## Theme & design system
- `st.session_state["theme"]` dark/light, mirrored in `?theme=` and restored before `inject()`. `get_theme_vars()` → `_build_css(t)` styles the whole app. No aurora/animated backgrounds.
- Theme toggle: `components.v1.html(height=0)` using `window.parent.document` (`st.html` blocks scripts, `st.markdown` strips them). Fixed `bottom:24px; left:220px`, 44px circle.
- Fonts: Inter (body), Source Serif 4 (h1–h3, hero), JetBrains Mono (meta). Light theme `BG #FBF8F3`; dark keeps deep greens; static top glow. Cards: 10px radius, 1px green outline.
- WCAG AA (4.5:1 text, 3:1 icons) — `tests/test_contrast.py` enforces tokens, `nav_palette()` and status pills; rerun it after any palette change.
- Hidden proxy buttons (nav, KPI, cards, palette): use `components/proxy.py` (`proxy_button(label, key=…)`, `PROXY_CSS`, `cosClickProxy(doc, label)`; labels `nav:<page>`, `kpi:<key>`, `card:<key>`) — never select by `st-key-*`.
- Zero-height iframes, `<style>`-only markdown blocks and the theme-flip button must be out of layout flow in `_build_css`, or each adds ~200px dead space.
- SVG: toolbar `svg path` rules need `:not([fill="none"])` (MoreVert has a `fill="none"` bounding path); JS guards the same. `stToolbarActionButtonIcon` is a CSS background-image — never `background: transparent`; hide with `display:none` or colour with `filter:`. Streamlit 1.56 toolbar testids: `stAppDeployButton`, `stAppToolbar`, `stToolbarActionButton(Icon|Label)`, `stToolbarItems`.
- Verify visually (tests can't see CSS): headless puppeteer-core + Edge, log in, navigate with Ctrl+K (a URL reload drops the session).

## Stack & runtime
- Flask, Streamlit **1.56.0** + **pyarrow<22** in `.venv` (pyarrow ≥22 needs NumPy 2; chromadb 0.5.5 needs NumPy 1.x — keep both pins; code uses 1.5x APIs like `width='stretch'`). PyJWT ≥2.10.1, bcrypt 4.2.0, anthropic ≥0.40, plotly, APScheduler (timezone `SCHEDULER_TIMEZONE`, default Europe/Berlin), pytest. Optional: openai-whisper, mcp + uvicorn.
- Known issue: under PowerShell 5.1 Streamlit's stderr deprecation warning can make `start.ps1` exit 1 and kill Streamlit. If the dashboard is down, run `.venv\Scripts\python.exe -m streamlit run dashboard\app.py --server.port 8501 --server.headless true`.
- Tests: `pytest` with shared `conftest.py` fixtures (`fresh_db`, `app`, `client`, `admin_token`; scheduler mocked).
- Supabase sync is push-only (15-min auto) for users, tickets, workflows and memory tables; sensitive columns excluded via `_EXCLUDE_COLS` in `sync/engine.py`. Sync log delete: `DELETE /sync/log/<id>` or `DELETE /sync/log` with `{"ids":[...]}` (max 200).
