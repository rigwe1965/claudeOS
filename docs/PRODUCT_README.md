# FaiykeOS — Product Package

**Version:** 17.3 | **Built by:** faiyke-ai | **License:** See below

---

## What You Are Getting

FaiykeOS is a complete, self-hosted AI Operating System. This package contains everything needed to deploy 12 specialist AI agents, long-term memory, automated workflows, a ticketing system, and a full observability stack on your own server.

---

## Package Contents

```
FaiykeOS/
├── agents/
│   ├── definitions/          ← 12 YAML agent definitions (customisable)
│   ├── executor.py           ← Claude API wrapper, streaming, eval trigger
│   ├── evaluator.py          ← LLM-as-Judge async quality scoring
│   ├── dispatcher.py         ← Namespace routing and lock enforcement
│   ├── registry.py           ← Agent registry (seed from YAML)
│   └── schemas.py
├── core/
│   ├── api/routes/           ← 40+ Flask REST endpoints
│   ├── app.py                ← Flask factory
│   ├── auth.py               ← JWT, bcrypt, roles, audit log
│   ├── database.py           ← SQLite connection + migration runner
│   ├── notifications.py      ← Email engine (smtplib, fire-and-forget)
│   └── config.py
├── dashboard/
│   ├── _pages/               ← 10 Streamlit pages
│   ├── components/           ← Brand CSS, login form, onboarding tour
│   └── app.py                ← Streamlit entry point
├── memory/
│   ├── engine.py             ← Memory facade
│   ├── retriever.py          ← Hybrid BM25+vector RAG
│   ├── context_builder.py    ← Tiered context injection
│   └── consolidator.py       ← Episodic→semantic consolidation
├── workflows/
│   ├── definitions/          ← 7 YAML workflow pipelines
│   ├── pipeline.py           ← Step executor
│   └── scheduler.py          ← APScheduler cron jobs
├── mcp/server.py             ← MCP Tool Server (port 5100, optional)
├── scripts/
│   ├── migrate.py            ← Runs all 20 DB migrations
│   ├── seed_agents.py        ← Loads agents from YAML
│   ├── seed_workflows.py     ← Loads workflows from YAML
│   ├── seed_namespaces.py    ← Creates default namespaces
│   ├── seed_client_schema.py ← Pre-populates 14 onboarding fields
│   ├── create_admin.py       ← Creates the first admin account
│   ├── gen_handbook_pdf.py   ← Regenerates the client handbook PDF
│   └── start.ps1             ← Starts Flask + Streamlit (Windows)
├── tests/                    ← 115 pytest tests
├── docs/
│   ├── FaiykeOS_Handbook_faiyke-ai.pdf   ← Full client handbook
│   ├── SETUP_GUIDE_NONTECHNICAL.md       ← For non-technical buyers
│   ├── AGENCY_LICENSE.md                 ← Agency/reseller terms
│   └── landing/                          ← Marketing landing pages
├── .env.example              ← Environment template
├── requirements.txt
├── CLAUDE.md                 ← Full project rules and architecture
└── SKILL.md                  ← Automated build playbook for new clients
```

---

## System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Windows 10 64-bit | Windows 10/11 or Ubuntu 22.04 |
| CPU | 2 cores | 4+ cores |
| RAM | 4 GB | 8 GB+ |
| Disk | 10 GB free | 20 GB+ SSD |
| Python | 3.11 | 3.11 or 3.12 |
| Internet | Required (Claude API calls) | Stable broadband |

---

## Quick Start (5 commands)

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
Copy-Item .env.example .env
# Edit .env — add ANTHROPIC_API_KEY and CLAUDEOS_SECRET_KEY (≥32 chars)

# 3. Initialise database (runs all 20 migrations)
python scripts/migrate.py

# 4. Seed default data
python scripts/seed_agents.py
python scripts/seed_workflows.py
python scripts/seed_namespaces.py

# 5. Create admin account and start
python scripts/create_admin.py --username admin --password YourPass123!
.\scripts\start.ps1
```

Open `http://localhost:8501` — login with your admin credentials.

---

## What's New in v17.3

| Change | Detail |
|--------|--------|
| Chat history restored on refresh | Conversation turns now reload from the database on every page load — no more lost chat history |
| Agent descriptions in dropdown | Chat selectbox shows category + description per agent — pick the right specialist at a glance |
| Context degraded warning | Live caption under any response where memory retrieval timed out — transparent about quality |
| Actionable Pulse Score alerts | Usage page alerts now include **Go →** buttons that navigate directly to Agents, Tickets, Memory, or Workflows |
| Sync log Select All + Delete fixed | Select All and bulk delete now fully work with persistent confirmation after delete |
| 429 rate limit handled | Dashboard shows an informative toast instead of a misleading "API offline" error |
| All 16 delete surfaces verified | Full end-to-end delete audit: memory, runs, workflow runs, outputs, API keys, sessions, tickets, sync log, users — all confirmed working |
| Memory audit trail | Every agent run now records which memory sections were injected (`context_sources` field in run record) |
| White-label demo on landing page | Side-by-side CSS browser mockup on the marketing page showing default vs. branded sidebar |

## What's New in v17.2

