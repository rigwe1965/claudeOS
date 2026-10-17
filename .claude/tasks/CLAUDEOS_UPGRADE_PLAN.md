# ClaudeOS Upgrade Plan — Phase 10–13
**Status:** AWAITING APPROVAL  
**Author:** Claude Code  
**Date:** 2026-05-23  
**Goal:** Elevate ClaudeOS to a top-tier AI Operating System with state-of-the-art capabilities missing from the current system.

---

## Executive Summary

After a full codebase audit and deep research into the AI landscape as of mid-2025, I identified **4 upgrade phases** targeting the biggest gaps between what ClaudeOS has today and what production-grade AI systems are running. Each phase is independent, ordered by impact-to-effort ratio, and builds on the last.

---

## Gap Analysis: What You Have vs. What's Missing

| Area | Current State | Industry Standard | Gap |
|------|--------------|------------------|-----|
| Agent responses | Full response returned at end (blocking) | SSE streaming, token-by-token | Users wait 5–30s, no feedback |
| Observability | Basic `agent_runs` DB row | Full trace trees, latency, eval scores | No insight into WHY agents fail |
| Output quality | Stored but never scored | LLM-as-Judge scoring on every run | No quality signal |
| Memory architecture | Flat SQLite + ChromaDB | 4-tier (working/episodic/semantic/procedural) | Memory bloat, no consolidation |
| RAG retrieval | Vector similarity only | Hybrid BM25+vector + reranking | Misses keyword-relevant results |
| Context injection | Flat dump of high-confidence facts | Tiered (summary + recent + retrieved) | Wastes tokens, reduces coherence |
| Workflow triggers | APScheduler cron only | Webhooks, event-driven, HTTP triggers | Can't react to external events |
| Agent protocols | Direct Python calls | MCP tool protocol, A2A Agent Cards | Not composable with any external system |
| Multimodal | Text only | Voice input + image/screenshot analysis | No natural interaction layer |
| Dashboard UX | Static page refreshes | Live streaming output, real-time metrics | Feels slow vs. modern AI tools |

---

## Phase 10: Real-Time Intelligence Layer
**Theme:** Make ClaudeOS *feel* like a live AI system, not a batch processor.  
**Effort:** Medium (2–3 days) | **Impact:** Very High — visible immediately to every user.

### 10.1 — Streaming Agent Responses (SSE)
**Why:** The single biggest UX complaint with LLM-based tools is waiting. GPT, Perplexity, Claude.ai all stream token-by-token. Your agents return nothing for 10–30 seconds then dump text. This phase fixes that.

**What:** 
- Add `stream=True` to Anthropic SDK calls in `agents/executor.py`
- New Flask endpoint `GET /api/v1/agents/stream` — uses `flask.Response(stream_with_context(...))` returning `text/event-stream`
- Dashboard agent chat page consumes the stream via Streamlit `st.write_stream`
- Progress indicator shows tokens-per-second live

**Files changed:** `agents/executor.py`, `core/api/routes/agents.py`, `dashboard/_pages/_agents.py`

### 10.2 — Langfuse Observability Integration
**Why:** Right now you have no visibility into which agents fail, which prompts degrade over time, or where latency spikes occur. Langfuse is open-source, self-hostable, and integrates with Anthropic SDK in ~50 lines. It gives you full trace trees: every LLM call, every memory retrieval, every tool invocation — timed, logged, searchable.

**What:**
- `pip install langfuse` — Langfuse Python SDK
- Wrap Anthropic calls in `agents/executor.py` with `@observe()` decorator
- Trace spans added for memory retrieval, context build, API call, output save
- New "Observability" dashboard tab showing: latency percentiles (p50/p95), cost by agent, error rate, cached vs. uncached token ratio
- Langfuse can run locally (Docker, or their hosted free tier for your volume)

**Files changed:** `agents/executor.py`, `core/config.py`, new `dashboard/_pages/_observability.py`

### 10.3 — LLM-as-Judge Quality Scoring
**Why:** You store every agent output but you have no idea if they are good. LLM-as-Judge is the 2025 standard — use Claude Haiku (cheap, fast) to score each completed run on 4 dimensions: task completion (0–5), factual grounding (0–5), conciseness (0–5), safety (pass/fail). These scores appear on the run history page and alert you to degrading agent quality before clients notice.

**What:**
- Background async evaluator: after each run completes, fire a Haiku call with the output + rubric
- Schema: add `eval_score`, `eval_reasoning`, `eval_dimensions` JSON columns to `agent_runs` table (migration 014)
- Dashboard shows quality trend sparklines per agent — immediately visible quality regression
- Alert: if average score drops below 3.0 in last 10 runs → show warning banner on Overview

