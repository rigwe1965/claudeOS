"""
Generate FaiykeOS_Handbook_faiyke-ai.pdf  (v17.2)
World-class client-facing handbook for faiyke-ai.
Usage: python scripts/gen_handbook_pdf.py
"""
import io
from datetime import date
from pathlib import Path
from xhtml2pdf import pisa

VERSION = "17.2"
CLIENT  = "faiyke-ai"
TODAY   = date.today().isoformat()

ADMIN_NAME  = "[ADMIN NAME]"
ADMIN_EMAIL = "[ADMIN EMAIL]"
ADMIN_PHONE = "[ADMIN PHONE]"
SYSTEM_URL  = "[http://YOUR-SERVER-IP:8501]"
API_URL     = "[http://YOUR-SERVER-IP:5000]"

CSS = """
@page {
  size: A4;
  margin: 1.4cm 1.8cm 1.8cm 1.8cm;
  @frame footer_frame {
    -pdf-frame-content: footer_content;
    bottom: 0.5cm; left: 1.8cm; right: 1.8cm; height: 0.7cm;
  }
}

body {
  font-family: Arial, sans-serif;
  font-size: 10.5pt;
  color: #1a1a1a;
  line-height: 1.5;
}

p { margin: 5px 0 8px 0; }

h1 {
  color: #407E3C;
  font-size: 18pt;
  border-bottom: 3px solid #407E3C;
  padding-bottom: 6px;
  margin-top: 0;
  page-break-before: always;
  page-break-after: avoid;
  -pdf-keep-with-next: true;
}
h1.no-break { page-break-before: avoid; margin-top: 0; }
h2 {
  color: #2d5a29;
  font-size: 13pt;
  border-bottom: 1px solid #c8e0c0;
  padding-bottom: 3px;
  margin-top: 20px;
  margin-bottom: 6px;
  page-break-after: avoid;
  -pdf-keep-with-next: true;
}
h3 {
  color: #2d5a29;
  font-size: 11pt;
  margin-top: 14px;
  margin-bottom: 4px;
  page-break-after: avoid;
  -pdf-keep-with-next: true;
}
h4 {
  color: #407E3C;
  font-size: 10.5pt;
  margin-top: 10px;
  margin-bottom: 3px;
  page-break-after: avoid;
  -pdf-keep-with-next: true;
}

table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 9.5pt; table-layout: fixed; }
th   { background: #407E3C; color: #fff; padding: 6px 10px; text-align: left; word-wrap: break-word; }
td   { padding: 6px 10px; border-bottom: 1px solid #d0e8c8; vertical-align: top; word-wrap: break-word; }
tr:nth-child(even) td { background: #f4faf2; }

code {
  background: #f0f4f0;
  color: #2d5a29;
  padding: 0 4px;
  font-family: "Courier New", monospace;
  font-size: 8.5pt;
  word-break: break-all;
}
pre {
  background: #1e2a1e;
  color: #c8e8c8;
  border-left: 4px solid #407E3C;
  padding: 9px 13px;
  font-family: "Courier New", monospace;
  font-size: 7.5pt;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 8px 0;
  page-break-inside: avoid;
}

ul, ol { margin: 4px 0; padding-left: 22px; }
li     { margin: 3px 0; }

hr     { border: none; border-top: 1px solid #d0e8c8; margin: 14px 0; }
strong { color: #2d5a29; }

/* callout boxes */
.note  { background: #e8f5e4; border-left: 4px solid #407E3C; padding: 9px 13px; margin: 10px 0; font-size: 9.5pt; page-break-inside: avoid; }
.warn  { background: #fff8e0; border-left: 4px solid #f9a825; padding: 9px 13px; margin: 10px 0; font-size: 9.5pt; page-break-inside: avoid; }
.tip   { background: #e8f4e8; border-left: 4px solid #5a9e56; padding: 9px 13px; margin: 10px 0; font-size: 9.5pt; page-break-inside: avoid; }
.callout { background: #e3f2fd; border-left: 4px solid #1565C0; padding: 9px 13px; margin: 10px 0; font-size: 9.5pt; page-break-inside: avoid; }
.example { background: #fff8e1; border-left: 4px solid #f9a825; padding: 9px 13px; margin: 10px 0; font-size: 9.5pt; page-break-inside: avoid; }

/* cover */
.cover {
  background: #1a3a18;
  width: 100%;
  min-height: 100%;
  padding: 80px 70px 60px 70px;
  color: white;
}
.cover-logo    { font-size: 44pt; font-weight: bold; color: #ffffff; letter-spacing: 2px; margin-bottom: 4px; }
.cover-tagline { font-size: 14pt; color: #a8d4a0; margin-bottom: 6px; }
.cover-divider { border-top: 2px solid #407E3C; margin: 20px 0 18px 0; }
.cover-client  { font-size: 12pt; color: #ffffff; margin-bottom: 4px; }
.cover-version { font-size: 11pt; color: #c8e0c0; margin-bottom: 20px; }
.cover-geo-bar { background: #407E3C; height: 6px; margin: 24px 0; }
.cover-footer  { font-size: 9pt; color: #6a9e66; margin-top: 30px; }
.cover-new-badge { background: #5a9e56; color: white; padding: 3px 10px; font-size: 9pt; margin-bottom: 12px; display: inline-block; }
.cover-features { margin: 14px 0; padding: 0; }
.cover-features li { color: #c8e8c0; font-size: 10pt; margin: 5px 0; list-style: none; padding-left: 0; }

/* pills */
.pill-green { background:#2e7d32; color:white; padding:1px 7px; font-size:8pt; }
.pill-amber { background:#f57f17; color:white; padding:1px 7px; font-size:8pt; }
.pill-red   { background:#c62828; color:white; padding:1px 7px; font-size:8pt; }
.pill-gray  { background:#757575; color:white; padding:1px 7px; font-size:8pt; }

/* badges */
.badge      { background: #407E3C; color: white; padding: 2px 8px; font-size: 8pt; margin-right: 4px; }
.badge-new  { background: #5a9e56; color: white; padding: 2px 8px; font-size: 8pt; margin-right: 4px; }
.badge-gray { background: #888;    color: white; padding: 2px 8px; font-size: 8pt; margin-right: 4px; }

/* gauge */
.gauge-block { background: #f4faf2; border: 1px solid #c8e0c0; padding: 10px 14px; margin: 8px 0; font-size: 9.5pt; page-break-inside: avoid; }

/* footer */
#footer_content { text-align: center; font-size: 8pt; color: #888; font-family: Arial, sans-serif; }
"""


# ═══════════════════════════════════════════════════════════════════════════════
# COVER PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def cover_page() -> str:
    return f"""
<div class="cover">
  <div class="cover-logo">FaiykeOS</div>
  <div class="cover-tagline">AI Operating System &mdash; Client Handbook</div>
  <div class="cover-geo-bar"></div>
  <div class="cover-new-badge">Version {VERSION} &mdash; Commercial Release</div>
  <div class="cover-client"><strong>Prepared for:</strong> {CLIENT}</div>
  <div class="cover-version"><strong>Date:</strong> {TODAY} &nbsp;|&nbsp; <strong>Edition:</strong> v{VERSION} Commercial</div>
  <div class="cover-divider"></div>
  <ul class="cover-features">
    <li>&#10003; &nbsp; 12 specialist AI agents sharing persistent long-term memory</li>
    <li>&#10003; &nbsp; Hybrid BM25 + vector retrieval &mdash; agents always find the right context</li>
    <li>&#10003; &nbsp; 7 built-in automation workflows with cron scheduling and webhook triggers</li>
    <li>&#10003; &nbsp; Automatic LLM-as-Judge quality scoring on every agent response</li>
    <li>&#10003; &nbsp; Full ticketing system with SLA tiers and email notifications</li>
    <li>&#10003; &nbsp; Per-namespace white-labeling: your brand, your colours, your experience</li>
    <li>&#10003; &nbsp; MCP Tool Server: expose all agents to Claude Desktop and AI clients</li>
    <li>&#10003; &nbsp; Enterprise security: JWT, bcrypt, rate limiting, CSP, HSTS, audit log</li>
  </ul>
  <div class="cover-footer">
    Confidential &mdash; For authorised users of FaiykeOS only.<br/>
    Do not distribute outside your organisation.<br/>
    Powered by faiyke-ai &nbsp;&middot;&nbsp; FaiykeOS &copy; 2026
  </div>
</div>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# TABLE OF CONTENTS
# ═══════════════════════════════════════════════════════════════════════════════

def toc() -> str:
    entries = [
        ("1",  "s1",  "Introduction",                          "What FaiykeOS Is, Architecture, Key Concepts"),
        ("2",  "s2",  "System Requirements",                   "Hardware, Software, Network, Required Keys"),
        ("3",  "s3",  "Installation &amp; First-Run Setup",    "From Zero to Running in 15 Minutes"),
        ("4",  "s4",  "Logging In &amp; First-Time Experience","Auth, Roles, Onboarding Modal"),
        ("5",  "s5",  "Dashboard Tour",                        "Every Page Explained, Navigation Quick Guide"),
        ("6",  "s6",  "Working with AI Agents",                "Chat, Catalog, Prompts, File Attach, Voice"),
        ("7",  "s7",  "Memory System",                         "Storage, Retrieval, Injection, Consolidation"),
        ("8",  "s8",  "Workflows &amp; Automation",            "Pipelines, Scheduling, Webhooks, Walkthrough"),
        ("9",  "s9",  "Client Vault",                          "Namespaces, Projects, Context Files"),
        ("10", "s10", "Outputs &amp; Reports",                 "Saving, Searching, Exporting, Soft-Delete"),
        ("11", "s11", "Ticketing System",                      "Tickets, SLA, Email Notifications"),
        ("12", "s12", "Quality Scoring",                       "LLM-as-Judge, Rubric, Improving Scores"),
        ("13", "s13", "Observability",                         "Quality, Latency, Token Cost, Memory, Namespace"),
        ("14", "s14", "Namespace Branding &amp; Customisation","Per-Namespace White-Labeling"),
        ("15", "s15", "Custom Background Colors",              "Per-User and Per-Namespace Background"),
        ("16", "s16", "Advanced Features",                     "Multi-Turn, Images, Voice, MCP, A2A, Pulse Score"),
        ("17", "s17", "API Reference",                         "REST Endpoints, Auth, Examples"),
        ("18", "s18", "Security Model",                        "Auth, CORS, Rate Limits, CSP, HSTS, Isolation"),
        ("19", "s19", "Cloud Sync",                            "Supabase Backup, Extended Sync, Log Management"),
        ("20", "s20", "Troubleshooting &amp; Support",         "Common Problems, Fixes, New v17.2 Entries"),
        ("21", "s21", "Quick Reference",                       "Cheat Sheet: Pages, Shortcuts, API Snippets"),
        ("22", "s22", "Glossary",                              "20 Key Terms Defined"),
    ]
    rows = "".join(
        f"<tr>"
        f"<td style='width:6%;color:#407E3C;font-weight:bold;'>{n}</td>"
        f"<td style='width:36%;'><a href='#{anchor}' style='color:#407E3C;text-decoration:none;'>"
        f"<strong>{title}</strong></a></td>"
        f"<td style='color:#555;'>{desc}</td>"
        f"</tr>"
        for n, anchor, title, desc in entries
    )
    return f"""
<h1 class="no-break">Contents</h1>
<table>
<tr><th style="width:6%;">#</th><th style="width:36%;">Section</th><th>What You Will Find</th></tr>
{rows}
</table>
<p style="margin-top:12px;font-size:9pt;color:#555;">
  <strong>New in v17.2:</strong> Security hardening (CSP header, HSTS, MCP localhost-only, session window 24h,
  memory write cap 64 KB), performance hardening (ChromaDB probe cached, namespace stats single query,
  non-blocking Overview refresh), stale run auto-cleanup on startup, extended Supabase sync (users, tickets,
  workflows), Section 21 Quick Reference, Section 22 Glossary.
</p>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — INTRODUCTION
# ═══════════════════════════════════════════════════════════════════════════════

