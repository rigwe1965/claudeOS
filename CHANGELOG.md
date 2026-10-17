# Changelog

All notable changes to ClaudeOS / FaiykeOS. Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [v17.3] — 2026-06-22 — Sales Readiness, Delete Audit & UX Hardening

### Added
- **Chat history persistence** (`561e2e1`): conversation turns are now restored from the database on every page refresh. Previously conversation was lost on browser reload. Existing turns from `agent_conversations` + `agent_conversation_turns` tables (migration 017) are seeded into session state on first load via `GET /agents/<name>/conversations/turns`.
- **Context degraded warning** (`561e2e1`): when the hybrid memory retrieval times out and falls back to fast FTS context, a subtle caption appears below the affected assistant response: _"Memory context unavailable — response may lack business-specific context."_ Signal is a null-byte sentinel in the context string emitted as an SSE `context_degraded` event. Runtime-only — does not persist across page refreshes.
- **Agent descriptions in chat dropdown** (`561e2e1`): agent selectbox now shows `[CATEGORY] Description` alongside each agent name — clients can pick the right agent without guessing.
- **White-label demo on landing page** (`561e2e1`): pure-CSS browser mockups in `docs/landing/index.html` showing default vs. client-branded sidebar side-by-side with a connecting arrow. No external deps.
- **Memory audit trail in agent runs** (`561e2e1`): `agent_runs.input` JSON now includes `context_sources` field listing the top memory section headers injected into the agent (e.g. `["Namespace Context [global]", "Recent Activity"]`). No migration required — appended to existing JSON column.
- **Usage page real navigation buttons** (`561e2e1`): actionable insight alerts (shown when Pulse Score < 60) now include a `Go →` button per alert that directly navigates to the relevant page (Agents, Tickets, Memory, Workflows).
- **429 rate limit toast** (`cdd5584`): `api_get()` now detects HTTP 429 responses and shows a `st.toast` warning instead of silently returning None and showing "API offline".
- **`/sync/status` cached** (`cdd5584`): added to `_READ_ONLY_PREFIXES` (30s TTL) — prevents rapid Settings page rerenders from exhausting rate limits on the sync status endpoint.
- **Sync log conversations/turns API endpoint** (`561e2e1`): `GET /agents/<name>/conversations/turns?namespace=<ns>&limit=<n>` — returns most recent turns for the latest conversation in a given namespace.

### Fixed
- **Sync log Select All + Delete now fully works** (`c6525cd`): Select All was previously broken (Streamlit widget ordering violation — `session_state` modified after widget rendered). Fixed with flag-before-widget pattern. Delete was silently succeeding but `st.success()` was invisible because `st.rerun()` fired immediately after. Fixed by storing success message in `session_state["_synclog_del_msg"]` so it survives the rerun.
- **Sync log cache causing deleted rows to reappear** (`c6525cd`): `/sync/log` was mistakenly added to `_READ_ONLY_PREFIXES` — 30s stale cache made deleted entries reappear on the next render. Removed.
- **Settings "API offline" false alarm** (`cdd5584`): when sync status fetch fails (rate limit, timeout, or endpoint error), error now reads "Could not fetch sync status — API may be rate-limited or temporarily unavailable. Refresh to retry." rather than the misleading "API offline".
- **Dead ctx_degraded history check removed** (`561e2e1`): `meta.ctx_degraded` check in the conversation history render loop was dead code — `agent_conversation_turns` has no metadata column, so seeded turns always had empty `meta`. Removed. Live streaming warning path unaffected.

### Verified
- **Full delete audit passed** (`scripts/test_deletes.py`): all 16 delete surfaces verified working end-to-end: memory single + bulk, agent run soft-delete (record stays in DB), workflow run, output single + bulk, API key single + bulk, session revoke single + bulk, ticket single + bulk, sync log single + bulk, user permanent delete.
- **Sync log cleared**: 789 accumulated error entries (all `[Errno 11001] getaddrinfo failed` — Supabase DNS failures from offline periods) bulk-deleted.

---