**Files changed:** New `agents/evaluator.py`, `agents/executor.py`, `data/db/migrations/014_agent_eval_scores.sql`, `dashboard/_pages/_agents.py`, `dashboard/_pages/_overview.py`

---

## Phase 11: Advanced Memory & Intelligent Retrieval
**Theme:** Make the memory system actually intelligent — not just a flat key-value store with vector search.  
**Effort:** Medium-High (3–4 days) | **Impact:** High — directly improves every agent output.

### 11.1 — Memory Consolidation Engine
**Why:** Your SQLite + ChromaDB stores grow unbounded. Every agent run adds memories but nothing summarizes or prunes them. Top AI systems (MemGPT, Mem0) run background consolidation: compress 50 raw episodic memories → 1 semantic summary. Result: faster retrieval, lower token cost, better generalization.

**What:**
- New `memory/consolidator.py` — background job (scheduled hourly via APScheduler)
- Algorithm: group episodic entries by namespace + category, find clusters via embedding similarity, summarize each cluster with Haiku into 1 high-confidence semantic fact
- Old episodic entries marked `archived=True` (not deleted — auditable)
- New DB column `is_consolidated` + `source_ids` JSON on semantic entries (migration 013)
- Dashboard memory page shows consolidation stats: "48 episodes → 6 semantic facts"

**Files changed:** New `memory/consolidator.py`, `memory/engine.py`, migration 013, `dashboard/_pages/_memory.py`

### 11.2 — Hybrid BM25 + Vector RAG with Reranking
**Why:** Your current retrieval is vector-only. If a user says "find the RECI contract signed May 2025", vector search fails (dates, proper nouns, IDs are weak in embeddings). BM25 keyword search catches exact matches. Combining both with Reciprocal Rank Fusion (RRF) gives you the best of both worlds — the 2025 industry standard for production RAG.

**What:**
- Add `rank-bm25` library for BM25 scoring over memory text
- `memory/retriever.py` — new hybrid retrieval module:
  - Runs BM25 + vector search in parallel (ThreadPoolExecutor)
  - Merges results via RRF formula: `score = 1/(k + bm25_rank) + 1/(k + vector_rank)`
  - Optional: add BGE-Reranker cross-encoder pass for top-10 results (reorders final set)
- `memory/engine.py` updated to use `retriever.py` instead of direct ChromaDB call
- Result: 30–50% better retrieval recall on agent context injection

**Files changed:** New `memory/retriever.py`, `memory/engine.py`, `requirements.txt`

### 11.3 — Tiered Context Injection
**Why:** `agents/executor.py` currently injects a flat dump of high-confidence facts. This wastes tokens on irrelevant facts and can hit context limits. Tiered injection (used by MemGPT, Letta, production LangChain apps) injects: (a) structured session summary, (b) last 3 recent interactions, (c) only the top-5 most relevant memories to THIS specific query.

**What:**
- `memory/context_builder.py` — new module that takes `(namespace, query, max_tokens)` and returns optimally packed context:
  1. Namespace summary (1 paragraph, cached 5 min)
  2. 3 most recent interactions from `agent_runs` for this namespace
  3. Top-5 retrieved memories most semantically similar to the current query
  4. Total context budget capped at `max_tokens` (default 2000)
- Replaces the current `get_agent_context()` call in `executor.py`
- Token savings: estimated 40% reduction in context tokens per call

**Files changed:** New `memory/context_builder.py`, `memory/engine.py`, `agents/executor.py`

### 11.4 — Contextual Memory Prefixing (Anthropic's Contextual Retrieval)
**Why:** Anthropic published research showing that adding a generated context summary to each memory chunk *before* embedding it reduces retrieval failure by 49%. Your memories are currently embedded as raw text. Prefixing them with context ("This fact was recorded during client onboarding for the RECI namespace on 2025-03-12 about contract terms...") dramatically improves semantic search quality.

**What:**
- On memory write, generate a 1–2 sentence context prefix using Haiku (async, non-blocking)
- Store prefix in new `context_prefix` column on `memories` table (migration 015)
- ChromaDB upsert uses `prefix + text` for embedding but stores only `text` for display
- Backfill job for existing memories (one-time script)

**Files changed:** `memory/store.py`, `memory/vector_store.py`, migration 015, new `scripts/backfill_memory_context.py`

---

## Phase 12: Event-Driven Workflows & Agent Protocol
**Theme:** Make ClaudeOS react to the world, not just run on schedules. Make agents composable.  
**Effort:** Medium (2–3 days) | **Impact:** Medium-High — unlocks new automation scenarios.