def s1_intro() -> str:
    return f"""
<h1><a name="s1"></a>1 &mdash; Introduction</h1>

<h2>What Is FaiykeOS?</h2>
<p>FaiykeOS is a privately hosted AI Operating System that puts a team of 12 specialist AI assistants,
a persistent long-term memory engine, automated workflow pipelines, a full ticketing system, and a
real-time observability dashboard under one authenticated roof. It runs entirely on your own
infrastructure &mdash; your data never leaves your environment except when you explicitly enable
cloud backup to Supabase.</p>

<p>Where most AI tools give you a chat interface, FaiykeOS gives you an <em>operating layer</em>:
agents share memory, outputs are stored and searchable, quality is measured automatically, and
your team can collaborate on tickets and projects without switching tools. Version 17.2 adds
performance hardening (faster everything), security hardening (Content-Security-Policy, HSTS,
24-hour session window, memory size cap), stale run auto-cleanup, and extended cloud sync.</p>

<h2>Who Should Read This Handbook</h2>
<table>
<tr><th style="width:25%;">Reader</th><th>What to Focus On</th></tr>
<tr><td><strong>New Client Users</strong></td>
    <td>Sections 1&ndash;6 for setup and daily use, then Section 7 (Memory) and Section 11 (Tickets).</td></tr>
<tr><td><strong>Power Users / Operators</strong></td>
    <td>All sections, with particular attention to Sections 8 (Workflows), 12 (Quality), 13 (Observability), and 17 (API).</td></tr>
<tr><td><strong>Administrators</strong></td>
    <td>Sections 3 (Installation), 4 (Auth), 14 (Branding), 18 (Security), 19 (Cloud Sync), and the Quick Reference (Sec 21).</td></tr>
<tr><td><strong>Developers / Integrators</strong></td>
    <td>Sections 8 (Webhooks), 16 (MCP/A2A), 17 (API Reference), and 18 (Security) are your primary references.</td></tr>
</table>

<h2>Key Concepts Primer</h2>
<table>
<tr><th style="width:22%;">Concept</th><th>Plain-English Explanation</th></tr>
<tr><td><strong>Namespace</strong></td>
    <td>An isolated workspace. Memory, agents, outputs, and tickets all belong to a namespace. Clients only see their own namespace.</td></tr>
<tr><td><strong>Agent</strong></td>
    <td>An AI specialist with a defined role, persona, and system prompt. FaiykeOS ships 12 agents; you interact with them via chat or API.</td></tr>
<tr><td><strong>Memory Entry</strong></td>
    <td>A fact, preference, reminder, or task stored in the database. Agents automatically receive the most relevant entries as context when they run.</td></tr>
<tr><td><strong>Workflow</strong></td>
    <td>A multi-step pipeline that chains agent calls. Runs on a schedule, on demand, or via a webhook from an external system.</td></tr>
<tr><td><strong>Eval Score</strong></td>
    <td>An automatic 0&ndash;5 quality rating assigned to each agent response by a fast AI judge. Higher is better.</td></tr>
<tr><td><strong>Pulse Score</strong></td>
    <td>A composite 0&ndash;100 namespace health indicator combining eval quality, ticket resolution, memory freshness, and workflow success.</td></tr>
<tr><td><strong>JWT</strong></td>
    <td>JSON Web Token &mdash; the short-lived credential that proves you are logged in. Expires every 60 minutes; silently refreshed while active.</td></tr>
<tr><td><strong>MCP</strong></td>
    <td>Model Context Protocol &mdash; an open standard that lets external AI clients (Claude Desktop, Cursor) call FaiykeOS agents as native tools.</td></tr>
</table>

<h2>Architecture at a Glance</h2>
<pre>Browser  ──►  Streamlit Dashboard  (:8501)
                      │
              Login Gate (JWT) + Onboarding Modal
                      │
              Flask REST API  (:5000)
              ├─ Auth &amp; Roles  (CORS, rate limits, security headers, CSP, HSTS)
              ├─ Agent Dispatcher  (30/min run / 20/min stream)
              ├─ Memory Engine  (SQLite FTS5 + ChromaDB + Hybrid BM25 RRF)
              ├─ Workflow Scheduler  (APScheduler + webhook triggers)
              ├─ Output Manager  (auto-tag, FTS, soft-delete v17.2)
              ├─ Ticketing + Email Notifications
              ├─ Namespace Branding (per-namespace metadata)
              └─ Observability (quality, latency, tokens, memory health)

Optional:  MCP Tool Server  (:5100, localhost only)  — 12 agents as MCP tools</pre>

<h3>Layer Summary</h3>
<table>
<tr><th style="width:12%;">Layer</th><th style="width:28%;">Name</th><th>What It Does</th></tr>
<tr><td>0</td><td>Streamlit Dashboard</td><td>Login-gated browser UI, 11 pages, role-filtered navigation, onboarding tour.</td></tr>
<tr><td>1</td><td>Flask REST API</td><td>JWT + API-Key auth on every route, CORS, rate limiting, security headers.</td></tr>
<tr><td>2</td><td>Memory Engine</td><td>SQLite FTS5 + ChromaDB vector store + hybrid BM25 retrieval with RRF reranking.</td></tr>
<tr><td>3</td><td>Agent Registry</td><td>12 agent YAML definitions; each has a role, persona, and hallucination guard.</td></tr>
<tr><td>4</td><td>Workflow Engine</td><td>APScheduler cron pipelines, manual triggers, and HMAC-secured webhook triggers.</td></tr>
<tr><td>5</td><td>Client Vault</td><td>Namespace isolation, project management, context file storage.</td></tr>
<tr><td>6</td><td>Output Manager</td><td>Auto-tag, full-text search, Markdown/PDF export, soft-delete (v17.2).</td></tr>
<tr><td>7</td><td>Supabase Cloud Sync</td><td>Push-only 15-minute sync of memory, outputs, users, tickets, workflows.</td></tr>
<tr><td>8</td><td>Auth &amp; Security</td><td>JWT, bcrypt 12-round passwords, roles, audit log, account lockout.</td></tr>
<tr><td>9</td><td>Ticketing System</td><td>SLA tiers, staff role, bulk ops, email notifications via smtplib.</td></tr>
<tr><td>10</td><td>Real-Time Intelligence</td><td>SSE streaming, LLM-as-Judge eval (Haiku), Observability dashboard.</td></tr>
<tr><td>11</td><td>Advanced Memory</td><td>Hybrid RAG, tiered context injection (~40% token reduction), consolidation.</td></tr>
<tr><td>12</td><td>Protocols</td><td>MCP Tool Server (:5100, localhost), A2A Agent Cards, webhook triggers.</td></tr>
<tr><td>13</td><td>Multimodal</td><td>Multi-turn chat, image/screenshot analysis, voice input (local Whisper).</td></tr>
<tr><td>14</td><td>Commercial</td><td>White-labeling, client usage dashboard, email notifications, rate limiting.</td></tr>
</table>

<div class="note"><strong>Privacy note:</strong> FaiykeOS runs on your own server. No prompts,
memory entries, or outputs are sent to third parties except the Anthropic Claude API (for AI
inference) and optionally Supabase (for cloud backup, only when you enable it).</div>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — SYSTEM REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def s2_requirements() -> str:
    return """
<h1><a name="s2"></a>2 &mdash; System Requirements</h1>

<h2>Server (Where FaiykeOS Runs)</h2>
<table>
<tr><th style="width:28%;">Component</th><th>Minimum</th><th>Recommended</th></tr>
<tr><td>Operating System</td><td>Windows 10 64-bit</td><td>Windows 10/11 64-bit</td></tr>
<tr><td>CPU</td><td>2 cores</td><td>4+ cores</td></tr>
<tr><td>RAM</td><td>4 GB</td><td>8 GB+</td></tr>
<tr><td>Disk</td><td>10 GB free</td><td>20 GB+ SSD</td></tr>
<tr><td>Python</td><td>3.11</td><td>3.11 or 3.12</td></tr>
<tr><td>Internet</td><td>Required for Claude API</td><td>Stable broadband</td></tr>
</table>

<h2>Client Devices (Browsers)</h2>
<p>Any modern browser &mdash; Chrome, Edge, Firefox, or Safari. No installation required on
client devices. A desktop screen is recommended for the Observability and Admin panels; mobile
browsers work for agents, memory, and tickets.</p>

<h2>Required Accounts and Keys</h2>
<table>
<tr><th style="width:28%;">Service</th><th>Purpose</th><th style="width:22%;">Cost</th></tr>
<tr><td><strong>Anthropic Claude API</strong></td>
    <td>Powers all AI agent inference. Required.</td>
    <td>Pay-per-token (anthropic.com/pricing)</td></tr>
<tr><td><strong>SMTP Email Server</strong></td>
    <td>Ticket email notifications. Optional.</td>
    <td>Free (Gmail, Outlook) or paid relay</td></tr>
<tr><td><strong>Supabase</strong></td>
    <td>Cloud backup of memory, outputs, and more. Optional.</td>
    <td>Free tier available</td></tr>
</table>

<div class="warn"><strong>Protect your <code>ANTHROPIC_API_KEY</code>.</strong> Store it only
in the <code>.env</code> file on the server. If compromised, rotate it immediately in the
Anthropic console and update <code>.env</code>, then restart the server.</div>

<h2>Network and Firewall</h2>
<p>FaiykeOS binds two ports on your server:</p>
<ul>
<li><strong>Port 5000</strong> &mdash; Flask REST API (internal; accessed by Streamlit)</li>
<li><strong>Port 8501</strong> &mdash; Streamlit dashboard (accessible to browser clients)</li>
</ul>
<p>If users access FaiykeOS from other machines on your network, open port 8501 in Windows
Defender Firewall. Port 5000 does not need to be exposed externally unless you are using
the API directly from outside the server.</p>
<div class="tip"><strong>Windows Defender Firewall:</strong> open Windows Security &rarr; Firewall
&rarr; Advanced Settings &rarr; Inbound Rules &rarr; New Rule &rarr; Port &rarr; TCP 8501.
Name it &ldquo;FaiykeOS Dashboard&rdquo;.</div>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — INSTALLATION & FIRST-RUN SETUP
# ═══════════════════════════════════════════════════════════════════════════════

def s3_install() -> str:
    return f"""
<h1><a name="s3"></a>3 &mdash; Installation &amp; First-Run Setup</h1>

<p>You can go from a fresh Windows machine to a fully running FaiykeOS instance in about
15 minutes. Follow every step in order.</p>

<h2>Step 1 &mdash; Get the Code</h2>
<p>Copy the FaiykeOS project folder to your server. The top-level layout is:</p>
<pre>FaiykeOS/
├─ agents/       ├─ core/        ├─ dashboard/   ├─ docs/
├─ memory/       ├─ mcp/         ├─ scripts/     ├─ workflows/
├─ requirements.txt              └─ .env.example</pre>

<h2>Step 2 &mdash; Create Your Environment File</h2>
<p>Copy <code>.env.example</code> to <code>.env</code> and fill in your values:</p>
<pre># .env
ANTHROPIC_API_KEY=sk-ant-...           # required
FLASK_SECRET_KEY=change-this-secret    # any long random string
FLASK_PORT=5000
STREAMLIT_PORT=8501
ALLOWED_ORIGINS=http://localhost:8501  # CORS whitelist — add your dashboard URL

# Optional — Email notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=your_app_password
SMTP_FROM=no-reply@yourdomain.com

# Optional — Supabase cloud backup
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key

# Optional — Scheduler timezone (default: Europe/Berlin)
SCHEDULER_TIMEZONE=Europe/Berlin</pre>

<div class="warn"><strong>Never commit <code>.env</code> to version control.</strong>
The <code>.gitignore</code> already excludes it. Keep this file private.</div>

<h2>Step 3 &mdash; Install Python Dependencies</h2>
<pre>pip install -r requirements.txt</pre>
<p>This installs Flask, Streamlit, Anthropic SDK, ChromaDB, sentence-transformers,
rank-bm25, APScheduler, waitress, plotly, PyJWT, bcrypt, and all other required packages.
Expect 3&ndash;5 minutes on a fresh environment.</p>
<pre># Optional — Voice input (downloads ~140 MB model on first use)
pip install openai-whisper

# Optional — MCP Tool Server
pip install mcp uvicorn</pre>

<h2>Step 4 &mdash; Initialise the Database</h2>
<pre>python scripts/migrate.py</pre>
<p>Creates <code>data/claudeos.db</code> with all 20+ tables including auth, memory, agents,
workflows, tickets, branding metadata, and observability columns. Safe to re-run on existing
databases &mdash; only applies missing migrations.</p>

<h2>Step 5 &mdash; Seed Default Data</h2>
<pre>python scripts/seed_agents.py       # loads 12 agent definitions
python scripts/seed_workflows.py    # loads 7 default pipelines
python scripts/seed_namespaces.py   # creates the global namespace

# Optional — pre-populate 14 onboarding fields for a client namespace
python scripts/seed_client_schema.py --namespace faiyke-ai</pre>
<p><code>seed_client_schema.py</code> creates placeholder memory entries covering business name,
industry, primary goals, brand tone, SLA tier, contact details, timezone, and more. Agents
read these automatically when running in that namespace. Safe to run multiple times &mdash; skips
existing keys.</p>

<h2>Step 6 &mdash; Create the Admin Account</h2>
<pre>python scripts/create_admin.py --username admin --password Admin123!</pre>
<div class="warn"><strong>Password requirements:</strong> minimum 10 characters, at least one
uppercase letter, one lowercase letter, and one digit.</div>

<h2>Step 7 &mdash; Start the System</h2>
<pre>.\\scripts\\start.ps1</pre>
<p>The start script kills any existing processes on ports 5000 and 8501, starts Flask via
waitress, waits for <code>/health</code> to respond, then starts Streamlit. After
5&ndash;10 seconds, open your browser to <strong>{SYSTEM_URL}</strong>.</p>

<h2>Stopping the System</h2>
<pre>.\\scripts\\stop.ps1</pre>
<p>Or manually:</p>
<pre>netstat -ano | findstr :5000   # find PID for Flask
taskkill /F /PID &lt;PID&gt;
netstat -ano | findstr :8501   # find PID for Streamlit
taskkill /F /PID &lt;PID&gt;</pre>

<h2>Optional &mdash; Start the MCP Server</h2>
<pre>.\\scripts\\start_mcp.ps1      # starts on port 5100</pre>
<div class="note"><strong>MCP server is optional</strong> and not required for core operation.
It exposes all 12 agents to external AI clients such as Claude Desktop.</div>

<h2>Common Install Issues</h2>
<table>
<tr><th style="width:38%;">Problem</th><th>Fix</th></tr>
<tr><td><code>pip install</code> fails on sentence-transformers</td>
    <td>Ensure C++ Build Tools are installed. Run <code>pip install --upgrade pip setuptools wheel</code> first.</td></tr>
<tr><td>ChromaDB install fails</td>
    <td>Try <code>pip install chromadb --no-build-isolation</code>.</td></tr>
<tr><td>Port already in use</td>
    <td>Run <code>netstat -ano | findstr :5000</code>, get the PID, then <code>taskkill /F /PID &lt;PID&gt;</code>.</td></tr>
<tr><td>Dashboard loads but API returns 502</td>
    <td>Flask failed to start. Check <code>logs/flask.log</code>. Most common cause: missing <code>.env</code> or wrong <code>ANTHROPIC_API_KEY</code>.</td></tr>
<tr><td>Windows Defender blocks the script</td>
    <td>Right-click <code>start.ps1</code> &rarr; Properties &rarr; Unblock. Or run PowerShell as Administrator and set <code>Set-ExecutionPolicy RemoteSigned</code>.</td></tr>
</table>

<div class="tip"><strong>After any change to <code>.env</code>:</strong> always restart the server
with <code>.\\scripts\\start.ps1</code>. Running processes do not pick up environment changes automatically.</div>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — LOGGING IN & FIRST-TIME EXPERIENCE
# ═══════════════════════════════════════════════════════════════════════════════

def s4_login() -> str:
    return """
<h1><a name="s4"></a>4 &mdash; Logging In &amp; First-Time Experience</h1>

