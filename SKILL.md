# ClaudeOS Build Skill
**File:** `SKILL.md`  
**Invoke as:** `/claudeos` (copy this file to `~/.claude/skills/claudeos.md`)  
**Purpose:** Reproduce the complete ClaudeOS AI Operating System for any new client from scratch — A to Z — with their name and brand applied throughout. Every feature, every phase, every file.

---

## How to Use This Skill

1. Copy this file to your Claude Code skills directory:
   ```powershell
   Copy-Item SKILL.md "$env:USERPROFILE\.claude\skills\claudeos.md"
   ```
2. In any new project directory, invoke with:
   ```
   /claudeos
   ```
3. Claude will ask you 3 questions, then build the entire system.

---

## Skill Instructions (what Claude does when invoked)

When this skill is invoked, execute the following steps exactly.

---

### STEP 0 — Collect Client Information

Ask the user these questions **one by one**. Wait for each answer before proceeding.

**Question 1 (required):**
> "What is the name of the client or business this system is being built for?  
> (Example: Acme Corp, Lagos Motors, BrightPath Finance)"

**Question 2 (optional — press Enter to skip):**
> "What are the brand colors?  
> Provide as hex codes: Primary, Secondary, Accent  
> (Example: #2563EB, #FFFFFF, #3B82F6)  
> Skip to use ClaudeOS defaults: #407E3C green, #FFFFFF white, #5a9e56 accent)"

**Question 3 (optional — press Enter to skip):**
> "Describe the client's business in one sentence.  
> This is injected into agent system prompts as context.  
> (Example: 'Lagos Motors is a vehicle logistics company operating across Nigeria.')"

After collecting answers, confirm:
> "Building [CLIENT_NAME] AI Operating System with [colors] brand. Proceeding..."

Then execute all steps below without further interruption.

---

### STEP 1 — Derive Variables

From the answers, derive these variables used throughout the build:

```
CLIENT_NAME       = answer to Q1  (e.g. "Acme Corp")
CLIENT_SLUG       = lowercase, hyphens  (e.g. "acme-corp")
CLIENT_NAMESPACE  = CLIENT_SLUG  (e.g. "acme-corp")
CLIENT_ADMIN_USER = first word of CLIENT_NAME, lowercase  (e.g. "acme")

BRAND_PRIMARY     = Q2 primary color OR "#407E3C"
BRAND_SECONDARY   = Q2 secondary color OR "#FFFFFF"
BRAND_ACCENT      = Q2 accent color OR "#5a9e56"
BRAND_DARK        = darken BRAND_PRIMARY by ~20%  (e.g. "#2d5a29" for green)

CLIENT_DESC       = Q3 answer OR "An AI-powered business platform."

SECRET_KEY        = generate random 48-char hex string
ADMIN_PASSWORD    = "Admin123!" + first 4 chars of CLIENT_SLUG (e.g. "Admin123!acme")
```

---

### STEP 2 — Scaffold Directory Structure

Create the following directory structure in the current working directory:

```
[CLIENT_SLUG]/
├── agents/
│   ├── definitions/          ← 12 YAML agent definitions
│   ├── __init__.py
│   ├── dispatcher.py
│   ├── evaluator.py
│   ├── executor.py
│   ├── registry.py
│   └── schemas.py
├── core/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── admin_routes.py
│   │   │   ├── agents.py
│   │   │   ├── auth_routes.py
│   │   │   ├── memory.py
│   │   │   ├── outputs.py
│   │   │   ├── projects.py
│   │   │   ├── sync.py
│   │   │   ├── system.py       ← /system/status, /system/stats, /system/namespace-stats
│   │   │   ├── tickets.py
│   │   │   └── workflows.py
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── limiter.py          ← flask-limiter rate limit config
│   │   └── middleware.py
│   ├── __init__.py
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── notifications.py        ← email engine: smtplib, fire-and-forget, branded HTML templates
│   └── utils.py
├── dashboard/
│   ├── _pages/
│   │   ├── _admin.py
│   │   ├── _agents.py
│   │   ├── _memory.py
│   │   ├── _observability.py
│   │   ├── _outputs.py
│   │   ├── _overview.py
│   │   ├── _projects.py
│   │   ├── _settings.py
│   │   ├── _tickets.py
│   │   ├── _usage.py           ← Client Usage Dashboard (client/viewer only — Pulse Score, KPI grid)
│   │   └── _workflows.py
│   ├── components/
│   │   ├── brand.py
│   │   ├── login_form.py
│   │   └── onboarding.py       ← first-login tour, persists via onboarding_done DB column
│   ├── __init__.py
│   └── app.py
├── data/                     ← created at runtime, not committed
├── logs/                     ← created at runtime
├── mcp/
│   ├── __init__.py
│   └── server.py
├── memory/
│   ├── db/
│   │   └── migrations/
│   │       ├── 001_initial.sql … 017_agent_conversations.sql
│   ├── __init__.py
│   ├── consolidator.py
│   ├── context_builder.py
│   ├── engine.py
│   ├── retriever.py
│   ├── schemas.py
│   ├── store.py
│   └── vector_store.py
├── notifications/
│   ├── __init__.py
│   └── reminder_job.py
├── outputs/
│   ├── store/
│   ├── __init__.py
│   └── manager.py
├── docs/
│   ├── FaiykeOS_Handbook_faiyke-ai.pdf   ← full client handbook (20 sections)
│   ├── PRODUCT_README.md                 ← buyer-facing package overview
│   ├── SETUP_GUIDE_NONTECHNICAL.md       ← 10-part setup guide for non-technical buyers
│   ├── AGENCY_LICENSE.md                 ← agency/reseller license terms
│   └── landing/
│       ├── index.html                    ← marketing landing page
│       └── pricing.html                  ← pricing + booking form
├── scripts/
│   ├── create_admin.py
│   ├── migrate.py
│   ├── seed_agents.py
│   ├── seed_client_schema.py   ← pre-populate 14 onboarding fields per namespace
│   ├── seed_namespaces.py
│   ├── seed_workflows.py
│   ├── build_package.py        ← builds dist/FaiykeOS-v17.2.1.zip for distribution
│   ├── gen_handbook_pdf.py     ← regenerates FaiykeOS_Handbook_faiyke-ai.pdf
│   ├── serve_api.py
│   ├── start.ps1
│   ├── stop.ps1
│   └── start_mcp.ps1
├── sync/
│   ├── __init__.py
│   ├── engine.py
│   ├── schemas.py
│   └── supabase_schema.sql
├── tests/
│   ├── test_agents.py
│   ├── test_memory.py
│   └── test_phase1.py
├── vault/
│   ├── __init__.py
│   └── manager.py
├── workflows/
│   ├── definitions/          ← 7 YAML workflow definitions
│   ├── __init__.py
│   ├── pipeline.py
│   ├── registry.py
│   ├── scheduler.py
│   └── schemas.py
├── .env
├── .env.example
├── .gitignore
├── CLAUDE.md
├── README.md
├── requirements.txt
└── SKILL.md                  ← copy of this file
```

**Implementation:** Copy all source files from the ClaudeOS reference implementation at `C:\Users\rigwe\Desktop\ClaudeOS\`. After copying, apply brand substitution in Step 3.

If the reference implementation is not available (building on a new machine), implement each file from scratch using the specifications in this document.

---

### STEP 3 — Apply Brand Throughout

After scaffolding, perform these exact substitutions. Use find-and-replace across all files.

#### In `dashboard/components/brand.py`:

Replace:
```python
PRIMARY       = "#407E3C"
ACCENT        = "#5a9e56"
PRIMARY_LIGHT = "#5a9e56"
PRIMARY_LT    = "#5a9e56"
PRIMARY_DK    = "#2d5a29"
WHITE         = "#FFFFFF"
```
With:
```python
PRIMARY       = "BRAND_PRIMARY"
ACCENT        = "BRAND_ACCENT"
PRIMARY_LIGHT = "BRAND_ACCENT"
PRIMARY_LT    = "BRAND_ACCENT"
PRIMARY_DK    = "BRAND_DARK"
WHITE         = "BRAND_SECONDARY"
```

Replace all 3 occurrences of `"#407E3C"` in the THEMES dict with `BRAND_PRIMARY`.
Replace all occurrences of `"#5a9e56"` in the THEMES dict with `BRAND_ACCENT`.
Replace `"#2d5a29"` with `BRAND_DARK`.

#### In `dashboard/app.py`:

Replace the page title and icon:
```python
page_title="ClaudeOS",
page_icon="🖥️",
```
With:
```python
page_title="CLIENT_NAME OS",
page_icon="🤖",
```

#### In `dashboard/_pages/_overview.py`:

Replace in `aurora_hero()` call:
```python
title="ClaudeOS",
subtitle="AI Operating System — coordination layer for all agents, memory, and workflows.",
```
With:
```python
title="CLIENT_NAME",
subtitle="CLIENT_DESC",
```

#### In `CLAUDE.md`:

Replace:
```
ClaudeOS — AI Operating System
Brand: #407E3C green + white
```
With:
```
CLIENT_NAME OS — AI Operating System
Brand: BRAND_PRIMARY · BRAND_SECONDARY · BRAND_ACCENT
```

#### In `README.md`:

Replace all occurrences of `ClaudeOS` in headings and descriptions with `CLIENT_NAME OS`.
Replace badge color `407E3C` with the hex of BRAND_PRIMARY (without `#`).

#### In all agent YAML definitions (`agents/definitions/*.yaml`):

In each agent's `system_prompt` field, prepend:
```
You are an AI agent operating within the CLIENT_NAME AI Operating System.
Business context: CLIENT_DESC
```

---

### STEP 4 — Configure .env

Create `.env` with:

```env
# CLIENT_NAME OS — Environment Configuration
# Generated by ClaudeOS Build Skill

ANTHROPIC_API_KEY=REPLACE_WITH_YOUR_KEY
CLAUDEOS_SECRET_KEY=SECRET_KEY
CLAUDEOS_ENV=development
CLAUDEOS_VERSION=1.0.0

SQLITE_PATH=data/claudeos.db
CHROMADB_PATH=data/chromadb

FLASK_PORT=5000
FLASK_DEBUG=false
ALLOWED_ORIGINS=http://localhost:8501

STREAMLIT_PORT=8501

# Cloud Sync (optional — fill in to activate)
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# MCP Server (optional)
MCP_PORT=5100

# Email notifications (optional)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
NOTIFY_EMAIL=

LOG_LEVEL=INFO
LOG_PATH=logs
```

Also create `.env.example` — same content but with all secrets as placeholder strings.

---

### STEP 5 — Configure .gitignore

Create `.gitignore`:

```gitignore
# Environment
.env
*.env

# Database & vector store
data/
*.db
*.db-journal

# Vault workspace files
vault/workspaces/

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/

# Logs
logs/
*.log

# Output files
outputs/store/

# Test artifacts
.pytest_cache/
htmlcov/
.coverage

# OS
.DS_Store
Thumbs.db
```

---

### STEP 6 — Create requirements.txt

```
# CLIENT_NAME OS Requirements

# Core
flask==3.0.3
flask-cors==4.0.1
flask-limiter==3.7.0

# AI
anthropic>=0.40.0

# Dashboard
streamlit==1.38.0

# Memory / Vector
chromadb==0.5.5
sentence-transformers==3.1.1

# Hybrid RAG
rank-bm25==0.2.2

# Scheduler
apscheduler==3.10.4

# Data / Validation
pydantic==2.8.2
pydantic-settings==2.4.0
python-dotenv==1.0.1

# WSGI (Windows-compatible)
waitress==3.0.0

# Cloud sync (optional)
supabase==2.7.4

# Output export
markdown2==2.5.0
pdfkit==1.0.0

# Auth
PyJWT>=2.10.1,<3.0.0
bcrypt==4.2.0

# Charts
plotly>=5.18.0

# Optional: voice input
# openai-whisper>=20231117

# Optional: MCP tool server
# mcp>=1.0.0
# uvicorn>=0.30.0

# Dev / testing
pytest==8.3.3
pytest-cov==5.0.0
httpx==0.27.2
```

---

### STEP 7 — Seed Agent YAML Definitions

Create these 12 agent YAML files in `agents/definitions/`. All have `CLIENT_NAME` and `CLIENT_DESC` already injected into system prompts (from Step 3). These are the same agents as the reference ClaudeOS implementation:

1. `meta-agent.yaml` — Orchestrator. Decomposes complex goals into agent chains.
2. `research-agent.yaml` — Deep research with synthesis and source validation.
3. `briefing-agent.yaml` — Daily briefings and market intelligence.
4. `analysis-agent.yaml` — Data analysis and metrics interpretation.
5. `writing-agent.yaml` — Content creation, editing, and refinement.
6. `comms-agent.yaml` — Internal communications and notifications.
7. `memory-curator-agent.yaml` — Memory management and context curation.
8. `client-manager-agent.yaml` — Client-specific data and context.
9. `qa-agent.yaml` — Quality assurance and content review.
10. `scheduling-agent.yaml` — Calendar and task scheduling coordination.
11. `workflow-builder-agent.yaml` — Generate new workflows from natural language.
12. `domain-agent.yaml` — Domain-specific operations (replaces transport-ops-agent; namespace unlocked for new client use).

**YAML structure** (use this template for each agent):
```yaml
name: [agent-name]
display_name: [Display Name]
description: [One-line description]
category: [ops|research|content|analysis|comms|system|engineering|domain]
system_prompt: |
  You are an AI agent operating within the CLIENT_NAME AI Operating System.
  Business context: CLIENT_DESC

  [Agent-specific instructions here]
model: claude-sonnet-4-6
max_tokens: 4096
temperature: 0.7
tools: []
namespace_lock: null
tags: [tag1, tag2]
enabled: true
version: "1.0.0"
```

---

### STEP 8 — Seed Workflow YAML Definitions

Create these 7 workflow YAML files in `workflows/definitions/`:

1. `01-morning-briefing.yaml` — Daily morning briefing (Mon–Fri 7:00 WAT)
2. `02-memory-curation.yaml` — Weekly memory cleanup (Sunday midnight)
3. `03-research-digest.yaml` — Weekly research summary
4. `04-client-report.yaml` — Weekly client reports (Friday 17:00 WAT)
5. `05-analysis-run.yaml` — Scheduled analytics
6. `06-qa-sweep.yaml` — Quality checks (Mon–Fri 6:00 WAT)
7. `07-meta-orchestrate.yaml` — Manual meta-orchestration (3 steps: plan → research → summary)

Update namespace in all workflow definitions from `global` to `CLIENT_NAMESPACE` where appropriate.

---

### STEP 9 — Install Dependencies & Run Migrations

```powershell
Set-Location CLIENT_SLUG
pip install -r requirements.txt
python scripts/migrate.py
python scripts/seed_agents.py
python scripts/seed_workflows.py
python scripts/seed_namespaces.py
python scripts/seed_client_schema.py --namespace CLIENT_NAMESPACE
```

For `seed_namespaces.py`, create the `CLIENT_NAMESPACE` namespace in addition to the standard `global` namespace. The client namespace should be the primary workspace.

`seed_client_schema.py` pre-populates 14 standard onboarding fields (business name, industry, primary goals, brand tone, SLA tier, contact name, contact email, timezone, preferred language, custom instructions, etc.) as blank placeholder memory entries. Agents read these automatically via memory context. Skips any key that already exists — safe to run multiple times.

---

### STEP 10 — Create Admin User

```powershell
python scripts/create_admin.py --username CLIENT_ADMIN_USER --password ADMIN_PASSWORD
```

Print the credentials clearly so the user can record them:
```
====================================
  CLIENT_NAME OS — Admin Credentials
====================================
  Dashboard: http://localhost:8501
  API:       http://localhost:5000/api/v1/health
  Username:  CLIENT_ADMIN_USER
  Password:  ADMIN_PASSWORD
  
  IMPORTANT: Change this password after first login.
  The admin will be prompted automatically on next login.
====================================
```

---

### STEP 11 — Start the System

```powershell
.\scripts\start.ps1
```

Verify both services are responding:
```powershell
# Check Flask
Invoke-RestMethod http://localhost:5000/api/v1/health

# Check Streamlit
Invoke-WebRequest http://localhost:8501/healthz -UseBasicParsing
```

If both respond, print:
```
====================================
  CLIENT_NAME OS is LIVE
====================================
  Dashboard:  http://localhost:8501
  API:        http://localhost:5000/api/v1/health
  
  Login with the admin credentials above.
  
  OPTIONAL next steps:
  - Add ANTHROPIC_API_KEY to .env and restart
  - Run .\scripts\start_mcp.ps1 for MCP tool server
  - Add Supabase credentials to .env for cloud sync
  - pip install openai-whisper for voice input
====================================
```

---

### STEP 12 — Generate Client CLAUDE.md

Create a `CLAUDE.md` in the project root with the full ClaudeOS project rules (as in the reference implementation), but with all instances of `ClaudeOS` replaced by `CLIENT_NAME OS`, and the brand colors updated to match the client's brand.

---

### STEP 13 — Commit Initial State

```powershell
git init
git add .
git commit -m "init: CLIENT_NAME OS — FaiykeOS v17.0 base build"
```

---

## What Gets Built (Complete Feature List)

Every deployment built by this skill includes all of the following. Nothing is cut down or simplified.

### Layers 0-9 (Core System)
| Layer | Feature |
|-------|---------|
| 0 | Streamlit dashboard — 10 pages, branded, dark/light theme |
| 1 | Flask REST API — 40+ endpoints, JWT + API key auth |
| 2 | Memory Engine — SQLite FTS5 + ChromaDB vector store |
| 3 | Agent Registry — 12 agents, YAML definitions, enable/disable |
| 4 | Workflow Engine — 7 pipelines, APScheduler, cron + manual |
| 5 | Client Vault — namespace isolation, per-client workspaces |
| 6 | Output Manager — auto-tag, full-text search, Markdown/PDF export |
| 7 | Supabase Cloud Sync — push-only, watermark, 15-min auto |
| 8 | Auth & Security — JWT/bcrypt, 5 roles, lockout, audit log |
| 9 | Ticketing System — SLA tiers P1–P4, staff role, bulk ops |

### Layers 10-13 (Intelligence Layer)
| Layer | Feature |
|-------|---------|
| 10 | Real-Time Intelligence: SSE streaming, LLM-as-Judge eval, Observability (5 tabs: Quality/Latency/Tokens/Memory Health/Namespace Usage) |
| 11 | Advanced Memory: hybrid BM25+vector RAG, tiered context, consolidation engine |
| 12 | Protocols: MCP Tool Server, A2A Agent Cards, webhook triggers |
| 13 | Multimodal: multi-turn chat, image analysis, voice input (resets on Clear Conversation), live dashboard, onboarding tour (DB-persisted, migration 018), Client Onboarding tab in Admin (14-field schema seed) |

### Layer 14 (Commercial Upgrade)
| Feature | Details |
|---------|---------|
| Security hardening | CORS ALLOWED_ORIGINS env var (not wildcard), security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection), rate limiting via flask-limiter |
| Rate limits | Agent /run: 30/min, /stream: 20/min, workflow /trigger: 10/min, workflow /run: 20/min |
| Namespace white-labeling | Per-namespace color, accent, company_name, icon stored in metadata; sidebar logo + aurora_hero() pill show client branding |
| Client Usage Dashboard | `_usage.py`: Namespace Pulse Score gauge (0–100), KPI grid (runs/tokens/cost/quality/outputs), activity feed, memory summary. Visible to client/viewer only |
| Namespace Pulse Score | Composite 0–100 = quality×40% + ticket_resolve×30% + memory_fresh×20% + workflow_ok×10% |
| Email notifications | `core/notifications.py`: stdlib smtplib, fire-and-forget thread pool, branded HTML; ticket assignment + completion/closure events |
| Admin Branding tab | 7th tab in Admin Panel: per-namespace color picker, accent, company name, live preview |
| Agent hallucination guard | analysis/briefing/research/writing agents ask clarifying questions; refuse to fill data gaps or fabricate findings |
| Output delete compat | SELECT-then-DELETE replaces RETURNING clause (supports SQLite < 3.35) |
| Output timestamps | YYYY-MM-DD HH:MM shown in all output views |
| Activity feed names | dispatcher.list_runs JOINs agents table; human-readable names always shown (agent_name > display_name > id[:12]) |
| Performance | Agents page uses api_get_cached for /namespaces (30s TTL); context_builder wrapped in 4s timeout in executor |