## [v17.2.1] — 2026-06-01 — UI Bugfix

### Fixed
- **Streamlit toolbar icon solid-square bug** (`brand.py`): The MoreVert (⋮) settings menu button in the Streamlit header was rendering as a solid colored square in both dark and light modes. Root cause: the MoreVert SVG contains a 24×24 bounding-box path (`M0 0h24v24H0V0z`) with `fill="none"` attribute; our CSS/JS fill override was ignoring that attribute and painting it solid. Fix: added `:not([fill="none"])` to all `svg path` selectors in both CSS blocks, added explicit `path[fill="none"]` → `fill: none` rules, and added `getAttribute('fill') === 'none'` guard in the JS `fixHeader` loop. Also targeted the correct Streamlit 1.56 testids: `stToolbarActionButton`, `stToolbarActionButtonIcon`, `stToolbarActionButtonLabel`, `stAppDeployButton`, `stToolbarItems`.

---

## [v17.2] — 2026-05-31 — Performance, Security & Architecture Hardening

### Performance
- **Eliminated SELECT before UPDATE** (`b5436df`): agent run completion no longer reads input row before updating — builds JSON directly from in-scope vars (saves 1 DB round-trip per run).
- **Streaming INSERT now starts as `running`** (`b5436df`): `create_run_record(status='running')` skips the separate `_update_run_status` UPDATE call per stream.
- **ChromaDB probe cached** (`b5436df`): `/system/status` reuses the existing singleton client with a 30s TTL cache — eliminates 200–800ms `PersistentClient` init on every Overview page load.
- **`namespace_stats` query collapsed** (`b5436df`): 7 sequential SQLite round-trips replaced with 1 compound SELECT using scalar subqueries.
- **Bulk memory delete batched** (`b5436df`): replaced N×`engine.delete()` calls (N selects + N deletes + N ChromaDB calls) with a single batch SELECT for permission checks, one `DELETE WHERE id IN (...)`, and grouped ChromaDB deletes per namespace.
- **Duplicate `_entry_dict` removed** (`b5436df`): second definition at end of `memory.py` was shadowing the first, silently returning fewer fields (missing `source`, `agent_id`, `session_id`, etc.) on all hybrid-search results.
- **Context builder seen_keys cached** (`b5436df`): `_ns_summary_cache` now stores `(result, seen_keys_set, expiry)` — eliminates string re-parse on every cache hit.
- **Non-blocking live refresh** (`b5436df`): Overview `time.sleep(8)` replaced with `st.fragment(run_every=8)` — session thread no longer frozen for 8s per refresh cycle (native Streamlit 1.38).
- **Duplicate import removed from render loop** (`b5436df`): `import streamlit.components.v1` was executing inside the agent catalog card loop (up to 6× per render); deduplicated to module-level import.
- **Agent list cache hit fixed** (`b5436df`): Overview used `/agents`, Agents page used `/agents?enabled_only=false` — different cache keys meant both always hit Flask. Standardized to `?enabled_only=false`.