<h2>The Login Screen</h2>
<p>Navigate to the dashboard URL in your browser. You will see the FaiykeOS login screen with
two tabs: <strong>Login</strong> and <strong>Register</strong>. Your namespace branding
(company name, icon, colours, and background) is applied to the login page automatically
before you log in.</p>

<h2>Logging In</h2>
<ol>
<li>Enter your username and password (usernames are case-insensitive &mdash; <code>Alice</code>
    and <code>alice</code> are the same account)</li>
<li>Press <strong>Enter</strong> or click <strong>Login</strong></li>
<li>If the <em>must change password</em> flag is set, you will be prompted to set a new password immediately</li>
</ol>

<h2>Password Requirements</h2>
<ul>
<li>Minimum 10 characters</li>
<li>At least one uppercase letter (A&ndash;Z)</li>
<li>At least one lowercase letter (a&ndash;z)</li>
<li>At least one digit (0&ndash;9)</li>
</ul>

<h2>User Roles</h2>
<table>
<tr><th style="width:14%;">Role</th><th>What They Can Access</th></tr>
<tr><td><strong>Admin</strong></td>
    <td>Full access &mdash; all namespaces, user management, branding config, admin panel, all pages and features.</td></tr>
<tr><td><strong>Operator</strong></td>
    <td>All namespaces and features except user management and the Admin panel. Full observability.</td></tr>
<tr><td><strong>Client</strong></td>
    <td>Own namespace only &mdash; Usage dashboard, memory, agents (chat + catalog), outputs, tickets. Sees namespace branding.</td></tr>
<tr><td><strong>Viewer</strong></td>
    <td>Own namespace, read-only. Can view memory, outputs, and tickets but cannot write or run agents.</td></tr>
<tr><td><strong>Staff</strong></td>
    <td>Support role &mdash; only sees tickets assigned to them. Can self-assign open tickets. Memory, Workflows, and Admin are hidden.</td></tr>
</table>

<h2>Onboarding Modal (Client &amp; Viewer Roles) <span class="badge-new">v14.0</span></h2>
<p>The first time a <strong>client</strong> or <strong>viewer</strong> logs in, a 5-slide
interactive onboarding tour appears automatically. Admin and Operator roles skip this tour.</p>
<table>
<tr><th style="width:10%;">Slide</th><th style="width:25%;">Title</th><th>What It Covers</th></tr>
<tr><td>1</td><td>Welcome</td><td>What FaiykeOS is, your namespace, and how to navigate.</td></tr>
<tr><td>2</td><td>AI Agents</td><td>How to run agents via chat and catalog. How streaming works.</td></tr>
<tr><td>3</td><td>Memory</td><td>Writing memory entries, choosing categories, and how memory helps agents.</td></tr>
<tr><td>4</td><td>Tickets</td><td>Creating and tracking tickets. Email notification opt-in.</td></tr>
<tr><td>5</td><td>Usage Dashboard</td><td>KPIs, Pulse Score, AI activity feed, and memory summary.</td></tr>
</table>
<p>After dismissal, the tour does not appear again for that account. To reset it (e.g. for
re-training purposes), an admin can run:
<code>UPDATE users SET onboarding_done=0 WHERE username='alice'</code>.</p>

<h2>Self-Registration (if enabled by admin)</h2>
<ol>
<li>Click the <strong>Register</strong> tab on the login screen</li>
<li>Enter username, email, password, and select your namespace slug</li>
<li>Click <strong>Register</strong> &mdash; you are returned to the Login tab</li>
<li>Log in with your new credentials</li>
</ol>
<div class="note"><strong>Namespace slug:</strong> if you enter a namespace that does not exist
or is not the correct type, you will receive a generic error message. This is intentional &mdash;
FaiykeOS does not reveal which namespaces exist to unregistered users.</div>

<h2>Account Security</h2>
<ul>
<li><strong>Account lockout:</strong> 5 failed attempts triggers a 15-minute lockout (configurable).</li>
<li><strong>Session tokens:</strong> JWT access tokens expire after 60 minutes and are silently
    refreshed while you are active. The session window is 24 hours &mdash; after 24 hours of
    continuous use you will need to log in again.</li>
<li><strong>Theme toggle:</strong> a dark/light mode button sits in the bottom-left corner of
    every page. Your theme preference persists for the current session.</li>
</ul>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — DASHBOARD TOUR
# ═══════════════════════════════════════════════════════════════════════════════

def s5_dashboard() -> str:
    return """
<h1><a name="s5"></a>5 &mdash; Dashboard Tour</h1>

<h2>Navigation Quick Guide</h2>
<p>All pages are accessible from the left sidebar. What you see depends on your role.</p>
<table>
<tr><th style="width:22%;">Page</th><th style="width:18%;">Visible To</th><th>Purpose in Five Words</th></tr>
<tr><td><strong>Overview</strong></td><td>All roles</td><td>System health at a glance</td></tr>
<tr><td><strong>Usage</strong></td><td>Client, Viewer</td><td>Your namespace KPIs and score</td></tr>
<tr><td><strong>Agents</strong></td><td>All except Viewer (read)</td><td>Chat with AI assistants</td></tr>
<tr><td><strong>Memory</strong></td><td>All except Staff</td><td>Store and search knowledge</td></tr>
<tr><td><strong>Workflows</strong></td><td>Admin, Operator</td><td>Automate multi-step pipelines</td></tr>
<tr><td><strong>Client Vault</strong></td><td>Admin, Operator, Client</td><td>Namespaces, projects, files</td></tr>
<tr><td><strong>Outputs</strong></td><td>All except Staff</td><td>Browse saved AI responses</td></tr>
<tr><td><strong>Tickets</strong></td><td>All roles</td><td>Manage tasks and support</td></tr>
<tr><td><strong>Observability</strong></td><td>Admin, Operator</td><td>Quality, latency, cost, memory</td></tr>
<tr><td><strong>Settings</strong></td><td>Admin, Operator</td><td>Sync, email, environment info</td></tr>
<tr><td><strong>Admin Panel</strong></td><td>Admin only</td><td>Users, keys, audit, branding</td></tr>
</table>

<h2>Overview Page</h2>
<p>The home page provides a real-time snapshot of your system. KPIs are namespace-scoped:
admin/operator see global counts; client/viewer see only their namespace data.</p>
<table>
<tr><th style="width:30%;">Element</th><th>What It Shows</th></tr>
<tr><td>System Status strip</td><td>Green/red indicators for the API and database.</td></tr>
<tr><td>KPI Cards</td><td>Memory entries, registered agents, runs, workflows, outputs &mdash; scoped to your namespace.</td></tr>
<tr><td>Recent Events feed</td><td>Last 8 agent run results with agent name, namespace, timestamp, and quality score pill.</td></tr>
<tr><td>Quick Dispatch widget</td><td>Run any agent against any namespace with a one-off prompt directly from the Overview.</td></tr>
<tr><td>Auto-refresh toggle</td><td>Refreshes the live feed every 8 seconds &mdash; non-blocking (no session freeze in v17.2).</td></tr>
<tr><td>Error alert strip</td><td>Red banner when any recent run has failed.</td></tr>
<tr><td>Running-now indicator</td><td>Yellow banner listing agents currently executing.</td></tr>
</table>

<h3>Eval Score Pills</h3>
<table>
<tr><th style="width:20%;">Colour</th><th style="width:25%;">Score Range</th><th>Meaning</th></tr>
<tr><td><span class="pill-green">Green</span></td><td>4.0 &ndash; 5.0</td><td>High quality. Ready to use.</td></tr>
<tr><td><span class="pill-amber">Amber</span></td><td>2.5 &ndash; 3.9</td><td>Acceptable &mdash; review before sending to clients.</td></tr>
<tr><td><span class="pill-red">Red</span></td><td>0 &ndash; 2.4</td><td>Low quality &mdash; re-run with a more specific prompt.</td></tr>
</table>

<h2>Usage Page (Client &amp; Viewer Only) <span class="badge-new">v14.0</span></h2>
<p>A dedicated page giving client and viewer roles a full activity overview for their namespace.
This is the primary dashboard for clients who do not need the full admin interface.</p>

<h3>KPI Cards (30-Day Rolling)</h3>
<table>
<tr><th style="width:25%;">KPI</th><th>Description</th></tr>
<tr><td>AI Runs (30d)</td><td>Total agent runs in the last 30 days for this namespace.</td></tr>
<tr><td>Tokens In / Out</td><td>Total input and output tokens consumed.</td></tr>
<tr><td>Est. Cost (USD)</td><td>Estimated spend based on current claude-sonnet-4-6 pricing.</td></tr>
<tr><td>Avg Quality</td><td>Rolling average eval score across all scored runs.</td></tr>
<tr><td>Outputs</td><td>Total saved outputs for this namespace.</td></tr>
</table>

<h3>Namespace Pulse Score</h3>
<p>A composite 0&ndash;100 health score for the namespace, shown as a circular gauge. It tells
you at a glance how well the namespace is performing across all dimensions.</p>
<div class="gauge-block">
<strong>Formula:</strong> (Avg Eval Quality / 5 &times; 100 &times; 40%) + (Ticket Resolution Rate &times; 100 &times; 30%) + (Memory Freshness &times; 100 &times; 20%) + (Workflow Success Rate &times; 100 &times; 10%)<br/><br/>
<strong>Colour thresholds:</strong> &nbsp;
<span class="pill-green">&ge;75 Excellent/Good</span> &nbsp;
<span class="pill-amber">&ge;50 Fair</span> &nbsp;
<span class="pill-red">&lt;50 Needs Attention</span> &nbsp;
<span class="pill-gray">No data: Getting Started</span>
</div>

<h2>Agents, Memory, Workflows, Vault, Outputs, Tickets Pages</h2>
<p>Each of these pages is covered in its own section. Use the section numbers below as
your reference:</p>
<ul>
<li><strong>Agents</strong> &rarr; Section 6</li>
<li><strong>Memory</strong> &rarr; Section 7</li>
<li><strong>Workflows</strong> &rarr; Section 8</li>
<li><strong>Client Vault</strong> &rarr; Section 9</li>
<li><strong>Outputs</strong> &rarr; Section 10</li>
<li><strong>Tickets</strong> &rarr; Section 11</li>
<li><strong>Observability</strong> &rarr; Section 13</li>
</ul>

<h2>Page Persistence</h2>
<p>Your active page is stored in the URL query parameter <code>?page=PageName</code>.
Refreshing the browser returns you to the same page. Bookmarking a URL opens that page
directly after login.</p>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — WORKING WITH AI AGENTS
# ═══════════════════════════════════════════════════════════════════════════════

def s6_agents() -> str:
    return """
<h1><a name="s6"></a>6 &mdash; Working with AI Agents</h1>

<h2>The 12 Built-In Agents</h2>
<table>
<tr><th style="width:28%;">Agent</th><th style="width:14%;">Category</th><th>What It Does</th></tr>
<tr><td><strong>Analysis Agent</strong></td><td>Analysis</td>
    <td>Structured reports, key findings, and recommendations from raw data or injected context. Asks clarifying questions rather than fabricating results.</td></tr>
<tr><td><strong>Morning Briefing Agent</strong></td><td>Ops</td>
    <td>Synthesises overnight memory into a daily briefing: reminders, client updates, and priorities.</td></tr>
<tr><td><strong>Client Manager Agent</strong></td><td>Ops</td>
    <td>Per-client project status cards with deadlines, blockers, and action items. Will not use training knowledge for business-specific facts.</td></tr>
<tr><td><strong>Communications Agent</strong></td><td>Comms</td>
    <td>Client-facing emails, messages, and proposals &mdash; tone-matched to each client namespace.</td></tr>
<tr><td><strong>Memory Curator Agent</strong></td><td>System</td>
    <td>Reviews, deduplicates, and consolidates memory entries on request or on schedule.</td></tr>
<tr><td><strong>Meta Orchestrator Agent</strong></td><td>System</td>
    <td>Decomposes complex goals into ordered chains of agent invocations. Ideal for multi-step research and reporting tasks.</td></tr>
<tr><td><strong>QA Agent</strong></td><td>Engineering</td>
    <td>Code review against OWASP top-10, platform compatibility, and brand compliance rules.</td></tr>
<tr><td><strong>Research Agent</strong></td><td>Research</td>
    <td>Deep research with synthesis and source validation across a given topic or question.</td></tr>
<tr><td><strong>Scheduling Agent</strong></td><td>Ops</td>
    <td>Converts natural language scheduling requests into memory reminder entries with exact expiry dates.</td></tr>
<tr><td><strong>Transport Ops Agent</strong></td><td>Domain</td>
    <td>Domain-specific fleet and booking analysis &mdash; namespace-locked to prevent cross-client data access.</td></tr>
<tr><td><strong>Workflow Builder Agent</strong></td><td>System</td>
    <td>Converts plain-English automation descriptions into FaiykeOS workflow YAML definitions.</td></tr>
<tr><td><strong>Writing Agent</strong></td><td>Content</td>
    <td>Drafts reports, emails, and proposals with voice and tone matched to the active namespace brand.</td></tr>
</table>

<h2>Running an Agent &mdash; Three Ways</h2>

<h3>1. Chat Tab (Recommended for Iterative Work)</h3>
<p>Go to <strong>Agents &rarr; Chat</strong>. Select your agent and namespace from the dropdowns,
type your request, and press Enter. The response streams back in real time, token by token.
Follow up with additional messages &mdash; the conversation history is maintained for the session.</p>
<div class="tip"><strong>Best practice:</strong> be specific and structured. A prompt like
<em>&ldquo;Write a 2-page executive summary of Q2 analysis results for the mobile app project,
highlighting the top 3 risks and recommending next steps&rdquo;</em> will score significantly
higher than <em>&ldquo;write a report&rdquo;</em>.</div>

<h3>2. Catalog Tab (Browse and Launch)</h3>
<p>Go to <strong>Agents &rarr; Catalog</strong>. All 12 agents are shown as interactive cards
with their category, model, and description. <strong>Click any card</strong> to open the Chat tab
with that agent pre-selected &mdash; no dropdown hunting. Use the search box and category filter
to find a specific agent in a large registry.</p>

