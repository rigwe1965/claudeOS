<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="assets/banner-light.svg">
    <img src="assets/banner-light.svg" alt="ClaudeOS" width="100%"/>
  </picture>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-407E3C?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"/>
  <img src="https://img.shields.io/badge/Flask-3.0-407E3C?style=flat-square&logo=flask&logoColor=white" alt="Flask 3.0"/>
  <img src="https://img.shields.io/badge/Streamlit-1.56-407E3C?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit 1.56"/>
  <img src="https://img.shields.io/badge/Supabase-cloud_sync-407E3C?style=flat-square&logo=supabase&logoColor=white" alt="Supabase cloud sync"/>
  <img src="https://img.shields.io/badge/Windows-10-407E3C?style=flat-square&logo=windows&logoColor=white" alt="Windows 10"/>
  <img src="https://img.shields.io/badge/license-MIT-5a9e56?style=flat-square" alt="MIT license"/>
</p>

<p align="center">
  Coordination layer unifying Claude Code skills, agents, and workflows into a single AI control center.
</p>

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 0  · Streamlit Dashboard        :8501         │
├─────────────────────────────────────────────────────┤
│  Layer 1  · Flask REST API             :5000         │
├──────────────┬──────────────────────────────────────┤
│  Layer 2     │  Memory Engine                        │
│  SQLite FTS5 │  ChromaDB vectors                     │
├──────────────┼──────────────────────────────────────┤
│  Layer 3     │  Agent Registry                       │
│  12 agents   │  YAML definitions                     │
├──────────────┼──────────────────────────────────────┤
│  Layer 4     │  Workflow Engine                      │
│  APScheduler │  7 pipelines                          │
├──────────────┼──────────────────────────────────────┤
│  Layer 5     │  Client Vault                         │
│  Namespaces  │  Isolated workspaces                  │
├──────────────┼──────────────────────────────────────┤
│  Layer 6     │  Output Manager                       │
│  Auto-tag    │  FTS search · Export                  │
├──────────────┼──────────────────────────────────────┤
│  Layer 7     │  Supabase Cloud Sync                  │
│  Push-only   │  Watermark · Auto 15min               │
├──────────────┼──────────────────────────────────────┤
│  Layer 8     │  Auth & Security                      │
│  JWT/bcrypt  │  Roles · Audit log                    │
├──────────────┼──────────────────────────────────────┤
│  Layer 9     │  Ticketing System                     │
│  SLA tiers   │  Staff role · Bulk ops                │
├──────────────┼──────────────────────────────────────┤
│  Layer 10    │  Real-Time Intelligence               │
│  SSE stream  │  LLM-as-Judge · Observability         │
├──────────────┼──────────────────────────────────────┤
│  Layer 11    │  Advanced Memory                      │
│  BM25+vector │  RRF rerank · Consolidation engine    │
├──────────────┼──────────────────────────────────────┤
│  Layer 12    │  Protocols                            │
│  Webhooks    │  MCP tool server :5100 · A2A cards    │
├──────────────┼──────────────────────────────────────┤
│  Layer 13    │  Multimodal                           │
│  Multi-turn  │  Image upload · Voice input           │
└──────────────┴──────────────────────────────────────┘
```

## Roles

| Role | Access |
|------|--------|
| `admin` | Full access — all namespaces, user management, admin panel |
| `operator` | All namespaces, all resources; no user management |
| `client` | Own namespace only; read/write memory, run agents, view outputs |
| `viewer` | Own namespace, read-only |
| `staff` | Sees only assigned tickets; can self-assign and advance ticket status |

## Setup

### Requirements
- Python 3.11+
- Windows 10 / PowerShell

### Install

```powershell
git clone https://github.com/rigwe1965/claudeOS.git
cd ClaudeOS
pip install -r requirements.txt
pip install rank-bm25 plotly
```

### Configure

```powershell
copy .env.example .env
```

Edit `.env`:

```env
ANTHROPIC_API_KEY=your_key_here
CLAUDEOS_SECRET_KEY=change_this_in_prod

# Optional: Supabase cloud sync
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
```

### Migrate + Seed

```powershell
python scripts/migrate.py
python scripts/seed_agents.py
python scripts/seed_workflows.py
python scripts/seed_namespaces.py
python scripts/create_admin.py --username admin --password Admin123!
```

### Start

```powershell
.\scripts\start.ps1
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:8501 |
| API | http://localhost:5000/api/v1/health |
| MCP Server | http://localhost:5100/mcp |

## Cloud Sync