### Security
- **MCP server bound to localhost** (`b5436df`): was `0.0.0.0` with zero authentication — any LAN host could invoke all 12 agents in any namespace. Now `127.0.0.1` only.
- **Workflow run delete role-gated** (`b5436df`): `DELETE /workflows/runs/<id>` and bulk variant now require `admin`/`operator` — any authenticated role (including `viewer`) could previously destroy audit trail records.
- **Workflow management role-gated** (`b5436df`): scheduler reload, webhook enable/disable, and workflow enable/disable now require `admin`/`operator`.
- **Workflow limit params hardened** (`b5436df`): `int()` casts on `?limit=` params wrapped in try/except returning 400; all limits bounded to max 200.
- **Workflow bulk delete capped** (`b5436df`): max 200 IDs per bulk delete request; returns 422 if exceeded.
- **Stored XSS closed in Admin Branding** (`b5436df`): company name and icon injected into `unsafe_allow_html` preview are now escaped with `html.escape()`.
- **System status info gated by role** (`b5436df`): DB path, absolute filesystem path, platform, and Python version no longer returned to `client`/`viewer` roles.
- **Content-Security-Policy header added** (`b5436df`): `default-src 'none'; frame-ancestors 'none'` on all Flask API responses.
- **HSTS header added** (`b5436df`): `Strict-Transport-Security` set when `CLAUDEOS_ENV=production`.
- **Settings repr masks credentials** (`b5436df`): `ANTHROPIC_API_KEY`, `SMTP_PASSWORD`, `SUPABASE_*`, `CLAUDEOS_SECRET_KEY` shown as `***` in any log/repr output.
- **Worktree weak secret default removed** (`b5436df`): `.claude/worktrees/…/config.py` had `CLAUDEOS_SECRET_KEY = "dev-secret-change-in-prod"` — removed, now required field.
- **Audit log date params validated** (`b5436df`): `?since=` and `?until=` on `GET /admin/audit` validated against ISO datetime pattern; returns 400 on invalid format.
- **Dashboard session TTL shortened** (`b5436df`): session key window reduced from 7 days to 24 hours.
- **Namespace slug enumeration closed** (`b5436df`): self-registration returned different errors for missing vs wrong-type namespaces; now returns a single generic message.

### Architecture
- **Stale run cleanup on startup** (`b5436df`): `_cleanup_stale_runs()` resets any `pending`/`running` agent or workflow runs older than 1 hour to `failed` on Flask startup — eliminates perpetually-stuck records from crash artifacts.
- **Memory value size limit** (`b5436df`): memory write endpoint caps `value` at 64KB; returns 422 if exceeded — prevents DoS via ChromaDB embed + FTS5 index bloat.
- **Scheduler timezone default** (`b5436df`): `SCHEDULER_TIMEZONE` changed from `Africa/Lagos` to `Europe/Berlin`; override via `.env`.

---

## [v17.0.1] — 2026-05-30

### Fixed
- **Output agent attribution** (`2afe202`): outputs now always carry the correct agent name. Root cause: `_stream_response()` in `_agents.py` was saving output using Streamlit selectbox state (stale across reruns). Fix: moved save entirely to `stream_agent()` in `agents.py` where `agent.name` comes from URL path registry lookup.
- **Stream error persistence** (`2afe202`): errors no longer flash and disappear on rerun. Fix: store in `st.session_state["_stream_error"]`, append to chat history as persistent assistant entry.
- **Output save reliability** (`2afe202`): switched from `_bg_pool.submit()` to `threading.Thread(daemon=True)` — avoids save being blocked behind concurrent eval jobs in the 2-worker pool.

### Added
- **Web intelligence + cross-agent output access** (`8f020e8`): agents can reference and build on outputs produced by other agents.

---

## [v17.0] — 2026-05-28 — Phase 15: Commercial Package

### Added
- **FaiykeOS brand** (`88a793f`): commercial product name applied to handbook, docs, landing pages; internal codebase retains ClaudeOS name.
- **Distribution ZIP** (`4c37bfa`): `scripts/build_package.py` → `dist/FaiykeOS-v17.0.zip` (~475 KB, 153 files); excludes .env, data/, logs/, dev scripts, __pycache__.
- **Sales template** (`fb2ba33`): `docs/landing/index.html` (marketing landing page) + `docs/landing/pricing.html` (3-tier pricing + Formspree booking form).
- **Buyer collateral** (`fb2ba33`): `docs/PRODUCT_README.md`, `docs/SETUP_GUIDE_NONTECHNICAL.md`, `docs/AGENCY_LICENSE.md`.
- **Sync log delete** (`cb82b81`, `26d1d38`): single-entry 🗑 button + bulk checkbox delete via `st.data_editor`; `DELETE /sync/log/<id>` and `DELETE /sync/log` (bulk, max 200).
- **Hallucination guard strengthened** (`87815fb`): analysis-agent and client-manager-agent block use of training data for business-specific facts; empty context triggers MISSING INPUT PROTOCOL.
- **Evaluator scope-refusal rubric** (`11f51e5`): correct scope refusals score `task_completion=5.0` — agents enforcing their own boundaries are not penalised.
- **Handover hardening** (`8405295`, `aaae16b`, `a93b2d8`, `3c25eec`): soft-delete (agent_runs + outputs), DB backup with 7-backup retention, 15 DB indexes, rate limiter SQLite storage, real ChromaDB health probe, webhook body size limit, role enforcement on sensitive routes, 115 passing tests.