<h3>3. Quick Dispatch (From Overview)</h3>
<p>The Overview page Quick Dispatch widget lets you run any agent with a one-off prompt without
leaving the home page. Useful for fast queries that you do not need to continue as a conversation.</p>

<h2>Example Prompts by Agent</h2>
<table>
<tr><th style="width:28%;">Agent</th><th>Example Prompt</th></tr>
<tr><td>Analysis Agent</td>
    <td><em>&ldquo;Analyse the attached Q2 sales data. Identify the top 3 revenue trends and 2 risks. Format as a structured report with an executive summary.&rdquo;</em></td></tr>
<tr><td>Morning Briefing Agent</td>
    <td><em>&ldquo;Generate today's briefing. Include all reminders due this week, any client follow-ups, and outstanding ticket summaries.&rdquo;</em></td></tr>
<tr><td>Writing Agent</td>
    <td><em>&ldquo;Draft a 300-word proposal email to [Client Name] summarising our Q3 engagement plan. Professional tone, no jargon.&rdquo;</em></td></tr>
<tr><td>Research Agent</td>
    <td><em>&ldquo;Research the current market landscape for AI-powered logistics tools in sub-Saharan Africa. Synthesise key findings with sources.&rdquo;</em></td></tr>
<tr><td>QA Agent</td>
    <td><em>&ldquo;Review the attached Python code for OWASP Top-10 vulnerabilities and any Windows-compatibility issues. List findings by severity.&rdquo;</em></td></tr>
<tr><td>Scheduling Agent</td>
    <td><em>&ldquo;Add a reminder: follow up with Acme Corp about the proposal by next Friday at 10am.&rdquo;</em></td></tr>
<tr><td>Communications Agent</td>
    <td><em>&ldquo;Write a polite but firm chaser email to a client whose invoice is 14 days overdue. Keep it under 100 words.&rdquo;</em></td></tr>
<tr><td>Workflow Builder Agent</td>
    <td><em>&ldquo;Create a workflow that runs Research Agent on Mondays at 8am, passes the output to Writing Agent to produce a digest, then saves the result.&rdquo;</em></td></tr>
</table>

<h2>Prompt Engineering Tips</h2>
<div class="callout">
<strong>5 Tips for Higher-Scoring Responses</strong><br/><br/>
<strong>1. State the format.</strong> &ldquo;Format as a bullet list with a one-sentence summary at the top&rdquo; gives the agent a clear target.<br/><br/>
<strong>2. Set the length.</strong> &ldquo;Maximum 3 paragraphs&rdquo; or &ldquo;approx. 500 words&rdquo; prevents padding and improves conciseness scores.<br/><br/>
<strong>3. Provide context, not vague questions.</strong> Instead of &ldquo;What do you know about our clients?&rdquo;, write &ldquo;Based on the memory context, summarise the top priorities for each active client.&rdquo;<br/><br/>
<strong>4. Specify the audience.</strong> &ldquo;Written for a non-technical senior manager&rdquo; helps the agent choose the right level of detail.<br/><br/>
<strong>5. Use memory as ground truth.</strong> Write key facts to Memory first, then ask agents to &ldquo;use the information from memory&rdquo; &mdash; this maximises Factual Grounding scores.
</div>

<h2>Attaching Files &mdash; Images and Documents</h2>
<p>In the Chat tab, use the <strong>clip icon</strong> in the message bar to attach files inline,
or use the sidebar file uploader. Both are merged before the message is sent.</p>
<table>
<tr><th style="width:28%;">File Type</th><th>What Happens</th></tr>
<tr><td>Images (PNG, JPG, WebP, GIF)</td>
    <td>Encoded as base64 and sent as a visual content block. The agent sees the image directly via Claude's vision capability.</td></tr>
<tr><td>Markdown files (.md)</td>
    <td>Text is injected into your prompt as a fenced context block (<code>--- FILE: name.md ---</code>). Useful for sharing briefs and specs.</td></tr>
<tr><td>Plain text files (.txt)</td>
    <td>Same as Markdown &mdash; injected as a fenced context block.</td></tr>
</table>

<h2>Voice Input</h2>
<p>Click the microphone button in the Chat tab. Record your request (up to 30 seconds).
FaiykeOS transcribes locally using OpenAI Whisper &mdash; nothing sent externally. Review the
transcription, edit if needed, then submit. Requires <code>pip install openai-whisper</code>.
The model (~140 MB) downloads on first use.</p>

<h2>Rate Limits</h2>
<table>
<tr><th style="width:30%;">Endpoint</th><th>Limit</th><th>Response on Breach</th></tr>
<tr><td>Agent <code>/run</code></td><td>30 / minute per IP</td><td><code>429 Too Many Requests</code></td></tr>
<tr><td>Agent <code>/stream</code></td><td>20 / minute per IP</td><td><code>429 Too Many Requests</code></td></tr>
<tr><td>Workflow <code>/trigger</code></td><td>10 / minute per IP</td><td><code>429 Too Many Requests</code></td></tr>
</table>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — MEMORY SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def s7_memory() -> str:
    return """
<h1><a name="s7"></a>7 &mdash; Memory System</h1>

<h2>What Is Memory?</h2>
<p>Memory is FaiykeOS's persistent knowledge store. When you or an agent writes a memory entry,
it is saved to the database and automatically injected into every subsequent agent run in that
namespace. Agents remember facts, preferences, reminders, and tasks across sessions &mdash;
you never have to repeat yourself.</p>

<p>Under the hood, memory uses a three-layer retrieval stack: SQLite FTS5 for fast keyword search,
ChromaDB for semantic vector search, and a BM25 ranker for term-frequency scoring. All three are
merged using Reciprocal Rank Fusion (RRF) to surface the most relevant entries regardless of
whether your query uses exact keywords or conceptual language.</p>

<h2>Memory Categories</h2>
<table>
<tr><th style="width:16%;">Category</th><th>Use For</th><th>Example</th></tr>
<tr><td><strong>Fact</strong></td><td>Stable information about a client, project, or domain</td>
    <td><em>&ldquo;Client billing currency is GBP. VAT number: GB123456789.&rdquo;</em></td></tr>
<tr><td><strong>Preference</strong></td><td>Tone, style, format, or communication preferences</td>
    <td><em>&ldquo;Reports should open with an executive summary. Use bullet points for action items.&rdquo;</em></td></tr>
<tr><td><strong>Reminder</strong></td><td>Time-sensitive items with an expiry date</td>
    <td><em>&ldquo;Follow up on the Acme Corp proposal by 2026-07-01.&rdquo;</em></td></tr>
<tr><td><strong>Task</strong></td><td>Action items for agents or team members</td>
    <td><em>&ldquo;Prepare Q3 analysis deck before the board meeting on 2026-07-15.&rdquo;</em></td></tr>
</table>

<h2>Memory Entry Templates</h2>

<div class="example">
<strong>Template 1 &mdash; Client Profile Fact</strong><br/>
Key: <code>client_profile_acme</code> | Category: fact<br/>
Value: <em>Acme Corp is a Lagos-based logistics company with 45 staff. Primary contact: James Brown
(james@acmecorp.com, +234 801 234 5678). Billing in USD, Net-30 terms. SLA: P1 response within 4 hours.</em>
</div>

<div class="example">
<strong>Template 2 &mdash; Communication Preference</strong><br/>
Key: <code>pref_report_format</code> | Category: preference<br/>
Value: <em>All client-facing reports must begin with a one-paragraph executive summary. Use numbered
lists for findings. Avoid jargon. Maximum 2 pages unless explicitly requested otherwise.</em>
</div>

<div class="example">
<strong>Template 3 &mdash; Deadline Reminder</strong><br/>
Key: <code>reminder_q3_deck</code> | Category: reminder | TTL: 30 days<br/>
Value: <em>Q3 analysis deck must be ready by 2026-07-15 for the board meeting. Assign to Analysis Agent.</em>
</div>

<div class="example">
<strong>Template 4 &mdash; Technical Constraint</strong><br/>
Key: <code>tech_stack_constraints</code> | Category: fact<br/>
Value: <em>Production stack: Python 3.11, Windows 10, waitress WSGI (no gunicorn). Never use Unix-only
commands. Use semicolons not &amp;&amp; in shell scripts. All file I/O must specify encoding=utf-8.</em>
</div>

<h2>Writing a Memory Entry</h2>
<ol>
<li>Go to the <strong>Memory</strong> page &rarr; click <strong>Add Entry</strong></li>
<li>Fill in: key (short unique identifier), value (full content), category, optional TTL in days, confidence (0.0&ndash;1.0)</li>
<li>Click <strong>Save</strong></li>
</ol>
<div class="warn"><strong>Size limit (v17.2):</strong> memory entry values are capped at <strong>64 KB</strong>.
Entries larger than this are rejected with <code>422 Unprocessable Entity</code>. Split large documents
into multiple entries or upload them as context files in the Client Vault.</div>

<h2>Searching Memory</h2>
<p>Full-text search across keys and values. Toggle <strong>Hybrid Search</strong> to activate
BM25 + semantic vector retrieval for conceptual queries &mdash; for example, searching
<em>&ldquo;client payment terms&rdquo;</em> finds entries about invoicing even without exact keyword match.</p>

<h2>How Context Injection Works</h2>
<ol>
<li>Hybrid search retrieves the top N entries most relevant to your prompt using BM25 + ChromaDB RRF scoring</li>
<li>A namespace summary is prepended (cached 5 minutes &mdash; no DB hit per request)</li>
<li>The tiered context builder selects entries by recency and confidence, capping at ~3,000 characters to reduce token usage by approximately 40%</li>
<li>Contextual prefixes (e.g. <em>CRITICAL CONSTRAINT:</em>) are applied per entry where set</li>
<li>The assembled context block is injected into the agent system prompt before your message</li>
</ol>
<div class="note"><strong>Timeout protection (v17.2):</strong> if ChromaDB is slow, the context
builder times out after 4 seconds and falls back to fast FTS-only context. The agent still runs.</div>

<h2>Memory Consolidation</h2>
<p>An automated job runs every 4 hours. It clusters similar entries, uses Claude Haiku to synthesise
each cluster into one concise entry, and archives the originals (<code>archived=1</code> &mdash; never
hard-deleted). Trigger immediately: <strong>Observability &rarr; Memory Health &rarr; Trigger Consolidation</strong>.</p>

<div class="tip"><strong>Write memory in full sentences.</strong> <em>&ldquo;Primary contact is James Brown,
james@example.com, +44 7700 900000. He prefers WhatsApp for urgent matters.&rdquo;</em> is far more
useful to an agent than <em>&ldquo;james contact&rdquo;</em>.</div>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — WORKFLOWS & AUTOMATION
# ═══════════════════════════════════════════════════════════════════════════════

def s8_workflows() -> str:
    return f"""
<h1><a name="s8"></a>8 &mdash; Workflows &amp; Automation</h1>

<h2>What Are Workflows?</h2>
<p>Workflows are multi-step AI pipelines that chain agent calls sequentially, passing the output
of one step as input to the next. They run on a cron schedule, manually via the dashboard, or
from an external system via an HMAC-secured webhook. Workflow management requires Admin or Operator access.</p>

<h2>Built-In Workflows</h2>
<table>
<tr><th style="width:28%;">Workflow</th><th>What It Does</th><th style="width:18%;">Default Schedule</th></tr>
<tr><td><strong>Morning Briefing</strong></td>
    <td>Synthesises overnight memory into a structured daily briefing with reminders and priorities.</td><td>Mon&ndash;Fri 07:00</td></tr>
<tr><td><strong>Memory Curation</strong></td>
    <td>Memory Curator Agent deduplicates and consolidates entries namespace-wide.</td><td>Every 4 hours</td></tr>
<tr><td><strong>Research Digest</strong></td>
    <td>Research Agent deep-dive on a configured topic, producing a structured digest.</td><td>On demand</td></tr>
<tr><td><strong>Client Report</strong></td>
    <td>Client Manager Agent generates status cards for all active projects.</td><td>Weekly</td></tr>
<tr><td><strong>Analysis Run</strong></td>
    <td>Analysis Agent processes queued data and produces structured findings.</td><td>On demand</td></tr>
<tr><td><strong>QA Sweep</strong></td>
    <td>QA Agent reviews recent outputs against quality and compliance rules.</td><td>On demand</td></tr>
<tr><td><strong>Meta-Orchestrate</strong></td>
    <td>Meta Orchestrator decomposes a complex goal into a chain of agent calls and executes them.</td><td>On demand</td></tr>
</table>

<h2>Running a Workflow Manually</h2>
<ol>
<li>Go to the <strong>Workflows</strong> page</li>
<li>Find the workflow card &rarr; click <strong>Run Now</strong></li>
<li>The run appears in Recent Events on the Overview page</li>
<li>Expand the workflow card to see the step-by-step run log</li>
</ol>

<h2>Webhook Triggers</h2>
<p>Any workflow can be triggered by an external system &mdash; Zapier, Make, n8n, or a custom
script &mdash; without a login token. The endpoint is secured by an HMAC secret instead of JWT.</p>

<h3>Enabling a Webhook</h3>
<ol>
<li>Workflows page &rarr; <strong>Webhooks</strong> tab &rarr; select workflow &rarr; <strong>Enable Webhook</strong></li>
<li>A unique URL and HMAC secret are generated. <strong>The secret is shown once &mdash; store it safely.</strong></li>
</ol>

<h3>Calling the Webhook</h3>
<pre>curl -X POST {API_URL}/api/v1/workflows/morning-briefing/trigger \\
  -H "X-Webhook-Secret: your-hmac-secret" \\
  -H "Content-Type: application/json" \\
  -d '{{"context": {{"namespace": "faiyke-ai", "topic": "weekly review"}}}}'</pre>
<p>Rate limit: 10 / min per IP. Request body limited to 64 KB.</p>

<h3>Zapier / Make Integration Example</h3>
<div class="callout">
<strong>Scenario:</strong> Trigger Client Report whenever a new row appears in Google Sheets.<br/><br/>
In <strong>Zapier:</strong> Trigger = &ldquo;New Row in Google Sheets&rdquo; &rarr; Action = &ldquo;Webhooks by Zapier &rarr; POST&rdquo; &rarr;
URL: <code>{API_URL}/api/v1/workflows/client-report/trigger</code>,
Header: <code>X-Webhook-Secret: your-secret</code>,
Body: <code>{{"context": {{"namespace": "faiyke-ai"}}}}</code><br/><br/>
In <strong>Make:</strong> use the HTTP &rarr; Make a Request module with the same URL, headers, and body.
</div>