| Change | Detail |
|--------|--------|
| Faster Overview page | ChromaDB health probe cached 30s; live refresh non-blocking (no more 8s session freeze) |
| Faster agent runs | Eliminated redundant DB read on every run completion; streaming path saves one extra write per request |
| Faster namespace stats | 7 sequential queries collapsed into 1 compound query |
| Faster bulk memory delete | Batch SQL replaces N individual deletes — up to 500× faster on large selections |
| MCP server secured | Now binds to localhost only — previously reachable from any network with zero authentication |
| Role enforcement hardened | Workflow delete, scheduler reload, webhook management now restricted to admin/operator |
| XSS fix in Admin Branding | Company name and icon are now HTML-escaped before rendering in the live preview |
| Content-Security-Policy | Added to all API responses |
| Stale run auto-cleanup | Runs stuck in "running" from a crashed server are automatically reset to "failed" on startup |
| Memory value size limit | Write endpoint rejects values over 64 KB (returns 422) — prevents accidental DoS |
| Timezone default | `SCHEDULER_TIMEZONE` now defaults to `Europe/Berlin`; set your own in `.env` |

## What's New in v17.1

| Change | Detail |
|--------|--------|
| Clickable agent catalog cards | Click any card in Catalog → opens Chat tab with that agent pre-selected |
| Inline file attachment | Attach images (PNG/JPG/WebP/GIF) and documents (.md/.txt) directly in the chat bar via 📎; sidebar uploader still available as fallback |
| Tab persistence | Active tab (Chat / Catalog / Run History) survives page reruns and dark/light theme switches |
| Retrieval performance | BM25 corpus cached per namespace; separate context-builder thread pool; retriever timeouts prevent slow ChromaDB from blocking agent responses |

---

## What's Included — Feature Summary

### AI Agents (12)
| Agent | Category | What It Does |
|-------|----------|-------------|
| Analysis Agent | Analysis | Structured reports, findings, recommendations from data |
| Morning Briefing Agent | Ops | Daily briefing from overnight memory context |
| Client Manager Agent | Ops | Per-client status cards with deadlines and blockers |
| Communications Agent | Comms | Client-facing emails, messages, proposals |
| Memory Curator Agent | System | Review, dedup, and consolidate memory entries |
| Meta Orchestrator Agent | System | Decompose complex goals into agent chains |
| QA Agent | Engineering | Code and content review against quality rules |
| Research Agent | Research | Deep research with synthesis and source validation |
| Scheduling Agent | Ops | Natural language → memory reminder entries |
| Transport Ops Agent | Domain | Fleet/booking analysis (namespace-locked, customisable) |
| Workflow Builder Agent | System | Plain English → workflow YAML |
| Writing Agent | Content | Reports, emails, proposals with voice matching |

### Dashboard Pages (10)
- **Overview** — KPIs, activity feed, quick dispatch, eval pills, auto-refresh
- **Agents** — Chat (streaming, images, voice, multi-turn, inline file attach), Catalog (clickable cards → pre-select agent in Chat), Run History
- **Memory** — FTS + semantic + hybrid search, write/edit/delete, bulk ops
- **Workflows** — Manage, trigger, schedule, webhook setup
- **Projects** — Namespaces, project management, context file upload
- **Outputs** — Browse, search, export (Markdown/PDF), bulk delete
- **Tickets** — Full lifecycle, SLA tiers, comments, email notifications
- **Observability** — Quality Scores, Latency, Token Cost, Memory Health, Namespace Usage
- **Settings** — Sync, email config, environment
- **Admin** — Users, API Keys, Audit Log, Sessions, Security, Onboarding, Branding
- **Usage** — Client/viewer: Pulse Score, KPI grid, activity feed (client/viewer only)

### Security
- JWT access tokens (60-min TTL) + refresh tokens (24-hour session window, SHA-256 hashed)
- bcrypt passwords (12 rounds), min 10 chars, complexity enforced
- 5 roles: admin, operator, client, viewer, staff
- Account lockout after 5 failed attempts
- CORS via ALLOWED_ORIGINS env var (no wildcard in production)
- Rate limiting: 30/min agent run, 20/min stream, 10/min webhook
- Security headers: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, CSP, HSTS (production)
- MCP server localhost-only (no unauthenticated external access)
- Role-gated destructive operations (admin/operator required for delete, webhook, scheduler)
- Full audit log

---

## Customising Agents

All agent behaviour is controlled by YAML files in `agents/definitions/`. No coding required. Example:

```yaml
name: my-custom-agent
display_name: "My Custom Agent"
system_prompt: |
  You are a specialist agent for [YOUR BUSINESS].
  [Add your instructions here]
model: claude-sonnet-4-6
max_tokens: 4096
temperature: 0.5
enabled: true
```

After editing, reseed: `python scripts/seed_agents.py`

---

## Environment Variables

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
CLAUDEOS_SECRET_KEY=your-random-48-char-string

# Ports
FLASK_PORT=5000
STREAMLIT_PORT=8501

# Security
ALLOWED_ORIGINS=http://localhost:8501

# Scheduler timezone (default: Europe/Berlin)
SCHEDULER_TIMEZONE=Europe/Berlin

# Optional — Email notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=your_app_password

# Optional — Cloud sync
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_key
```

---

## Running Tests

```powershell
pytest tests/ -v
# Expected: 115 passed
```

---

## License

**Self-Install (Developer):** Personal use only. Deploy on one server for your own business. No resale.

**Agency License:** Full white-label rights. Deploy for unlimited clients under your brand. Resale permitted under the terms in `docs/AGENCY_LICENSE.md`.

See `docs/AGENCY_LICENSE.md` for full commercial terms.

---

## Support

**Email:** hello@faiyke-ai.com  
**Subject line:** `FaiykeOS Support — [brief description]`  
**Include:** Your purchase reference, OS/Python version, exact error message, which page/feature

Response within 24 hours (business days).