### Layer 15 (Commercial Package)
| Feature | Details |
|---------|---------|
| Product name | **FaiykeOS** — commercial brand name; internal codebase retains ClaudeOS |
| Handbook | `docs/FaiykeOS_Handbook_faiyke-ai.pdf` — 20-section client handbook, regenerated via `python scripts/gen_handbook_pdf.py` |
| Landing page | `docs/landing/index.html` — standalone HTML marketing page; hero, features, personas, pricing preview, FAQ |
| Pricing page | `docs/landing/pricing.html` — 3-tier cards, comparison table, Formspree booking form; replace `YOUR_FORM_ID` with real Formspree endpoint |
| Pricing tiers | Developer $197 one-time \| Business $997 + $147/mo \| Agency $497 + $97/mo or $997 flat unlimited |
| Buyer collateral | `docs/PRODUCT_README.md`, `docs/SETUP_GUIDE_NONTECHNICAL.md`, `docs/AGENCY_LICENSE.md` |
| Distribution ZIP | `scripts/build_package.py` → `dist/FaiykeOS-v17.2.1.zip` (475 KB, 153 files); excludes .env, data/, logs/, dev scripts |
| Replacements needed | Update `hello@faiyke-ai.com` email + Formspree form ID in landing/pricing HTML before distributing |