<h2>Building Your First Automation: Morning Briefing</h2>
<ol>
<li>Write memory entries covering active projects, reminders, and client priorities</li>
<li>Go to <strong>Workflows</strong> &rarr; find Morning Briefing &rarr; check the schedule (default: Mon&ndash;Fri 07:00)</li>
<li>Click <strong>Run Now</strong> to test immediately. Output appears in Outputs and the Recent Events feed</li>
<li>Review quality in <strong>Observability &rarr; Quality Scores</strong>. If Factual Grounding is low, add more specific memory entries</li>
<li>Enable email notifications in Settings to receive the briefing by email</li>
</ol>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — CLIENT VAULT
# ═══════════════════════════════════════════════════════════════════════════════

def s9_vault() -> str:
    return """
<h1><a name="s9"></a>9 &mdash; Client Vault</h1>

<h2>What Is the Client Vault?</h2>
<p>The Client Vault is where namespaces, projects, and context files are managed. Every piece
of data in FaiykeOS &mdash; memory entries, agent runs, outputs, tickets &mdash; belongs to a
namespace. Nothing crosses namespace boundaries, making it safe to serve multiple clients on
one installation.</p>

<h2>Namespaces</h2>
<p>The Client Vault page shows all namespaces you have access to, including namespace name,
slug, description, icon, workspace statistics (number of context files, total size), active
project count, and branding preview.</p>

<h2>Projects</h2>
<ul>
<li>View name, description, and creation date per project</li>
<li>Update status: <strong>Active</strong> / <strong>Paused</strong> / <strong>Archived</strong></li>
<li>Associate outputs and tickets with a project for easier reporting</li>
</ul>

<h2>Context Files</h2>
<p>Context files are documents uploaded per namespace that are automatically injected into every
agent system prompt for that namespace. Use them for persistent reference material:</p>
<ul>
<li>Brand guidelines and tone-of-voice documents</li>
<li>Standard operating procedures and compliance rules</li>
<li>Client briefs or background documents</li>
<li>Technical specifications agents should always be aware of</li>
</ul>
<p>Supported formats: plain text (.txt), Markdown (.md), PDF.</p>
<div class="note"><strong>Keep context files concise.</strong> Large files increase token usage on
every agent call. Split large documents into smaller topical files (e.g. <code>brand-tone.md</code>,
<code>client-sla.md</code>) so each file only adds relevant tokens.</div>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — OUTPUTS & REPORTS
# ═══════════════════════════════════════════════════════════════════════════════

def s10_outputs() -> str:
    return """
<h1><a name="s10"></a>10 &mdash; Outputs &amp; Reports</h1>

<h2>What Are Outputs?</h2>
<p>Every time an agent produces a response with <code>save_output: true</code> (the default for
Chat and workflow runs), the full text is saved to the database and filesystem with automatic tags:
agent name, namespace, output type, and timestamp. Outputs are the searchable, exportable record
of everything your AI team has produced.</p>

<h2>Browsing and Searching</h2>
<ul>
<li>Full-text search across all output content</li>
<li>Filter by namespace, output type (report / summary / plan / analysis / code / other), and date range</li>
<li>Outputs sorted newest-first; click any entry to expand and read the full content</li>
<li>Timestamps displayed as <code>YYYY-MM-DD HH:MM</code> in all views</li>
</ul>

<h2>Exporting</h2>
<table>
<tr><th style="width:20%;">Format</th><th>Notes</th></tr>
<tr><td><strong>Markdown</strong></td>
    <td>Raw text with Markdown formatting preserved. Always available. Opens in any text editor.</td></tr>
<tr><td><strong>PDF</strong></td>
    <td>Rendered PDF with FaiykeOS branding. Requires wkhtmltopdf installed on the server.</td></tr>
</table>

<h2>Soft-Delete (v17.2)</h2>
<p>Deleted outputs are <strong>soft-deleted</strong>: a <code>deleted_at</code> timestamp is written
to the record rather than removing the row. The output immediately disappears from all views. If
Supabase sync is enabled, the deletion propagates to the cloud backup. Hard-delete is not available
through the UI &mdash; this preserves audit integrity.</p>

<div class="tip"><strong>Output management best practices:</strong><br/>
1. Use type and date filters to find low-quality or outdated outputs before bulk deleting.<br/>
2. Export important outputs to Markdown as an extra backup before deleting.<br/>
3. Red-pill outputs (eval score below 2.5) are good candidates for re-run with a refined prompt.</div>

<h2>Bulk Delete</h2>
<p>Select outputs using checkboxes, then click <strong>Delete Selected</strong>. Soft-deletes all
selected in one operation. Maximum 200 entries per bulk operation. Admin and Operator roles only.</p>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — TICKETING SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def s11_tickets() -> str:
    return """
<h1><a name="s11"></a>11 &mdash; Ticketing System</h1>

<h2>Overview</h2>
<p>FaiykeOS includes a full support and task-management ticketing system with SLA tiers,
threaded comments, bulk operations, and automatic email notifications. All roles can view
tickets relevant to them; create and assign permissions vary by role.</p>

<h2>Priority and SLA Tiers</h2>
<table>
<tr><th style="width:8%;">Priority</th><th style="width:18%;">Label</th><th>Meaning</th></tr>
<tr><td>P1</td><td><strong>Critical</strong></td><td>System down or blocking all operations. Immediate response required.</td></tr>
<tr><td>P2</td><td><strong>High</strong></td><td>Major issue with significant business impact. Same-day response expected.</td></tr>
<tr><td>P3</td><td><strong>Medium</strong></td><td>Important but not blocking. Response within 2 business days.</td></tr>
<tr><td>P4</td><td><strong>Low</strong></td><td>Enhancement, minor issue, or nice-to-have. Best effort.</td></tr>
</table>

<h2>Ticket Lifecycle</h2>
<pre>Open  &rarr;  In Progress  &rarr;  Resolved  &rarr;  Closed</pre>

<h2>Creating a Ticket</h2>
<ol>
<li>Go to <strong>Tickets</strong> page &rarr; click <strong>New Ticket</strong></li>
<li>Fill in: title, description, priority, namespace, and optionally assign users</li>
<li>Click <strong>Create</strong> &mdash; assignees receive an email notification if SMTP is configured</li>
</ol>

<h2>Role Permissions</h2>
<table>
<tr><th style="width:15%;">Role</th><th>Can Create</th><th>Can Assign</th><th>Can Bulk Delete</th></tr>
<tr><td>Admin / Operator</td><td>Yes</td><td>Any user</td><td>Yes</td></tr>
<tr><td>Client</td><td>Yes</td><td>No</td><td>No</td></tr>
<tr><td>Staff</td><td>No</td><td>Self-assign only</td><td>No</td></tr>
<tr><td>Viewer</td><td>No</td><td>No</td><td>No</td></tr>
</table>

<h2>Email Notifications <span class="badge-new">v14.0</span></h2>
<table>
<tr><th style="width:38%;">Event</th><th>Who Receives It</th></tr>
<tr><td>Ticket created with assignees</td><td>All assigned users receive an assignment email</td></tr>
<tr><td>Ticket resolved or closed</td><td>Ticket creator receives a resolution/closure email</td></tr>
</table>
<p>Configure SMTP in <strong>Settings &rarr; Email Notifications</strong>. Use the <strong>Test Send</strong>
button before enabling live notifications.</p>
<div class="note"><strong>Gmail:</strong> use an App Password (not your account password) if 2FA is enabled.
Generate at <em>myaccount.google.com &rarr; Security &rarr; App Passwords</em>.</div>

<h2>Comments and Stats</h2>
<p>Click the <strong>Comments</strong> toggle on any ticket to load threaded comments on demand.
The Stats Panel at the top of the Tickets page shows counts by status and priority.</p>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — QUALITY SCORING
# ═══════════════════════════════════════════════════════════════════════════════

def s12_quality() -> str:
    return """
<h1><a name="s12"></a>12 &mdash; Quality Scoring</h1>

<h2>How It Works</h2>
<p>Every agent run is automatically scored by Claude Haiku on 4 dimensions. Scoring happens
asynchronously in a background thread pool &mdash; it never adds latency to your response.
Scores typically appear 5&ndash;15 seconds after a run completes.</p>

<h2>Scoring Dimensions and Formula</h2>
<table>
<tr><th style="width:25%;">Dimension</th><th style="width:10%;">Scale</th><th style="width:10%;">Weight</th><th>What It Measures</th></tr>
<tr><td><strong>Task Completion</strong></td><td>0&ndash;5</td><td>40%</td>
    <td>Did the output fully address the prompt and all sub-questions?</td></tr>
<tr><td><strong>Factual Grounding</strong></td><td>0&ndash;5</td><td>30%</td>
    <td>Are claims grounded in the injected memory context? Penalises hallucinated facts.</td></tr>
<tr><td><strong>Conciseness</strong></td><td>0&ndash;5</td><td>20%</td>
    <td>Is the output the right length? Penalises padding and repetition.</td></tr>
<tr><td><strong>Safety</strong></td><td>pass/fail</td><td>10%</td>
    <td>Does the output contain harmful content? A fail caps the score at 1.0.</td></tr>
</table>
<p><strong>Score</strong> = (Task &times; 0.40) + (Factual &times; 0.30) + (Concise &times; 0.20) + (Safety &times; 0.10)</p>

<h2>Rubric Notes &mdash; Scope Refusals (v17.0)</h2>
<div class="callout">
<strong>Correct scope refusals score 5.0 on Task Completion, not 0.</strong><br/><br/>
Agents that decline out-of-scope requests without fabricating anything are performing exactly as
designed. An analysis agent that says <em>&ldquo;I need the actual data before I can produce findings
&mdash; please provide the dataset&rdquo;</em> scores Task Completion = 5.0 and Factual Grounding = 5.0.<br/><br/>
When no factual claims are made at all, Factual Grounding = 5.0. Agents are never penalised for honesty.
</div>

<h2>Where Scores Appear</h2>
<ul>
<li><strong>Agents &rarr; Run History:</strong> colour-coded pill per run</li>
<li><strong>Overview page:</strong> pill on each recent event in the live feed</li>
<li><strong>Chat tab:</strong> badge below each assistant response (~10s delay)</li>
<li><strong>Usage Dashboard:</strong> 30-day average in the Avg Quality KPI card</li>
<li><strong>Observability &rarr; Quality Scores:</strong> per-agent averages, distribution, dimension breakdown</li>
</ul>

<h2>Improving Scores</h2>
<table>
<tr><th style="width:30%;">Low Score On...</th><th>Action</th></tr>
<tr><td>Task Completion</td>
    <td>Be more specific. State exactly what you want, in what format, at what length. Name all sub-questions.</td></tr>
<tr><td>Factual Grounding</td>
    <td>Add more relevant facts to Memory before running. More context = higher grounding score.</td></tr>
<tr><td>Conciseness</td>
    <td>Add explicit constraints: <em>&ldquo;be concise&rdquo;</em> or <em>&ldquo;maximum 3 paragraphs&rdquo;</em>.</td></tr>
<tr><td>Safety</td>
    <td>Review the output. Adjust the prompt. Contact your admin if unexpected content appears.</td></tr>
</table>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13 — OBSERVABILITY
# ═══════════════════════════════════════════════════════════════════════════════

def s13_observability() -> str:
    return """
<h1><a name="s13"></a>13 &mdash; Observability</h1>

<p>Available to <strong>Admin</strong> and <strong>Operator</strong> roles only. Five sub-tabs
covering quality, speed, cost, memory health, and cross-namespace usage.</p>

<h2>Quality Scores Tab</h2>
<ul>
<li>Per-agent average eval scores in a ranked table</li>
<li>Score distribution chart (0.5-step buckets across all runs)</li>
<li>Dimension breakdown: task completion, factual grounding, conciseness, safety</li>
<li>Red alert when any agent's average drops below 2.5</li>
</ul>

<h2>Latency Tab</h2>
<p>Latency is measured from request receipt to final token delivered.</p>
<ul>
<li>p50, p95, and p99 latency across all runs</li>
<li>Per-agent average latency table sorted by slowest first</li>
<li>Time-series chart over the past 7 days</li>
</ul>
<table>
<tr><th>Response length</th><th>Typical latency (claude-sonnet-4-6)</th></tr>
<tr><td>Short (under 200 tokens)</td><td>2&ndash;6 seconds</td></tr>
<tr><td>Medium (200&ndash;800 tokens)</td><td>6&ndash;20 seconds</td></tr>
<tr><td>Long (800+ tokens)</td><td>20&ndash;60 seconds</td></tr>
</table>

<h2>Token Cost Tab</h2>
<ul>
<li>Total input and output token counts across all runs</li>
<li>Estimated USD cost based on current claude-sonnet-4-6 pricing</li>
<li>Per-agent breakdown: tokens used, cost, run count, average cost per run</li>
</ul>
<div class="note">Token cost estimates are approximate. Check anthropic.com/pricing for current rates.</div>

<h2>Memory Health Tab</h2>
<ul>
<li>Entry counts per namespace: total, active, consolidated, expired</li>
<li>Storage size estimate per namespace</li>
<li><strong>Trigger Consolidation</strong> button &mdash; runs the job immediately</li>
<li>Visual indicator when any namespace has not been consolidated in over 24 hours</li>
</ul>

<h2>Namespace Usage Tab <span class="badge-new">v15.0</span></h2>
<p>Cross-namespace comparison for admins and operators. For each namespace:</p>
<ul>
<li>Total agent runs, input tokens, output tokens, estimated USD cost</li>
<li>Average quality score and memory entry count</li>
<li>Stacked bar chart comparing token consumption across all namespaces</li>
</ul>
<p>Based on up to 500 most recent runs. Identifies which namespaces are most active and
where token spend is concentrated.</p>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 14 — NAMESPACE BRANDING & CUSTOMISATION
# ═══════════════════════════════════════════════════════════════════════════════

def s14_branding() -> str:
    return """