1. Create a [Supabase](https://supabase.com) project
2. Run `sync/supabase_schema.sql` in Supabase SQL Editor
3. Add credentials to `.env` and restart
4. Auto-sync fires every 15 minutes — or trigger manually from the **Settings** tab

## Phase 10–13 Features

### Phase 10 — Real-Time Intelligence

**SSE Streaming**
Agent responses stream token-by-token via Server-Sent Events. Hit `GET /agents/<name>/stream?prompt=...` and pipe the `data:` events into your UI. The multi-turn chat page in the dashboard uses this natively.

**LLM-as-Judge**
After every agent run completes, an async background task dispatches the prompt+output to Claude Haiku for evaluation. Four dimensions scored 0–5:
- Task Completion (weight 40%) — did the output address the prompt?
- Factual Grounding (weight 30%) — are claims grounded in injected memory?
- Conciseness (weight 20%) — appropriate length, no padding?
- Safety (pass/fail, weight 10%) — no harmful content?

Overall score = weighted average. Scores are stored in `agent_runs.eval_score` and appear in Run History and Overview within ~10 seconds of run completion. Roughly half of runs are sampled for scoring, so not every run has a score. The judge uses the model set in `CLAUDE_FAST_MODEL`.

**Observability Dashboard** (admin/operator)
Four sub-tabs: Quality Scores (per-agent averages, distribution chart, dimension breakdown, low-quality alerts), Latency (p50/p95/p99 across all runs, per-agent avg), Token Cost (input/output totals, estimated USD, per-agent), Memory Health (entry counts by namespace, consolidation trigger).

### Phase 11 — Advanced Memory

**Hybrid BM25+Vector RAG with RRF Reranking**
`memory/retriever.py` runs BM25 keyword search and ChromaDB vector search in parallel, then fuses results via Reciprocal Rank Fusion (RRF). Yields significantly better recall than either method alone, especially for short or technical queries.

**Tiered Context Injection**
`memory/context_builder.py` selects memory entries in priority tiers before injecting into agent system prompts. Only the highest-relevance entries fill the context window. Measured ~40% reduction in input token consumption versus flat injection.

**Memory Consolidation Engine**
An APScheduler job runs every 4 hours: clusters semantically similar entries per namespace, calls Claude to produce a single summary entry, then marks the originals as consolidated. Keeps memory stores lean and coherent over time.

### Phase 12 — Protocols

**Webhook-Triggered Workflows**
Enable a per-workflow webhook URL from the Workflows → Webhooks tab. External systems POST to `POST /workflows/<name>/trigger` with `X-Webhook-Secret: <secret>` — no JWT required. Payload `context` dict is passed as workflow input.

**MCP Tool Server**
All 12 ClaudeOS agents are exposed as MCP (Model Context Protocol) tools at `http://localhost:5100/mcp`. Any MCP-compatible client (Claude Desktop, Cursor, custom agents) can call your agents as first-class tools.

**A2A Agent Cards**
Each agent exposes a machine-readable capability card at `GET /agents/<name>/.well-known/agent.json` following the Agent-to-Agent (A2A) protocol. Cards include name, description, accepted input schema, and output schema for automatic tool discovery.

### Phase 13 — Multimodal

**Multi-Turn Chat UI**
The Agents page adds a Chat tab with full conversational history per agent per session. Supports:
- Streaming responses (tokens render as they arrive)
- Image/screenshot upload for visual analysis
- Voice input (record audio, auto-transcribed via Whisper)
- Eval score badges on each assistant response
- Persistent error messages — stream errors survive page reruns and appear inline in chat history
- Correct agent attribution on saved outputs — backend saves with registry-resolved agent name, not UI selectbox state

**Live Overview Dashboard**
Overview now includes an auto-refresh toggle (every 8 seconds), an error alert strip (red banner when recent runs failed), a running-now indicator (yellow banner for in-flight agents), and eval score pills on each run entry (green ≥4.0, amber ≥2.5, red <2.5).

## MCP Server

Start the MCP server alongside the main stack:

```powershell
.\scripts\start_mcp.ps1
```

Add to Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "claudeos": {
      "url": "http://localhost:5100/mcp"
    }
  }
}
```

Optional dependencies for full MCP + voice support:

```powershell
pip install mcp uvicorn openai-whisper
```

Note: first voice transcription downloads ~140 MB Whisper model automatically.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | System health (public) |
| `GET/POST` | `/api/v1/memory` | Memory entries |
| `POST` | `/api/v1/memory/consolidate` | Trigger memory consolidation |
| `GET` | `/api/v1/memory/hybrid-search` | Hybrid BM25+vector search with RRF reranking |
| `GET` | `/api/v1/agents` | List agents |
| `POST` | `/api/v1/agents/{id}/run` | Run agent |
| `GET` | `/api/v1/agents/{name}/stream` | SSE streaming response (token-by-token) |
| `GET` | `/api/v1/agents/{name}/.well-known/agent.json` | A2A Agent Card |
| `POST` | `/api/v1/agents/{name}/webhook/enable` | Enable webhook for agent |
| `GET` | `/api/v1/workflows` | List workflows |
| `POST` | `/api/v1/workflows/{name}/trigger` | Webhook trigger (public, X-Webhook-Secret auth) |
| `GET` | `/api/v1/outputs` | List outputs |
| `DELETE` | `/api/v1/outputs/bulk` | Bulk delete outputs |
| `GET/POST` | `/api/v1/tickets` | List / create tickets |
| `GET/PUT/DELETE` | `/api/v1/tickets/{id}` | Get, update, or delete a ticket |
| `DELETE` | `/api/v1/tickets/bulk` | Bulk delete tickets |
| `GET` | `/api/v1/tickets/stats` | Ticket counts by status/priority |
| `GET` | `/api/v1/sync/status` | Sync status |
| `POST` | `/api/v1/sync/push` | Push to Supabase |

## Performance

- Parallel API calls via `ThreadPoolExecutor` — overview data fetched in one shot
- Ticket assignees batch-fetched in a single query (N+1 eliminated)
- Ticket comments lazy-loaded on toggle — not fetched on every card render
- `_cached_api_get` cache key scoped per JWT token — no cross-user cache pollution
- Bulk session revoke uses single `UPDATE ... WHERE id IN (...)` — no per-row loop
- `ticket_stats` aggregates 5 metrics in 3 queries via `SUM(CASE WHEN ...)`
- `idx_events_created` index on `system_events(created_at DESC)` — migration 012
- `_api_key_last_updated` bounded to 500 entries with TTL eviction
- Security settings update uses `executemany` — no per-row loop
- `_is_assignee` uses EXISTS point query — no full list fetch
- Hybrid RRF retrieval: BM25 and vector search run in parallel threads, fused before scoring
- Tiered context injection: ~40% input token reduction versus flat memory injection
- BM25 index built once per namespace on first query, cached in-process for subsequent calls
- Memory consolidation 4h job: clusters then summarises, keeps SQLite row count bounded
- Eval scoring is fully async — no latency added to the agent run itself

## Stack

| | |
|--|--|
| **AI** | Anthropic SDK · claude-sonnet-5-5 (agents) · claude-haiku-5-5 (eval, consolidation) — set in `core/models.py` |
| **Backend** | Flask · waitress (Windows WSGI) |
| **Dashboard** | Streamlit |
| **Memory** | SQLite FTS5 · ChromaDB · sentence-transformers · rank-bm25 |
| **Scheduler** | APScheduler |
| **Cloud** | Supabase |
| **Observability** | plotly |
| **MCP** | mcp · uvicorn (optional) |
| **Voice** | openai-whisper (optional) |
| **Testing** | pytest |

## Models & Cost

Models are chosen in one place, `core/models.py`, and every agent run, eval and consolidation job follows it.

| `.env` setting | Effect | Default |
|--|--|--|
| `CLAUDE_MODEL` | Agents, chat, streaming | `claude-sonnet-5-5` |
| `CLAUDE_FAST_MODEL` | Quality judge, memory consolidation | `claude-haiku-5-5` |
| `CLAUDE_PRICE_IN_PER_MTOK` / `CLAUDE_PRICE_OUT_PER_MTOK` | USD per million tokens shown in cost estimates | built-in list price (Sonnet 5.5: $2 / $10) |

- Edits to `.env` apply to the next run — no restart needed.
- Agents inherit the default model; only an agent deliberately pinned to another model keeps it.
- `GET /api/v1/system/models` shows the models and prices currently in force. Cost figures on the Usage and Observability pages are estimates at that price.

## Troubleshooting

| Symptom | Cause / fix |
|--|--|
| Semantic search returns nothing, log shows `KeyError '_type'` | The ChromaDB index was written by a different chromadb version. Rebuild it from SQLite: `python scripts/reindex_vectors.py`, then stop the API, move `data/chromadb` to `data/backups/`, rename `data/chromadb_rebuild` to `data/chromadb`, and start the API. |
| `ChromaDB warmup FAILED` in `logs/api.log` | Semantic search is off and memory falls back to keyword search. Check the warning above it; the index rebuild above fixes the `_type` case. |
| Dashboard is down after `scripts/start.ps1` | On Windows PowerShell 5.1 a Streamlit warning on stderr can make the script exit and stop Streamlit. Start it directly: `.venv\Scripts\python.exe -m streamlit run dashboard\app.py --server.port 8501 --server.headless true` |
| Usage page shows Avg Quality `0.0/5` | No scored runs yet (scoring is sampled and async). Run a few agents and wait ~10 seconds. |

## Brand

`#407E3C` green · `#FFFFFF` white · `#5a9e56` accent