### Authentication & Roles
| Role | Access |
|------|--------|
| admin | Full access — all namespaces, user management, admin panel |
| operator | All namespaces, all resources, no user management |
| client | Own namespace only — memory R/W, run agents, view outputs |
| viewer | Own namespace, read-only |
| staff | Assigned tickets only — can self-assign and advance status |

### Dashboard Pages
- Overview — live activity feed, KPIs, quick dispatch, eval score pills, auto-refresh toggle, error/running alerts
- Agents — 3-tab UI: Chat (streaming, images, voice, multi-turn, clear conversation resets voice widget), Catalog, Run History
- Memory — FTS search, semantic search, hybrid BM25+vector, write/edit/delete, bulk ops
- Workflows — manage, trigger, schedule, webhook setup
- Projects — client vault, namespaces, project management, context file upload
- Outputs — search, view, export (Markdown/PDF), bulk delete (timestamps shown as YYYY-MM-DD HH:MM)
- Tickets — create, assign, comment (lazy-loaded), SLA tracking, bulk ops (email notification on assign/complete)
- Observability — 5 tabs: Quality Scores, Latency (p50/p95/p99), Token Cost, Memory Health, Namespace Usage (admin/operator only)
- Settings — env config, sync controls (Supabase), email notification config + test send; Sync Log with per-row 🗑 delete and bulk-select delete (st.data_editor checkboxes + "Delete Selected (N)" button)
- Admin Panel — 7 tabs: Users, API Keys, Audit Log, Sessions, Security config, Client Onboarding (14-field schema seed), Branding
  - Users tab 5-column action bar: Unlock/Status | Deactivate/Reactivate | Reset Password | ✏️ Edit | 🗑 Delete
  - Edit User: `@st.dialog` modal — change role, namespace, email, active status, force-pw-change flag
  - Delete User: `@st.dialog` permanent-delete confirmation — hard-deletes user + sessions + auth events; last-admin guard
  - Context-aware unlock: Unlock button only shown when user is actually locked
  - Branding tab: per-namespace color picker, accent color, company name, icon, live preview