### Fixed
- Handbook duplicate footer on last page (`b4e561c`).
- Sync log delete false 404 — `SELECT changes()` resets after commit; switched to `cursor.rowcount` (`26d1d38`).
- All agents now ask clarifying questions when input is missing instead of hallucinating (`b1211e5`, `49c6631`).

---

## [v16.0] — 2026-05-27 — Phase 14: Commercial Upgrade

### Added
- **Namespace white-labeling** (`6db1bc1`): per-namespace color, accent, company name, icon stored in metadata; sidebar logo and aurora hero pill reflect client brand.
- **Client Usage Dashboard** (`6db1bc1`): `_usage.py` page for client/viewer roles — Namespace Pulse Score (0–100 composite gauge), KPI grid, activity feed, memory summary.
- **Namespace Pulse Score** (`6db1bc1`): composite 0–100 = quality×40% + ticket_resolve×30% + memory_fresh×20% + workflow_ok×10%.
- **Email notifications** (`6db1bc1`): `core/notifications.py` — stdlib smtplib, fire-and-forget, branded HTML; fires on ticket assignment and completion.
- **Admin Branding tab** (`6db1bc1`): 7th tab in Admin Panel — per-namespace color picker, accent, company name, icon, live preview.
- **Rate limiting** (`6db1bc1`): flask-limiter; agent /run 30/min, /stream 20/min, workflow /trigger 10/min, /run 20/min.
- **Security headers** (`6db1bc1`): X-Content-Type-Options, X-Frame-Options, X-XSS-Protection on all Flask responses.
- **CORS hardening** (`6db1bc1`): `ALLOWED_ORIGINS` env var replaces wildcard `*`.
- **Edit User dialog** (`528346c`): `@st.dialog` modal — change role, namespace, email, active status, force-pw flag.
- **Delete User** (`528346c`): permanent-delete confirmation dialog; last-admin guard.
- **Admin unlock** (`eba9751`): Unlock button shown only when user is actually locked (context-aware).
- **Onboarding persistence** (`03366f6`): `onboarding_done` DB column (migration 018); tour never shows again after first completion.
- **Client Onboarding tab** (`7a13a1c`): 14-field schema seed per namespace in Admin Panel.
- **Namespace Usage tab in Observability** (`744f6a3`): cross-namespace token/cost/quality comparison, stacked bar chart.

### Fixed
- Output delete fails on SQLite < 3.35 — SELECT-then-DELETE replaces DELETE...RETURNING (`0cadc72`).
- Output timestamps showed date only — now YYYY-MM-DD HH:MM in all views (`0cadc72`).
- Activity feed showed agent UUID instead of readable name — dispatcher.list_runs JOINs agents table (`552e5b3`).
- Memory namespace list was hardcoded — now fetched dynamically from API (`5423ba2`).
- Context tier duplication when namespace == global (`70860f2`, `ba0cb43`).
- Theme toggle overlapping sidebar text — fixed at `left:220px` (`86bbade`).
- Voice input widget not resetting on Clear Conversation (`208d58b`, `b969309`).
- Images not forwarded through SSE stream endpoint (`291eece`).
- `/system/stats` fetch failed on non-main thread (`bed94f7`).
- Browser refresh lost active page — persisted to URL (`64c4140`).
- XSS escaping, security hardening across dashboard inputs (`63a83d6`).
- Cross-user cache pollution — `/agents/runs` excluded from `_cached_api_get` (`d0583a6`).

---

## [v15.0] — 2026-05-23 — Phases 10–13: Intelligence, Memory, Protocols, Multimodal