### 12.1 — Webhook-Triggered Workflow Activation
**Why:** Every modern automation platform (n8n, Zapier, Make) triggers on events, not just cron. Your workflows can only run on a schedule or manual trigger. Adding webhook activation means external systems (GitHub, Stripe, your client apps, Supabase) can trigger ClaudeOS workflows — turning it into a true automation hub.

**What:**
- New Flask route: `POST /api/v1/workflows/webhook/<workflow_name>` — receives JSON payload, validates API key, fires named workflow with payload injected as context
- Unique webhook URLs per workflow, stored in `workflows` table (`webhook_secret` column)
- Dashboard: workflow detail page shows webhook URL + secret (copy button)
- Example use cases: GitHub push → analysis workflow, new Stripe payment → client-report workflow, Supabase row insert → briefing workflow

**Files changed:** `core/api/routes/workflows.py`, `workflows/pipeline.py`, migration 016, `dashboard/_pages/_workflows.py`

### 12.2 — MCP Tool Server for ClaudeOS Agents
**Why:** MCP (Model Context Protocol) is the 2025 standard for AI tool interoperability. Anthropic, OpenAI, Google, Cursor, and VS Code all support it. Exposing your 12 agents as MCP tools means any MCP-compatible AI (Claude Desktop, Cursor, custom apps) can call them directly — your ClaudeOS becomes a tool platform, not just a dashboard.

**What:**
- New `mcp/server.py` — Python MCP server using `mcp` SDK (`pip install mcp`)
- Exposes each enabled agent as an MCP Tool: `{name, description, inputSchema}`
- Memory search exposed as an MCP Resource
- Runs on its own port (default 5100) via stdio or HTTP transport
- New `scripts/start_mcp.ps1` — starts MCP server alongside Flask + Streamlit

**Files changed:** New `mcp/` directory, `mcp/server.py`, `mcp/tools.py`, `scripts/start_mcp.ps1`, `scripts/start.ps1`

### 12.3 — A2A Agent Cards
**Why:** Google's Agent-to-Agent protocol is gaining traction. Publishing `/.well-known/agent.json` Agent Cards for each agent means external orchestrators can discover and delegate to your agents automatically. This future-proofs ClaudeOS for the multi-agent internet forming in 2025.

**What:**
- Flask route: `GET /api/v1/agents/<name>/.well-known/agent.json` — returns A2A-spec Agent Card
- Card includes: name, description, capabilities, input/output schema, auth requirements, endpoint URL
- New `agents/registry.py` method: `to_agent_card(agent)` — maps YAML definition to A2A schema
- No external dependencies — pure JSON generation

**Files changed:** `core/api/routes/agents.py`, `agents/registry.py`

---

## Phase 13: Multimodal Input & Smart Dashboard
**Theme:** Modernize the interaction layer — voice, images, live data.  
**Effort:** Medium (2–3 days) | **Impact:** High — dramatically changes how you interact with ClaudeOS.

### 13.1 — Voice Input for Agent Chat
**Why:** Every serious AI assistant in 2025 accepts voice. Whisper (OpenAI, free, runs locally) gives you accurate STT. Streamlit 1.31+ has `st.audio_input`. The pipeline: record → Whisper transcribe → send to agent. No ongoing API cost (Whisper runs locally on CPU).

**What:**
- Add `openai-whisper` package (local inference, no API key required) or `faster-whisper` (4× faster)
- Agent chat page: add `st.audio_input("Speak your request")` button
- On audio submit: transcribe with Whisper, populate prompt field, auto-submit
- Text-to-speech for responses (optional): use `gTTS` or `pyttsx3` (both free, local)

**Files changed:** `dashboard/_pages/_agents.py`, `requirements.txt`

### 13.2 — Image / Screenshot Analysis in Agent Chat
**Why:** Claude Sonnet natively accepts images. Your agent chat currently accepts text only. Enabling image upload lets you: drop a screenshot of an error into the QA agent, upload a spreadsheet screenshot to the analysis agent, share a client document photo to memory-curator. This is a standard capability in every modern AI assistant.

**What:**
- Add `st.file_uploader(type=["png","jpg","jpeg","pdf"])` to agent chat page
- Uploaded image → base64 encode → inject into Claude API call as `image` content block
- PDF: extract page as image using `pdf2image` library, send first N pages
- Agents YAML gets optional `multimodal: true` flag — only multimodal-enabled agents show the upload

**Files changed:** `dashboard/_pages/_agents.py`, `agents/executor.py`, `requirements.txt`

### 13.3 — Live Overview Dashboard (Real-Time Metrics)
**Why:** The current overview page does a batch API fetch on load and shows static numbers. Production AI dashboards (like LangSmith, Arize) show live activity — agents running now, token burn rate, last 5 events with timestamps, error rate trend. Streamlit's `st.empty()` + `time.sleep(2)` polling loop gives you a live dashboard with zero external dependencies.