- Usage — client/viewer only: Namespace Pulse Score (0–100 composite gauge), KPI grid (runs/tokens/cost/quality/outputs), activity feed, memory summary

### API Endpoints (Key)
| Endpoint | Description |
|----------|-------------|
| `POST /auth/login` | JWT login |
| `GET /agents` | List agents |
| `POST /agents/<name>/run` | Run agent |
| `GET /agents/<name>/stream` | SSE streaming response (token-by-token, bytes generator, direct_passthrough=True) |
| `GET /agents/<name>/.well-known/agent.json` | A2A Agent Card |
| `GET /agents/<name>/conversations` | List multi-turn conversation sessions |
| `POST /agents/runs/<id>/cancel` | Cancel a pending/running run |
| `GET /memory` | List memory |
| `POST /memory` | Write memory |
| `GET /memory/hybrid-search` | Hybrid BM25+vector search |
| `POST /memory/consolidate` | Trigger consolidation |
| `GET /workflows` | List workflows |
| `POST /workflows/<name>/run` | Run workflow |
| `POST /workflows/<name>/trigger` | Webhook trigger |
| `POST /workflows/<name>/webhook/enable` | Enable webhook |
| `GET /tickets` | List tickets |
| `POST /tickets` | Create ticket |
| `GET /system/status` | System health |
| `GET /health` | Public health check |
| `DELETE /admin/users/<user_id>/permanent` | Hard-delete user + sessions + auth events (admin only; last-admin guard) |
| `PATCH /admin/users/<user_id>` | Update user fields: role, namespace, email, is_active, must_change_password |
| `GET /system/namespace-stats` | Namespace Pulse Score + usage metrics (tokens, cost, runs, quality, memory, tickets, workflows) |
| `DELETE /sync/log/<id>` | Delete single sync log entry |
| `DELETE /sync/log` | Bulk delete sync log entries — body: `{"ids": [...]}`, max 200 |