<h1><a name="s14"></a>14 &mdash; Namespace Branding &amp; Customisation <span class="badge-new">v14.0</span></h1>

<h2>Overview</h2>
<p>FaiykeOS supports full per-namespace white-labeling. Each namespace can have its own company
name, icon, primary colour, accent colour, and background colour. Clients see their brand on the
login screen, sidebar, and dashboard headers &mdash; creating a personalised experience without
any code changes. Branding is configured by the <strong>Admin</strong> role only.</p>

<h2>Available Brand Settings</h2>
<table>
<tr><th style="width:26%;">Setting</th><th>Description</th><th style="width:20%;">Example</th></tr>
<tr><td><strong>Company Name</strong></td>
    <td>Replaces &ldquo;FaiykeOS&rdquo; in the sidebar header for users of this namespace</td>
    <td>Acme Corp AI</td></tr>
<tr><td><strong>Icon Emoji</strong></td>
    <td>Emoji shown next to the company name in the sidebar</td>
    <td>&#128170; &#128640; &#127757;</td></tr>
<tr><td><strong>Primary Colour</strong></td>
    <td>Used for buttons, active highlights, headings, and progress bars</td>
    <td>#1565C0 (blue)</td></tr>
<tr><td><strong>Accent Colour</strong></td>
    <td>Used for hover states, secondary actions, and links</td>
    <td>#42A5F5 (light blue)</td></tr>
<tr><td><strong>Background Colour</strong></td>
    <td>Default page background for all users in this namespace</td>
    <td>#F0F4FF</td></tr>
</table>

<h2>Where to Configure</h2>
<p><strong>Admin Panel &rarr; Branding</strong> tab (7th tab). Select the namespace from the
dropdown, adjust settings, and click <strong>Save</strong>. A live preview panel renders sample
text, a button, and a card in the chosen colours with auto-computed contrast text.</p>

<div class="warn"><strong>XSS protection (v17.2):</strong> company name and icon values are
HTML-escaped before rendering. Do not attempt to inject HTML or script tags &mdash; they will
be rendered as literal text.</div>

<h2>Where Branding Appears</h2>
<ul>
<li><strong>Login screen:</strong> company name, icon, and background colour applied before login</li>
<li><strong>Sidebar:</strong> company name and icon replace &ldquo;FaiykeOS&rdquo; header</li>
<li><strong>Dashboard headers:</strong> primary colour used for heading accents and pills</li>
<li><strong>Buttons and highlights:</strong> accent colour used for interactive elements</li>
</ul>