**What:**
- Overview page refactored with `st.empty()` live update loop (2-second refresh)
- New "Live Activity Feed" panel: last 10 agent runs with status, model, tokens, duration — updates in real-time
- Token burn rate chart: rolling 1-hour window, updates live (Plotly chart in st.empty)
- "Agents Running Now" counter with spinning indicator
- Error alert strip: if any run in last 5 min has status=error → red banner with details
- New Flask endpoint `GET /api/v1/overview/live` — returns compact JSON optimized for polling

**Files changed:** `dashboard/_pages/_overview.py`, `core/api/routes/` (new `overview.py`), new `dashboard/components/live_feed.py`

### 13.4 — Agent Chat History & Multi-Turn Conversations
**Why:** Currently each agent dispatch is stateless — the agent has no memory of what you said 5 minutes ago in the same session. Every production AI assistant maintains conversation history. This makes your agents dramatically more useful for iterative work (refining a document, multi-step analysis, debugging a workflow).

**What:**
- `st.session_state["chat_history"][agent_name]` — per-agent conversation list
- Agent chat page renders full chat history with `st.chat_message` bubbles
- `executor.py` accepts optional `messages` list (prior turns) — passes as multi-turn Claude API call
- Conversation stored in `agent_conversations` table (new): session_id, agent_name, turn, role, content, tokens
- Dashboard: conversation history browser (filter by agent, date, namespace)
- Migration 017: `agent_conversations` table

**Files changed:** `dashboard/_pages/_agents.py`, `agents/executor.py`, migration 017, new `dashboard/components/chat_ui.py`

---

## Implementation Order & Checkpoints

```
Phase 10 (Real-Time Intelligence)
  10.1 SSE Streaming          ← Start here. Biggest visible UX win.
  10.2 Langfuse Observability ← Parallel or after 10.1.
  10.3 LLM-as-Judge Scoring   ← After 10.2 (uses same trace IDs).

Phase 11 (Advanced Memory)
  11.3 Tiered Context         ← Quick win. Touch only executor.py.
  11.2 Hybrid BM25+Vector     ← Standalone retriever module.
  11.4 Contextual Prefixing   ← After 11.2 (shares retriever logic).
  11.1 Consolidation Engine   ← Last — needs stable retriever first.

Phase 12 (Event-Driven + Protocol)
  12.1 Webhook Triggers       ← Most immediate utility.
  12.2 MCP Server             ← Opens external integrations.
  12.3 A2A Agent Cards        ← Lightest lift, pure JSON generation.

Phase 13 (Multimodal + Dashboard)
  13.4 Multi-Turn Chat        ← Biggest daily-use improvement.
  13.2 Image Analysis         ← Native Claude capability, low effort.
  13.1 Voice Input            ← After 13.4 (shares chat UI).
  13.3 Live Dashboard         ← Polish. After all agents improved.
```

---

## Risk & Dependency Notes

| Risk | Mitigation |
|------|-----------|
| Langfuse requires Docker or cloud account | Can run hosted free tier; no self-host needed initially |
| Whisper model (~140MB) needs one-time download | Download on first use, cache locally in `data/models/` |
| SSE streaming breaks existing polling clients | New endpoint `/agents/stream` is additive, old endpoint unchanged |
| Memory consolidation may lose nuance | Archive originals (not delete), consolidation is reversible |
| BM25 index needs rebuild on all existing memories | One-time script `scripts/build_bm25_index.py`, runs in <5 min |
| MCP server adds port 5100 conflict risk | Port configurable via `.env` `MCP_PORT=5100` |

---

## Summary: What You'll Have After All 4 Phases

- **Real-time streaming AI** — responses start appearing in <1s, not after 20s
- **Full observability** — trace every call, see latency, cost, quality trends per agent
- **Self-improving quality** — every output scored, quality regressions auto-detected
- **Intelligent memory** — memory that consolidates itself, retrieves with precision, costs 40% fewer tokens
- **Event-driven automation** — any external system can trigger your workflows via webhook
- **Universal tool platform** — your agents callable from Claude Desktop, Cursor, any MCP client
- **Voice + vision** — speak to agents, drop screenshots, get multimodal analysis
- **Conversational agents** — multi-turn sessions, full chat history, persistent context

This puts ClaudeOS in the same capability class as LangSmith + Mem0 + n8n + Claude Desktop — all in one self-hosted system you control.

---

**AWAITING YOUR APPROVAL TO PROCEED.**  
Reply with "go ahead" or specify which phases to start with.