### Migrations (020 total)
| Migration | Content |
|-----------|---------|
| 001 | Initial schema (memory, agents, workflows, outputs) |
| 002 | Sync state |
| 003–005 | Performance indexes |
| 006 | Auth users, sessions, events |
| 007 | must_change_password flag |
| 008 | More performance indexes |
| 009 | Ticketing tables |
| 010–012 | More performance indexes |
| 013 | Dashboard sessions |
| 014 | Agent eval scores (eval_score, eval_dimensions, eval_at) |
| 015 | Memory upgrades (context_prefix, is_consolidated, archived) |
| 016 | Webhook triggers on workflows |
| 017 | Agent conversations + turns (multi-turn chat) |
| 018 | onboarding_done column on users table (first-login tour persists across logout/re-login) |
| 019 | 15 high-traffic DB indexes (performance) |
| 020 | Soft-delete: deleted_at column on agent_runs + outputs; hard-delete replaced with soft-delete everywhere |

---

## What Is NOT Included (Client Must Provide)

| Item | Notes |
|------|-------|
| `ANTHROPIC_API_KEY` | Required to run agents — client provides from console.anthropic.com |
| Brand colors | Asked in Step 0 — defaults to ClaudeOS green if skipped |
| Client business description | Asked in Step 0 — used in agent prompts |
| Supabase credentials | Optional — for cloud sync only |
| Custom agent YAML content | 12 default agents provided; client can customize system prompts |
| Custom workflow YAML content | 7 default workflows provided; client can add more |
| SMTP credentials | Optional — for email notifications |
| Domain/SSL | Optional — for production deployment beyond localhost |