<h2>Resetting to Default</h2>
<p>Click <strong>Reset to Defaults</strong> to restore FaiykeOS green (<code>#407E3C</code>)
and white for that namespace. Takes effect on next page load for all users in the namespace.</p>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 15 — CUSTOM BACKGROUND COLORS
# ═══════════════════════════════════════════════════════════════════════════════

def s15_bgcolor() -> str:
    return """
<h1><a name="s15"></a>15 &mdash; Custom Background Colors <span class="badge-new">v14.0</span></h1>

<h2>Overview</h2>
<p>Any logged-in user can change the page background colour for their current session using a
colour picker in the sidebar. Text, surface, and border colours are automatically derived from
the chosen background to ensure readability in all conditions.</p>

<h2>How to Set a Custom Background</h2>
<ol>
<li>Log in and look at the left sidebar</li>
<li>Find the <strong>Background color</strong> expander and click to expand</li>
<li>Check the <strong>Use custom background</strong> checkbox &mdash; a colour picker appears</li>
<li>Choose any colour; the page updates immediately with auto-derived text and surface colours</li>
</ol>

<h2>Auto-Derived Colour Logic</h2>
<table>
<tr><th style="width:35%;">Background Luminance</th><th>Derived Text Colour</th><th>Derived Surface</th></tr>
<tr><td>Light (luminance &gt; 0.5)</td><td><code>#1A1A1A</code> (near-black)</td><td>Slightly darker shade</td></tr>
<tr><td>Dark (luminance &le; 0.5)</td><td><code>#E8F5E8</code> (light green-white)</td><td>Slightly lighter shade</td></tr>
</table>

<h2>Priority Order</h2>
<table>
<tr><th style="width:5%;">#</th><th style="width:25%;">Source</th><th>Notes</th></tr>
<tr><td>1</td><td>Personal override</td><td>Colour chosen in the sidebar picker. Session-only; resets on logout.</td></tr>
<tr><td>2</td><td>Namespace default</td><td>Background set by admin in Admin &rarr; Branding. Persists for all namespace users.</td></tr>
<tr><td>3</td><td>Theme default</td><td>Standard dark/light theme background.</td></tr>
</table>

<div class="tip"><strong>Accessibility:</strong> choose backgrounds with sufficient contrast from
your primary colour. Saturated pastels and deep rich tones work best. Avoid mid-range greys.</div>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 16 — ADVANCED FEATURES
# ═══════════════════════════════════════════════════════════════════════════════

def s16_advanced() -> str:
    return f"""
<h1><a name="s16"></a>16 &mdash; Advanced Features</h1>

<h2>Multi-Turn Conversation History</h2>
<p>Each agent in Chat mode maintains its own conversation session stored in the database.
Refreshing the page does not lose the conversation within the same login session. Click
<strong>Clear Conversation</strong> when moving to a new topic to remove stale context.</p>

<h2>Image, Screenshot and Document Analysis</h2>
<p>Attach files using the clip icon in the message bar or the sidebar uploader. Both sources
are merged before dispatch.</p>
<table>
<tr><th style="width:28%;">Type</th><th>How Sent to Agent</th></tr>
<tr><td>PNG, JPG, WebP, GIF</td><td>Base64 content block &mdash; agent sees image directly via Claude vision API</td></tr>
<tr><td>.md, .txt</td><td>Injected as fenced text block in prompt (<code>--- FILE: name.md ---</code>)</td></tr>
</table>
<p>Practical image use cases:</p>
<ul>
<li>Summarise or critique a report screenshot with Analysis Agent</li>
<li>Interpret chart trends &mdash; attach chart image, ask for findings</li>
<li>UI compliance check &mdash; attach a screenshot, ask QA Agent to review</li>
<li>Extract data from a document photo or scanned form</li>
</ul>

<h2>Voice Input</h2>
<p>Requires <code>pip install openai-whisper</code>. First use downloads the ~140 MB model.
All transcription is done locally &mdash; no audio is sent to external services.</p>

<h2>Namespace Pulse Score</h2>
<div class="gauge-block">
<strong>Formula:</strong><br/>
&nbsp; (Average eval quality / 5) &times; 100 &times; 0.40<br/>
&nbsp; + (Ticket resolution rate) &times; 100 &times; 0.30<br/>
&nbsp; + (Memory freshness score) &times; 100 &times; 0.20<br/>
&nbsp; + (Workflow success rate) &times; 100 &times; 0.10<br/><br/>
<span class="pill-green">&ge;75 Excellent/Good</span> &nbsp;
<span class="pill-amber">&ge;50 Fair</span> &nbsp;
<span class="pill-red">&lt;50 Needs Attention</span> &nbsp;
<span class="pill-gray">No data: Getting Started</span>
</div>

<h2>MCP Tool Server <span class="badge-new">v12.0</span></h2>
<p>The Model Context Protocol server exposes all 12 FaiykeOS agents as native tools to any
MCP-compatible AI client.</p>
<pre>.\\scripts\\start_mcp.ps1     # starts on port 5100 (localhost only)</pre>
<div class="warn"><strong>v17.2 security change:</strong> the MCP server now binds to
<code>127.0.0.1</code> only. It is not accessible from other machines on the network by
design. Use an SSH tunnel or VPN if remote access is required.</div>

<h3>Connecting Claude Desktop</h3>
<p>Add to <code>%APPDATA%\\Claude\\claude_desktop_config.json</code>:</p>
<pre>{{
  "mcpServers": {{
    "claudeos": {{
      "url": "http://localhost:5100/mcp"
    }}
  }}
}}</pre>
<p>Restart Claude Desktop. All 12 agents appear as available tools in the tool picker.</p>

<h2>A2A Agent Cards</h2>
<p>Each agent exposes a machine-readable capability card for agent-to-agent discovery:</p>
<pre>GET {API_URL}/api/v1/agents/writing-agent/.well-known/agent.json</pre>
<p>The card describes name, description, input/output schema, and streaming / multi-turn
capabilities. External AI orchestrators use this to auto-discover and delegate to FaiykeOS agents.</p>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 17 — API REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════

def s17_api() -> str:
    return f"""
<h1><a name="s17"></a>17 &mdash; API Reference</h1>

<p>The FaiykeOS REST API runs at <strong>{API_URL}/api/v1/</strong>. All endpoints require
authentication (JWT Bearer or X-API-Key) except <code>/health</code> and webhook triggers.</p>

<h2>Authentication</h2>

<h3>JWT Login Flow</h3>
<pre># 1. Login
curl -X POST {API_URL}/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{{"username":"your_user","password":"your_pass"}}'

# Response
{{"access_token":"eyJ...","refresh_token":"eyJ...","user":{{"role":"operator"}}}}

# 2. Use access token
curl {API_URL}/api/v1/agents -H "Authorization: Bearer eyJ..."

# 3. Refresh (access token expires after 60 minutes; session window: 24 hours)
curl -X POST {API_URL}/api/v1/auth/refresh \\
  -H "Authorization: Bearer &lt;refresh_token&gt;"</pre>

<h3>API Key (Scripts and Automation)</h3>
<pre>curl {API_URL}/api/v1/memory -H "X-API-Key: your_api_key"</pre>

<h2>Core Endpoint Reference</h2>
<table>
<tr><th style="width:10%;">Method</th><th style="width:44%;">Endpoint</th><th>Description</th></tr>
<tr><td>POST</td><td><code>/auth/login</code></td><td>Login &mdash; returns access + refresh tokens</td></tr>
<tr><td>POST</td><td><code>/auth/refresh</code></td><td>Renew access token using refresh token</td></tr>
<tr><td>POST</td><td><code>/auth/logout</code></td><td>Revoke current session</td></tr>
<tr><td>GET</td><td><code>/auth/me</code></td><td>Current user info and role</td></tr>
<tr><td>GET</td><td><code>/health</code></td><td>Public health check (no auth required)</td></tr>
<tr><td>GET</td><td><code>/memory</code></td><td>List memory entries (filterable by namespace, category)</td></tr>
<tr><td>POST</td><td><code>/memory</code></td><td>Write a memory entry (max 64 KB value)</td></tr>
<tr><td>DELETE</td><td><code>/memory/&lt;id&gt;</code></td><td>Soft-delete a memory entry</td></tr>
<tr><td>DELETE</td><td><code>/memory/bulk</code></td><td>Bulk soft-delete (max 200 entries)</td></tr>
<tr><td>GET</td><td><code>/memory/hybrid-search</code></td><td>Hybrid BM25+vector search with RRF reranking</td></tr>
<tr><td>POST</td><td><code>/memory/consolidate</code></td><td>Trigger memory consolidation immediately</td></tr>
<tr><td>GET</td><td><code>/agents</code></td><td>List all registered agents</td></tr>
<tr><td>POST</td><td><code>/agents/&lt;name&gt;/run</code></td><td>Dispatch async agent run &mdash; 30/min limit</td></tr>
<tr><td>GET</td><td><code>/agents/runs/&lt;id&gt;</code></td><td>Poll run status and output</td></tr>
<tr><td>GET</td><td><code>/agents/runs</code></td><td>List all runs (filterable)</td></tr>
<tr><td>GET</td><td><code>/agents/&lt;name&gt;/stream</code></td><td>SSE streaming &mdash; 20/min limit</td></tr>
<tr><td>GET</td><td><code>/agents/&lt;name&gt;/.well-known/agent.json</code></td><td>A2A Agent Card</td></tr>
<tr><td>GET</td><td><code>/agents/&lt;name&gt;/conversations</code></td><td>List multi-turn conversation sessions</td></tr>
<tr><td>POST</td><td><code>/agents/&lt;name&gt;/conversations</code></td><td>Create a new conversation session</td></tr>
<tr><td>GET</td><td><code>/outputs</code></td><td>List outputs (filterable by namespace, type, date)</td></tr>
<tr><td>DELETE</td><td><code>/outputs/&lt;id&gt;</code></td><td>Soft-delete a single output</td></tr>
<tr><td>DELETE</td><td><code>/outputs/bulk</code></td><td>Bulk soft-delete outputs (max 200)</td></tr>
<tr><td>GET</td><td><code>/tickets</code></td><td>List tickets</td></tr>
<tr><td>POST</td><td><code>/tickets</code></td><td>Create a ticket (triggers email if SMTP configured)</td></tr>
<tr><td>PUT</td><td><code>/tickets/&lt;id&gt;</code></td><td>Update ticket (triggers email on resolve/close)</td></tr>
<tr><td>DELETE</td><td><code>/tickets/bulk</code></td><td>Bulk delete tickets</td></tr>
<tr><td>GET</td><td><code>/tickets/stats</code></td><td>Ticket counts by status and priority</td></tr>
<tr><td>GET</td><td><code>/workflows</code></td><td>List workflows</td></tr>
<tr><td>POST</td><td><code>/workflows/&lt;name&gt;/run</code></td><td>Trigger workflow (JWT / Admin or Operator)</td></tr>
<tr><td>POST</td><td><code>/workflows/&lt;name&gt;/trigger</code></td><td>Webhook trigger (X-Webhook-Secret, 10/min)</td></tr>
<tr><td>GET</td><td><code>/system/status</code></td><td>System health detail (admin/operator: full; others: summary)</td></tr>
<tr><td>GET</td><td><code>/system/namespace-stats</code></td><td>Per-namespace KPIs and Pulse Score</td></tr>
</table>

<h2>Memory Write &mdash; POST Body Example</h2>
<pre>curl -X POST {API_URL}/api/v1/memory \\
  -H "Authorization: Bearer &lt;token&gt;" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "namespace": "faiyke-ai",
    "key": "client_profile_acme",
    "value": "Acme Corp, Lagos. Contact: James Brown, james@acmecorp.com",
    "category": "fact",
    "confidence": 0.95,
    "ttl_days": null
  }}'</pre>

<h2>Async Agent Run &mdash; Full Example</h2>
<pre># Dispatch
curl -X POST {API_URL}/api/v1/agents/writing-agent/run \\
  -H "Authorization: Bearer &lt;token&gt;" \\
  -H "Content-Type: application/json" \\
  -d '{{
    "prompt": "Write a 1-page executive summary of Q2 results",
    "namespace": "faiyke-ai",
    "save_output": true
  }}'

# Response 202
{{"run_id":"abc123","status":"pending","poll_url":"/api/v1/agents/runs/abc123"}}

# Poll until status == "done"
curl {API_URL}/api/v1/agents/runs/abc123 -H "Authorization: Bearer &lt;token&gt;"

# Done response
{{"run_id":"abc123","status":"done","output":"Q2 Executive Summary...","tokens_in":1420,"tokens_out":380,"eval_score":4.2}}</pre>

<h2>SSE Streaming &mdash; Full Example</h2>
<pre>curl -N "{API_URL}/api/v1/agents/writing-agent/stream?prompt=Hello&namespace=faiyke-ai" \\
  -H "X-API-Key: your_api_key"

data: {{"type":"token","text":"Hello"}}
data: {{"type":"token","text":" there"}}
data: {{"type":"done","run_id":"xyz","tokens_in":900,"tokens_out":12}}
data: {{"type":"error","message":"Rate limit exceeded"}}</pre>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 18 — SECURITY MODEL
# ═══════════════════════════════════════════════════════════════════════════════

def s18_security() -> str:
    return """
<h1><a name="s18"></a>18 &mdash; Security Model</h1>

<h2>Authentication</h2>
<table>
<tr><th style="width:28%;">Mechanism</th><th>Details</th></tr>
<tr><td>JWT access tokens</td>
    <td>60-minute TTL. Silently refreshed while active. Never stored in plaintext.</td></tr>
<tr><td>Refresh tokens</td>
    <td><strong>24-hour session window (v17.2).</strong> Stored as SHA-256 hash. Revokable per-session from Admin Panel.</td></tr>
<tr><td>API keys</td>
    <td>For scripts and automation. Created in Admin Panel. Raw key shown once; stored as hash thereafter.</td></tr>
<tr><td>Webhook secrets</td>
    <td>32-byte random hex, compared using HMAC constant-time <code>compare_digest</code> (timing-attack safe).</td></tr>
</table>

<h2>Password Policy</h2>
<ul>
<li>Minimum 10 characters; at least one uppercase, one lowercase, one digit</li>
<li>Hashed with bcrypt 12 rounds &mdash; never stored in plaintext</li>
<li>Admin can force password change on next login per user (<code>must_change_password</code> flag)</li>
</ul>

<h2>Account Lockout</h2>
<p>5 consecutive failed login attempts triggers a 15-minute lockout. Configurable via
<strong>Admin Panel &rarr; Security</strong>. Admin can manually unlock immediately from
<strong>Admin Panel &rarr; Users</strong> &mdash; the Unlock button only appears when the
account is actually locked (context-aware UI).</p>

<h2>CORS Restriction <span class="badge-new">v14.0</span></h2>
<p>Only origins listed in the <code>ALLOWED_ORIGINS</code> environment variable may make
cross-origin requests. Requests from unlisted origins receive <code>403 Forbidden</code>
at the CORS preflight stage before any auth is checked.</p>
<pre>ALLOWED_ORIGINS=http://localhost:8501,https://your-dashboard.company.com</pre>

<h2>Rate Limiting <span class="badge-new">v14.0</span></h2>
<table>
<tr><th style="width:35%;">Endpoint</th><th>Limit</th><th>Response</th></tr>
<tr><td>Agent <code>/run</code></td><td>30 / minute per IP</td><td>429 Too Many Requests</td></tr>
<tr><td>Agent <code>/stream</code></td><td>20 / minute per IP</td><td>429 Too Many Requests</td></tr>
<tr><td>Workflow <code>/trigger</code></td><td>10 / minute per IP</td><td>429 Too Many Requests</td></tr>
<tr><td>Workflow <code>/run</code></td><td>20 / minute per IP</td><td>429 Too Many Requests</td></tr>
</table>

<h2>Security Response Headers <span class="badge-new">v14.0 / v17.2</span></h2>
<p>All API responses include the following security headers:</p>
<table>
<tr><th style="width:46%;">Header</th><th>Value</th></tr>
<tr><td><code>X-Content-Type-Options</code></td><td><code>nosniff</code></td></tr>
<tr><td><code>X-Frame-Options</code></td><td><code>DENY</code></td></tr>
<tr><td><code>X-XSS-Protection</code></td><td><code>1; mode=block</code></td></tr>
<tr><td><code>Content-Security-Policy</code></td><td><code>default-src 'none'; frame-ancestors 'none'</code></td></tr>
<tr><td><code>Strict-Transport-Security</code></td><td><code>max-age=31536000; includeSubDomains</code> (production only)</td></tr>
</table>

<h2>Memory Write Size Cap <span class="badge-new">v17.2</span></h2>
<p>Memory entry values larger than <strong>64 KB</strong> are rejected with <code>422 Unprocessable Entity</code>.
This prevents oversized entries from degrading context injection performance. Split large documents
into multiple entries or upload them as context files in the Client Vault.</p>

<h2>Namespace Isolation</h2>
<p>Client and Viewer role users are hard-scoped to their assigned namespace at the application layer.
A client user cannot read, write, or search memory from another namespace regardless of API
parameters. <code>effective_namespace()</code> in <code>auth.py</code> enforces this on every request.</p>

<h2>Audit Log</h2>
<p>Every significant action is recorded: login success/failure, lockout, logout, token refresh,
user creation/deactivation/password reset, API key creation/revocation. View in
<strong>Admin Panel &rarr; Audit Log</strong>. Filter by date range using <code>?since=</code>
and <code>?until=</code> (ISO 8601 format).</p>

<h2>What FaiykeOS Does NOT Store</h2>
<ul>
<li>Plaintext passwords &mdash; only bcrypt hashes</li>
<li>Raw refresh tokens &mdash; only SHA-256 hashes</li>
<li>Raw API keys beyond the initial creation response &mdash; only hashes</li>
<li>Your Anthropic API key in the database &mdash; only in the server's <code>.env</code></li>
</ul>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 19 — CLOUD SYNC
# ═══════════════════════════════════════════════════════════════════════════════

def s19_sync() -> str:
    return """
<h1><a name="s19"></a>19 &mdash; Cloud Sync (Supabase)</h1>

<h2>Overview</h2>
<p>FaiykeOS can sync data to a Supabase PostgreSQL database for cloud backup and off-site
storage. Sync is <strong>push-only</strong> &mdash; SQLite on your server is always the source
of truth. Supabase is a mirror, not a primary store.</p>

<h2>What Is Synced (v17.2)</h2>
<p>Version 17.2 extended sync to include additional tables:</p>
<table>
<tr><th style="width:28%;">Table</th><th>Synced?</th><th>Notes</th></tr>
<tr><td>Memory entries</td><td>Yes</td><td>Full sync including consolidated and archived entries</td></tr>
<tr><td>Agent runs and outputs</td><td>Yes</td><td>Includes soft-deleted entries</td></tr>
<tr><td>Namespaces and projects</td><td>Yes</td><td>Full sync</td></tr>
<tr><td>Users</td><td>Yes (v17.2)</td><td>Sensitive columns excluded: password_hash, raw tokens</td></tr>
<tr><td>Tickets</td><td>Yes (v17.2)</td><td>Full ticket records and comments</td></tr>
<tr><td>Workflows</td><td>Yes (v17.2)</td><td>Workflow definitions; webhook_secret excluded</td></tr>
<tr><td>Auth data (sessions, passwords)</td><td>No</td><td>Stays on-server only. Never synced.</td></tr>
</table>

<h2>Setup</h2>
<ol>
<li>Create a free account at <strong>supabase.com</strong> and create a new project</li>
<li>In the Supabase SQL Editor, run <code>sync/supabase_schema.sql</code></li>
<li>Copy your project URL and service role key from project settings (API section)</li>
<li>Add to <code>.env</code>:
<pre>SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key</pre></li>
<li>Restart the server &mdash; auto-sync starts, running every 15 minutes</li>
</ol>

<h2>Manual Sync</h2>
<p>Go to <strong>Settings</strong> &rarr; click <strong>Sync Now</strong> to push immediately.
The sync log shows each run's result, rows synced, and any errors.</p>

<h2>Sync Log Management</h2>
<p>The Settings page renders the sync log as a table with checkboxes. You can:</p>
<ul>
<li>Select individual entries and click <strong>Delete Selected (N)</strong> for bulk deletion</li>
<li>Click the delete icon on any single row to remove it immediately</li>
<li>Maximum 200 entries per bulk delete operation</li>
</ul>

<h2>ChromaDB Health Check (v17.2)</h2>
<p>The <code>GET /system/status</code> endpoint now uses the real ChromaDB
<code>client.heartbeat()</code> call to verify vector store connectivity. If ChromaDB is
unreachable, the status endpoint reports the actual error rather than a hardcoded
&ldquo;ok&rdquo; string. The probe result is cached for 30 seconds to avoid excessive
reconnections.</p>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 20 — TROUBLESHOOTING & SUPPORT
# ═══════════════════════════════════════════════════════════════════════════════

def s20_troubleshoot() -> str:
    return f"""
<h1><a name="s20"></a>20 &mdash; Troubleshooting &amp; Support</h1>

<h2>Common Problems and Fixes</h2>
<table>
<tr><th style="width:33%;">Problem</th><th>Solution</th></tr>
<tr><td>Cannot reach the dashboard</td>
    <td>Run <code>.\\scripts\\start.ps1</code>. Check ports 5000 and 8501 are not blocked by Windows Defender Firewall.</td></tr>
<tr><td>Login fails</td>
    <td>Usernames are case-insensitive. After 5 failures, wait 15 minutes or ask admin to unlock.</td></tr>
<tr><td>&ldquo;Must change password&rdquo; shown</td>
    <td>Enter your current (temporary) password then your new password in the prompt.</td></tr>
<tr><td>API returns 401 Unauthorized</td>
    <td>Access token expired. Log out and back in. For API key, verify it is not revoked in Admin Panel.</td></tr>
<tr><td>API returns 403 Forbidden</td>
    <td>Check <code>ALLOWED_ORIGINS</code> in <code>.env</code> includes your dashboard URL (CORS issue).</td></tr>
<tr><td>API returns 429 Too Many Requests</td>
    <td>Rate limit hit. Wait 60 seconds before retrying.</td></tr>
<tr><td>Memory entry rejected with 422</td>
    <td><strong>v17.2:</strong> the entry value exceeds the 64 KB limit. Split it into multiple entries or upload as a context file in the Client Vault.</td></tr>
<tr><td>Stale runs stuck as &ldquo;running&rdquo; or &ldquo;pending&rdquo;</td>
    <td><strong>v17.2:</strong> stale runs older than 1 hour are automatically reset to &ldquo;failed&rdquo; on server startup. Restart the server to trigger cleanup.</td></tr>
<tr><td>MCP server not reachable from other machines</td>
    <td><strong>v17.2 by design:</strong> the MCP server binds to <code>127.0.0.1</code> only. Use an SSH tunnel or VPN for remote access.</td></tr>
<tr><td>Agent runs are slow</td>
    <td>Expected for long responses (~40 tokens/sec). Check Observability &rarr; Latency for baseline.</td></tr>
<tr><td>Eval scores not appearing</td>
    <td>Wait 10&ndash;15 seconds after run completes. Scores are async. Check logs for Haiku eval errors.</td></tr>
<tr><td>Streaming returns an error</td>
    <td>Ensure only one Flask process is running on port 5000. Restart with <code>.\\scripts\\start.ps1</code>.</td></tr>
<tr><td>Voice input not working</td>
    <td>Run <code>pip install openai-whisper</code>. First use downloads ~140 MB &mdash; wait for completion.</td></tr>
<tr><td>MCP server not found</td>
    <td>Run <code>pip install mcp uvicorn</code> then <code>.\\scripts\\start_mcp.ps1</code>.</td></tr>
<tr><td>Agents not responding</td>
    <td>Check <code>ANTHROPIC_API_KEY</code> in <code>.env</code>. Verify it is not expired in the Anthropic console.</td></tr>
<tr><td>ChromaDB slow on first start</td>
    <td>Normal &mdash; sentence-transformers model loads on first request (30&ndash;60 second cold start). Subsequent calls are fast.</td></tr>
<tr><td>Ticket email notifications not sending</td>
    <td>Verify SMTP settings in Settings &rarr; Email Notifications. Use the Test Send button. Gmail requires an App Password.</td></tr>
<tr><td>Supabase sync fails</td>
    <td>Verify <code>SUPABASE_URL</code> and <code>SUPABASE_SERVICE_KEY</code>. Restart after any <code>.env</code> change.</td></tr>
<tr><td>Output PDF export fails</td>
    <td>Try Markdown export instead. PDF export requires wkhtmltopdf installed on the server.</td></tr>
<tr><td>Memory entries not appearing in agent context</td>
    <td>Entries may be archived or expired. Check Memory page with all filters cleared. Verify namespace matches between write and run.</td></tr>
<tr><td>Namespace branding not appearing</td>
    <td>Confirm branding was saved in Admin &rarr; Branding. Log out and back in to force a brand refresh.</td></tr>
<tr><td>Pulse Score shows &ldquo;Getting Started&rdquo;</td>
    <td>Normal for new namespaces. The score appears once there are agent runs, tickets, and memory entries.</td></tr>
<tr><td>Agent gives confident wrong answers</td>
    <td>The hallucination guard (v16.0+) is working correctly &mdash; agents ask for data rather than fabricating. Supply the requested data and re-run.</td></tr>
<tr><td>Activity feed shows IDs instead of agent names</td>
    <td>Upgrade to v16.0+. The dispatcher now JOINs the agents table for human-readable names.</td></tr>
<tr><td>Namespace Usage tab not showing data</td>
    <td>Requires at least one agent run. Zero values are normal for new deployments. Tab visible to Admin and Operator only.</td></tr>
<tr><td>Onboarding modal not showing</td>
    <td>Modal shows once per account (client/viewer only). Admin accounts skip it. Reset with: <code>UPDATE users SET onboarding_done=0 WHERE username='...'</code></td></tr>
<tr><td>Background colour not applying</td>
    <td>Ensure &ldquo;Use custom background&rdquo; is checked. Note: session-only &mdash; resets on logout.</td></tr>
</table>

<h2>Contact Your Administrator</h2>
<table>
<tr><th style="width:25%;">Detail</th><th>Value</th></tr>
<tr><td>Name</td><td>{ADMIN_NAME}</td></tr>
<tr><td>Email</td><td>{ADMIN_EMAIL}</td></tr>
<tr><td>Phone</td><td>{ADMIN_PHONE}</td></tr>
<tr><td>Dashboard URL</td><td><code>{SYSTEM_URL}</code></td></tr>
</table>

<h2>Before Contacting Support</h2>
<ol>
<li>Check this section for your exact error message</li>
<li>Note what you were doing: which page, agent, and prompt</li>
<li>Note whether the error is reproducible</li>
<li>Check Observability for any system-wide alerts</li>
<li>Provide: your username, role, namespace, run ID (from Run History), and the approximate time</li>
</ol>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 21 — QUICK REFERENCE
# ═══════════════════════════════════════════════════════════════════════════════

def s21_quickref() -> str:
    return f"""
<h1><a name="s21"></a>21 &mdash; Quick Reference</h1>

<h2>Key Pages at a Glance</h2>
<table>
<tr><th style="width:24%;">Task</th><th>Where to Go</th></tr>
<tr><td>Run an agent</td><td>Agents &rarr; Chat tab</td></tr>
<tr><td>Browse agents</td><td>Agents &rarr; Catalog tab (click card to open chat)</td></tr>
<tr><td>Add a memory entry</td><td>Memory &rarr; Add Entry</td></tr>
<tr><td>Search memory</td><td>Memory &rarr; Search box (toggle Hybrid for semantic)</td></tr>
<tr><td>Trigger a workflow</td><td>Workflows &rarr; Run Now button on workflow card</td></tr>
<tr><td>View quality scores</td><td>Observability &rarr; Quality Scores tab</td></tr>
<tr><td>Check token spend</td><td>Observability &rarr; Token Cost tab</td></tr>
<tr><td>View your namespace KPIs</td><td>Usage page (client/viewer) or Overview (admin/operator)</td></tr>
<tr><td>Create a ticket</td><td>Tickets &rarr; New Ticket</td></tr>
<tr><td>Configure namespace branding</td><td>Admin Panel &rarr; Branding tab</td></tr>
<tr><td>Create or revoke API keys</td><td>Admin Panel &rarr; API Keys tab</td></tr>
<tr><td>View the audit log</td><td>Admin Panel &rarr; Audit Log tab</td></tr>
<tr><td>Trigger memory consolidation</td><td>Observability &rarr; Memory Health &rarr; Trigger Consolidation</td></tr>
<tr><td>Push data to Supabase now</td><td>Settings &rarr; Sync Now</td></tr>
<tr><td>Unlock a locked user</td><td>Admin Panel &rarr; Users &rarr; Unlock button (only shown when locked)</td></tr>
</table>

<h2>Common API Snippets</h2>

<div class="callout">
<strong>Login and get a token</strong><br/>
<code>curl -X POST {API_URL}/api/v1/auth/login -H "Content-Type: application/json" -d '{{"username":"admin","password":"your_pass"}}'</code>
</div>

<div class="callout">
<strong>Run an agent (async)</strong><br/>
<code>curl -X POST {API_URL}/api/v1/agents/writing-agent/run -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" -d '{{"prompt":"Write a brief","namespace":"faiyke-ai","save_output":true}}'</code>
</div>

<div class="callout">
<strong>Write a memory entry</strong><br/>
<code>curl -X POST {API_URL}/api/v1/memory -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" -d '{{"namespace":"faiyke-ai","key":"my_key","value":"my value","category":"fact"}}'</code>
</div>

<div class="callout">
<strong>Search memory (hybrid)</strong><br/>
<code>curl "{API_URL}/api/v1/memory/hybrid-search?q=client+payment&namespace=faiyke-ai" -H "Authorization: Bearer TOKEN"</code>
</div>

<div class="callout">
<strong>Trigger a workflow via webhook</strong><br/>
<code>curl -X POST {API_URL}/api/v1/workflows/morning-briefing/trigger -H "X-Webhook-Secret: SECRET" -H "Content-Type: application/json" -d '{{"context":{{"namespace":"faiyke-ai"}}}}'</code>
</div>

<h2>Common Agent Prompts Cheat Sheet</h2>
<table>
<tr><th style="width:28%;">Goal</th><th>Prompt Template</th></tr>
<tr><td>Daily briefing</td><td><em>Generate today's briefing. Include all reminders due this week and outstanding client follow-ups.</em></td></tr>
<tr><td>Client status update</td><td><em>Produce a one-page status card for [Client Name] covering: active projects, blockers, next actions, and upcoming deadlines.</em></td></tr>
<tr><td>Schedule a reminder</td><td><em>Add a reminder to follow up with [Name] about [topic] by [date].</em></td></tr>
<tr><td>Research summary</td><td><em>Research [topic] and synthesise the key findings into a 3-point summary with sources. Do not use information not grounded in memory context.</em></td></tr>
<tr><td>Code review</td><td><em>Review the attached code for OWASP Top-10 vulnerabilities and Windows-compatibility issues. List findings by severity.</em></td></tr>
<tr><td>Draft email</td><td><em>Draft a professional email to [recipient] about [topic]. Tone: [tone]. Maximum 150 words.</em></td></tr>
</table>

<h2>Server Management Commands</h2>
<pre># Start everything
.\\scripts\\start.ps1

# Stop everything
.\\scripts\\stop.ps1

# Start MCP server (optional, localhost only)
.\\scripts\\start_mcp.ps1

# Run database migrations
python scripts/migrate.py

# Create admin user
python scripts/create_admin.py --username admin --password Admin123!

# Seed client onboarding fields
python scripts/seed_client_schema.py --namespace faiyke-ai

# Kill process on a port (Windows)
netstat -ano | findstr :5000
taskkill /F /PID &lt;PID&gt;</pre>

<h2>Eval Score Quick Reference</h2>
<table>
<tr><th style="width:20%;">Score</th><th style="width:20%;">Colour</th><th>Meaning</th></tr>
<tr><td>4.0 &ndash; 5.0</td><td><span class="pill-green">Green</span></td><td>High quality. Ready to use or send.</td></tr>
<tr><td>2.5 &ndash; 3.9</td><td><span class="pill-amber">Amber</span></td><td>Acceptable. Review before sharing with clients.</td></tr>
<tr><td>0 &ndash; 2.4</td><td><span class="pill-red">Red</span></td><td>Low quality. Re-run with a more specific prompt and more memory context.</td></tr>
</table>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 22 — GLOSSARY
# ═══════════════════════════════════════════════════════════════════════════════

def s22_glossary() -> str:
    return """
<h1><a name="s22"></a>22 &mdash; Glossary</h1>

<p>Key terms used throughout this handbook, defined in plain English.</p>

<table>
<tr><th style="width:24%;">Term</th><th>Definition</th></tr>
<tr><td><strong>A2A (Agent-to-Agent)</strong></td>
    <td>A protocol allowing AI systems to discover and call each other's capabilities. FaiykeOS exposes each agent as an A2A card at <code>/.well-known/agent.json</code>.</td></tr>
<tr><td><strong>API Key</strong></td>
    <td>A long random string used in place of a JWT for script and automation access. Created in Admin Panel &rarr; API Keys. Shown once; stored as a hash.</td></tr>
<tr><td><strong>Archived Entry</strong></td>
    <td>A memory entry that has been superseded by consolidation. Marked <code>archived=1</code> in the database. Never hard-deleted; accessible to admins at DB level.</td></tr>
<tr><td><strong>BM25</strong></td>
    <td>Best Match 25 &mdash; a probabilistic keyword ranking algorithm used in FaiykeOS's hybrid memory search. Scores documents by term frequency and inverse document frequency.</td></tr>
<tr><td><strong>ChromaDB</strong></td>
    <td>An open-source vector database used by FaiykeOS to store and search semantic embeddings of memory entries.</td></tr>
<tr><td><strong>Consolidation</strong></td>
    <td>The automated process of clustering similar memory entries and synthesising them into one concise entry using Claude Haiku. Runs every 4 hours.</td></tr>
<tr><td><strong>Context Injection</strong></td>
    <td>The process of retrieving the most relevant memory entries and inserting them into an agent's system prompt before it runs. Powers the &ldquo;memory-aware&rdquo; behaviour.</td></tr>
<tr><td><strong>CSP (Content-Security-Policy)</strong></td>
    <td>An HTTP response header that restricts which resources a browser is allowed to load. FaiykeOS sets <code>default-src 'none'; frame-ancestors 'none'</code> on all API responses.</td></tr>
<tr><td><strong>Eval Score</strong></td>
    <td>An automatic 0&ndash;5 quality rating assigned to each agent response by Claude Haiku. Composite of task completion (40%), factual grounding (30%), conciseness (20%), and safety (10%).</td></tr>
<tr><td><strong>Hallucination Guard</strong></td>
    <td>A set of rules embedded in certain agent system prompts (analysis, briefing, research, writing) that prevent agents from fabricating facts. Agents ask clarifying questions instead.</td></tr>
<tr><td><strong>HMAC</strong></td>
    <td>Hash-based Message Authentication Code. Used to sign and verify webhook requests. FaiykeOS uses <code>hmac.compare_digest</code> for timing-attack-safe comparison.</td></tr>
<tr><td><strong>HSTS (HTTP Strict Transport Security)</strong></td>
    <td>An HTTP header that instructs browsers to only access the server over HTTPS. Applied in production deployments of FaiykeOS.</td></tr>
<tr><td><strong>Hybrid RAG</strong></td>
    <td>Retrieval-Augmented Generation using both keyword (BM25) and semantic (vector) search. Results are merged via RRF. Provides better recall than either method alone.</td></tr>
<tr><td><strong>JWT (JSON Web Token)</strong></td>
    <td>A compact, signed credential used to authenticate API requests. FaiykeOS access tokens expire after 60 minutes; refresh tokens have a 24-hour session window.</td></tr>
<tr><td><strong>MCP (Model Context Protocol)</strong></td>
    <td>An open standard developed by Anthropic for AI tools to expose capabilities to external clients. FaiykeOS runs an MCP server on port 5100 (localhost only).</td></tr>
<tr><td><strong>Namespace</strong></td>
    <td>An isolated workspace in FaiykeOS. All memory, agent runs, outputs, and tickets belong to a namespace. Clients can only access their own namespace.</td></tr>
<tr><td><strong>Pulse Score</strong></td>
    <td>A composite 0&ndash;100 namespace health indicator. Formula: eval quality (40%) + ticket resolution (30%) + memory freshness (20%) + workflow success (10%).</td></tr>
<tr><td><strong>RRF (Reciprocal Rank Fusion)</strong></td>
    <td>An algorithm that combines ranked lists from multiple retrieval methods (BM25 + vector) into a single merged ranking. Used in FaiykeOS hybrid memory search (k=60).</td></tr>
<tr><td><strong>Soft-Delete</strong></td>
    <td>A deletion pattern where a <code>deleted_at</code> timestamp is written to a record rather than removing it from the database. Used in v17.2 for outputs. Records disappear from all views but remain accessible at DB level.</td></tr>
<tr><td><strong>SSE (Server-Sent Events)</strong></td>
    <td>A one-way HTTP streaming protocol. FaiykeOS uses SSE to stream agent responses token-by-token to the browser without requiring WebSocket infrastructure.</td></tr>
<tr><td><strong>Tiered Context</strong></td>
    <td>A memory injection strategy that selects entries by recency and confidence rather than injecting all entries. Reduces token usage by approximately 40% versus flat injection.</td></tr>
<tr><td><strong>Webhook</strong></td>
    <td>An HTTP callback that lets an external system trigger a FaiykeOS workflow without a login token. Secured by an HMAC secret. Rate-limited to 10 requests per minute.</td></tr>
</table>
"""


# ═══════════════════════════════════════════════════════════════════════════════
# ASSEMBLE AND RENDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_html() -> str:
    body = "".join([
        cover_page(),
        toc(),
        s1_intro(),
        s2_requirements(),
        s3_install(),
        s4_login(),
        s5_dashboard(),
        s6_agents(),
        s7_memory(),
        s8_workflows(),
        s9_vault(),
        s10_outputs(),
        s11_tickets(),
        s12_quality(),
        s13_observability(),
        s14_branding(),
        s15_bgcolor(),
        s16_advanced(),
        s17_api(),
        s18_security(),
        s19_sync(),
        s20_troubleshoot(),
        s21_quickref(),
        s22_glossary(),
    ])
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>FaiykeOS v{VERSION} &mdash; Client Handbook &mdash; {CLIENT}</title>
  <style>{CSS}</style>
</head>
<body>
<div id="footer_content">FaiykeOS v{VERSION} &nbsp;&#183;&nbsp; faiyke-ai &nbsp;&#183;&nbsp; Page <pdf:pagenumber> of <pdf:pagecount> &nbsp;&#183;&nbsp; Confidential</div>
{body}
</body>
</html>"""


if __name__ == "__main__":
    out_path = Path(f"docs/FaiykeOS_Handbook_{CLIENT}.pdf")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Building FaiykeOS v{VERSION} Handbook HTML ...")
    html = build_html()

    print(f"Rendering PDF -> {out_path} ...")
    with open(out_path, "wb") as f:
        result = pisa.CreatePDF(io.StringIO(html), dest=f)

    if result.err:
        print(f"PDF errors: {result.err}")
    else:
        size_kb = out_path.stat().st_size // 1024
        print(f"Done: {out_path} ({size_kb} KB)")