### Added
- **SSE streaming** (`c1233c0`): `GET/POST /agents/<name>/stream` — token-by-token responses via Server-Sent Events.
- **LLM-as-Judge eval** (`c1233c0`): async Haiku evaluation after every run — 4 dimensions (task completion, factual grounding, conciseness, safety); scores stored in `agent_runs.eval_score`.
- **Observability dashboard** (`c1233c0`): 5 tabs — Quality Scores, Latency (p50/p95/p99), Token Cost, Memory Health, Namespace Usage (admin/operator only).
- **Hybrid BM25+Vector RAG** (`c1233c0`): `memory/retriever.py` — BM25 + ChromaDB run in parallel, fused via RRF (k=60).
- **Tiered context injection** (`c1233c0`): `memory/context_builder.py` — ~40% input token reduction vs flat injection.
- **Memory consolidation engine** (`c1233c0`): `memory/consolidator.py` — 4h APScheduler job; clusters, summarises, archives originals (never deletes).
- **Webhook triggers** (`c1233c0`): `POST /workflows/<name>/trigger` — HMAC-secured, no JWT required.
- **MCP Tool Server** (`c1233c0`): `mcp/server.py` on port 5100 — all 12 agents exposed as MCP tools.
- **A2A Agent Cards** (`c1233c0`): `GET /agents/<name>/.well-known/agent.json` — machine-readable capability cards.
- **Multi-turn chat UI** (`c1233c0`): conversation history per agent per session (migration 017).
- **Image/screenshot analysis** (`c1233c0`): base64 content blocks via executor; POST body `images` field.
- **Voice input** (`c1233c0`): `st.audio_input` + local Whisper transcription (optional).
- **Live Overview** (`c1233c0`): auto-refresh toggle (8s), eval score pills, error/running alert banners.
- **Onboarding tour** (`c1233c0`): first-login only for client/viewer roles; 5-slide walkthrough.

### Fixed
- SSE stream endpoint 500 — bypass Werkzeug hop-by-hop Connection header; use `direct_passthrough=True` and yield bytes (`d7c281d`).
- Clear conversation button — use `on_click` callback instead of bare `st.rerun()` (`fe1d3bc`).
- 6 production bugs patched after full system audit (`3805121`).
- 3 production bugs: stream logging, blocking freeze, workflow attribution (`aab3668`).
- Observability score distribution — 0.5-step buckets (`4e56ec8`).

---

## [v13.0] — 2026-05-22 — Phase 9: Ticketing System

### Added
- Full ticketing system (`569c52d`): SLA tiers P1–P4, staff role, namespace isolation, ticket status workflow (open → assigned → work_in_progress → completed → closed).
- Bulk delete across all resource types (`b66bbac`).
- Ticket badge in Overview sidebar (`60906b2`).

### Fixed
- Namespace isolation enforcement for client/viewer roles on agents, outputs, vault (`a8d9ec9`, `2824eee`, `614efdf`).

---

## [v12.0] — 2026-05-22 — Phase 8: Auth & Security

### Added
- JWT + bcrypt auth (`c1233c0` era): 5 roles (admin, operator, client, viewer, staff), account lockout, refresh tokens, audit log.
- API key auth (X-API-Key fallback on all routes).
- Admin Panel: Users, API Keys, Audit Log, Sessions, Security config tabs.
- `must_change_password` flag — forced pw change on next login.
- Case-insensitive username lookup.
- Security audit + full fix pass (`3504700` – `cb157d8`): CR/HI/ME/LO severity fixes across all routes.

---

## [v1.0] — 2026-05-22 — Initial Release

### Added
- Core infrastructure: Flask :5000 API + Streamlit :8501 dashboard.
- Memory Engine: SQLite FTS5 + ChromaDB vector store.
- Agent Registry: 12 agents, YAML definitions.
- Workflow Engine: APScheduler, 7 pipelines.
- Client Vault: namespace isolation, per-client workspaces.
- Output Manager: auto-tag, FTS search, Markdown/PDF export.
- Supabase Cloud Sync: push-only, 15-min auto-sync.
- Brand: #407E3C green + white, dark/light mode theme toggle.