---

## Optional Extras (Ask After Build)

After the system is running, offer these optional additions:

1. **Custom agents** — "Would you like me to create agents specific to [CLIENT_NAME]'s business?"
2. **Custom workflows** — "Would you like scheduled workflows tailored to your operations?"
3. **Seed initial memory** — "Shall I pre-populate memory with facts about [CLIENT_NAME]?"
4. **MCP server** — "Would you like the MCP Tool Server started? (lets Claude Desktop call your agents)"
5. **Supabase cloud sync** — "Do you have Supabase credentials for cloud backup?"
6. **Commercial package** — "Would you like me to generate the buyer-facing handbook PDF and distribution ZIP for this deployment?" → run `python scripts/gen_handbook_pdf.py` then `python scripts/build_package.py`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `CLAUDEOS_SECRET_KEY` error on startup | Check .env — key must be ≥32 chars and not a placeholder |
| Migrations fail | Run `python scripts/migrate.py` manually; check data/ directory exists |
| Agents not found | Run `python scripts/seed_agents.py` |
| ChromaDB warmup slow (30-60s) | Normal on first start — sentence-transformers model loading |
| Eval scores not appearing | Async — wait ~10s; check ANTHROPIC_API_KEY in .env |
| Streaming returns 500 | Flask is running but Connection hop-by-hop header rejected by waitress. Fix: `stream_agent` route must use `direct_passthrough=True` on the `Response` object and yield `bytes` (not strings) from the generator — this bypasses Werkzeug's automatic `Connection` header injection (PEP 3333) |
| Streaming not working in browser | Ensure only one Flask process on port 5000 (`netstat -ano \| findstr :5000`); kill duplicates and restart |
| Runs stuck as "running" | Old server crashed mid-stream. Fix: `UPDATE agent_runs SET status='failed', completed_at=NOW() WHERE status='running'` |
| Runs not appearing in history | Streaming runs only appear in history if `create_run_record()` is called in the stream route before the generator starts — not inside the generator |
| Images not received by agent | SSE stream endpoint must forward images through the generator. Verify `stream_agent` passes `images=` kwarg to `execute_stream()` — fixed in reference impl commit 291eece |
| Voice input widget not clearing | `st.session_state` key for `st.audio_input` must be reset on Clear Conversation — same key as the conversation reset. Fixed in reference impl commit 208d58b |
| Voice input error | `pip install openai-whisper`; first use downloads ~140MB model |
| MCP server not found | `pip install mcp uvicorn`; run `.\scripts\start_mcp.ps1` |
| Port conflict on startup | Run `netstat -ano \| findstr :<PORT>` to find PID, then `taskkill /F /PID <PID>` for each process on the port |
| Onboarding tour shows every login | migration 018 not applied or POST /auth/onboarding-done not wired in login_form.py. Run `python scripts/migrate.py` and verify the endpoint is called on skip/complete |
| Onboarding tour not showing for new user | Tour only triggers for `client` and `viewer` roles. Users with `admin`, `operator`, or `staff` role skip it. Change role to `viewer` or `client` via Admin → Users → Edit |
| Edit User changes not saving | `must_change_password` and other fields must be in `_ALLOWED_USER_UPDATES` in admin_routes.py — whitelist enforced server-side |
| Delete User button not working | Use `@st.dialog` decorator for confirmation modals — never `st.session_state` confirmation flags inside columns (Streamlit nested columns limitation) |
| Analysis agent scope warning in logs | Scoped namespace check in analysis agent was too strict. Fixed in reference impl commit 8a36d10 |
| Workflow run delete fails | DELETE /workflows/runs/<id> must be wired in routes/workflows.py. Fixed in reference impl commit 8a36d10 |
| Theme toggle overlaps sidebar text | Toggle position must be `left:220px` (not `left:0` or right-side). Check brand.py theme_toggle() CSS — fixed in commit 86bbade |
| Memory namespace list hardcoded | `_observability.py` and memory pages must fetch namespace list from API dynamically, not from a hardcoded path. Fixed in commit 5423ba2 |
| Output delete silently fails | SQLite < 3.35 does not support DELETE...RETURNING. Use SELECT-then-DELETE in manager.py. Fixed in commit 0cadc72 |
| Sync log delete returns "Delete failed" / 404 | `SELECT changes()` resets to 0 after DELETE commits inside context manager. Use `cursor.rowcount` instead. Fixed in commit 26d1d38 |
| Output timestamps missing time | Output timestamps must display as YYYY-MM-DD HH:MM in all views. Check manager.py created_at formatting. Fixed in commit 0cadc72 |
| Activity feed shows UUID instead of agent name | dispatcher.list_runs must JOIN agents table and return agent_name + agent_display_name. Overview must use fallback chain: agent_name > display_name > id[:12]. Fixed in commit 552e5b3 |
| Both outputs from different agents show same agent name | Frontend (`_stream_response`) was saving output using stale selectbox state. Fix: output save belongs entirely in `stream_agent()` in `agents.py`; `agent.name` comes from URL path registry lookup. Fixed in commit 2afe202 |
| Stream error message flashes and immediately disappears | `st.error()` inside a streaming context is lost on `st.rerun()`. Fix: store error in `st.session_state["_stream_error"]`; `_render_chat_tab` appends it as an assistant history entry that persists. Fixed in commit 2afe202 |
| Output not saving after streaming completes | `_bg_pool` (max_workers=2) blocked by concurrent eval jobs — save task queued but never ran. Fix: use `threading.Thread(daemon=True)` for output save instead of `_bg_pool.submit()`. Fixed in commit 2afe202 |
| Agent gives confident answers with no data | analysis/briefing/research/writing agents must ask clarifying questions when input is missing or vague — never fabricate findings. Check system_prompt in agent YAML. Fixed in commits 49c6631, b1211e5 |
| Analysis/client-manager agents use training data for business facts | analysis-agent and client-manager-agent have explicit CRITICAL — NO TRAINING KNOWLEDGE block in system_prompt. Empty context must trigger MISSING INPUT PROTOCOL, not a fabricated answer. client-manager out-of-scope requests (email drafts, analysis) get one-line redirect only. Fixed in commit 87815fb |
| Evaluator gives task_completion=0 for correct scope refusals | Correct scope refusals must score task_completion=5.0 — agents enforcing their own scope boundaries are not penalised. Check _EVAL_PROMPT in agents/evaluator.py. Fixed in commit 11f51e5 |
| Legacy test files return 401 (no auth headers) | test_agents.py, test_memory.py, test_phase1.py require auth fixtures + APScheduler mock on client fixture. Add CLAUDEOS_SECRET_KEY (≥32 chars) to monkeypatch, mock init_scheduler/shutdown_scheduler, add auth_headers fixture. Fixed in commit 3c25eec |
| Usage page not visible | Usage page only shows for `client` and `viewer` roles. Admin/operator use Observability. Check dashboard/app.py nav role filter. |
| Namespace branding not loading | Namespace metadata (company_name, color, icon) loaded on login for client/viewer. If sidebar shows raw namespace slug: check `_ns_brand_loaded` logic in app.py and /namespaces/<ns> API response includes metadata field. |
| Email notifications not sending | Requires SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL in .env. Check core/notifications.py logs. SMTP must allow relaying from server IP. |
| Rate limit 429 errors | flask-limiter is active. Agent /run: 30/min, /stream: 20/min. If testing, either increase limits in limiter.py or throttle test requests. |
| CORS errors in browser | Set ALLOWED_ORIGINS in .env to match your dashboard URL. Never use wildcard `*` in production. |
| Context builder timeout in logs | Normal fallback — ChromaDB/hybrid-search took > 4s. System fell back to fast FTS context. If this is frequent, check ChromaDB indexing and sentence-transformers model load time. |

---

## Reference Implementation

The canonical ClaudeOS implementation lives at:
```
C:\Users\rigwe\Desktop\ClaudeOS\
```

When building for a new client, copy all source files from this reference, then apply brand substitution as described in Step 3. Do not rebuild from scratch unless the reference is unavailable — copying ensures 100% feature parity.

**To install this skill globally:**
```powershell
Copy-Item "C:\Users\rigwe\Desktop\ClaudeOS\SKILL.md" "$env:USERPROFILE\.claude\skills\claudeos.md"
```

Then invoke in any new directory with `/claudeos`.
