#!/usr/bin/env python3
"""
ClaudeOS Client Documentation Generator
========================================
Usage:  python scripts/generate_docs.py
Output: docs/ClaudeOS_Client_Documentation.pdf
Requires: pip install fpdf2
"""

import os
import sys
from datetime import date
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("ERROR: Missing dependency. Run:  pip install fpdf2")
    sys.exit(1)

ROOT = Path(__file__).parent.parent
OUT  = ROOT / "docs" / "ClaudeOS_Client_Documentation.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)
TODAY = date.today().strftime("%B %Y")

# ── Brand colours (RGB) ──────────────────────────────────────────────────────
GREEN   = (64, 126, 60)
GREEN2  = (45, 90, 41)
LTGREEN = (237, 247, 237)
CODEBG  = (245, 245, 245)
TEXT    = (26, 26, 26)
MUTED   = (107, 114, 128)
WHITE   = (255, 255, 255)

PW = 170   # usable page width (210 - 20 left - 20 right)


# ─────────────────────────────────────────────────────────────────────────────
#  PDF class
# ─────────────────────────────────────────────────────────────────────────────

class Doc(FPDF):
    def __init__(self, toc_offset: int = 0, link_ids: dict = None):
        super().__init__()
        self.toc_offset = toc_offset
        self._sections: dict[str, int] = {}
        self._link_ids: dict[str, int] = link_ids or {}
        self.set_auto_page_break(True, margin=22)
        self.set_margins(20, 25, 20)

    # ── FPDF overrides ───────────────────────────────────────────────────────

    def header(self):
        if self.page_no() <= 1 + self.toc_offset:
            return
        self.set_fill_color(*GREEN)
        self.rect(0, 0, 210, 8, 'F')
        self.set_font('Helvetica', 'I', 7)
        self.set_text_color(*WHITE)
        self.set_xy(0, 1)
        self.cell(0, 6, 'ClaudeOS  |  AI Operating System  |  Client Guide & Reference Manual', align='C')
        self.set_text_color(*TEXT)
        # Must reset y to top margin — without this, content after auto-page-break
        # starts at y=1 (inside the green bar) instead of y=t_margin.
        self.set_y(self.t_margin)

    def footer(self):
        if self.page_no() <= 1 + self.toc_offset:
            return
        self.set_y(-14)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(*MUTED)
        pg = self.page_no() - 1 - self.toc_offset
        self.cell(0, 8, f'Page {pg}  |  ClaudeOS Client Guide  |  Confidential', align='C')
        self.set_text_color(*TEXT)

    # ── Layout helpers ───────────────────────────────────────────────────────

    def h1(self, title: str, new_page: bool = True):
        if new_page:
            # Only add a new page if we're not already near the top
            # (prevents double blank page when auto-page-break already fired)
            if self.get_y() > 40:
                self.add_page()
        else:
            self.ln(4)
        self._sections[title] = self.page_no()
        if title in self._link_ids:
            self.set_link(self._link_ids[title], y=0, page=self.page_no())
        self.set_fill_color(*GREEN)
        self.set_text_color(*WHITE)
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, f'  {title}', fill=True, ln=True)
        self.set_text_color(*TEXT)
        self.ln(3)

    def h2(self, title: str):
        self.ln(3)
        self.set_fill_color(*GREEN2)
        self.set_text_color(*WHITE)
        self.set_font('Helvetica', 'B', 11)
        self.cell(0, 8, f'  {title}', fill=True, ln=True)
        self.set_text_color(*TEXT)
        self.ln(2)

    def h3(self, title: str):
        self.ln(2)
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(*GREEN)
        self.cell(0, 7, title, ln=True)
        self.set_text_color(*TEXT)

    def body(self, text: str):
        self.set_font('Helvetica', '', 11)
        self.set_text_color(*TEXT)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def bullets(self, items: list, indent: int = 8):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*TEXT)
        for item in items:
            self.set_x(20 + indent)
            self.multi_cell(PW - indent, 6, f'- {str(item)}')
        self.ln(1)

    def numbered(self, items: list, indent: int = 8):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*TEXT)
        for i, item in enumerate(items, 1):
            self.set_x(20 + indent)
            self.multi_cell(PW - indent, 6, f'{i}. {str(item)}')
        self.ln(1)

    def code(self, text: str):
        self.set_fill_color(*CODEBG)
        self.set_font('Courier', '', 9)
        self.set_text_color(*TEXT)
        self.multi_cell(0, 5, f'  {text}', fill=True)
        self.ln(2)

    def tip(self, label: str, text: str):
        self.set_fill_color(*LTGREEN)
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(*GREEN)
        self.cell(0, 6, f'  {label}', fill=True, ln=True)
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*TEXT)
        self.multi_cell(0, 5.5, f'  {text}', fill=True)
        self.ln(3)

    def table(self, headers: list, rows: list, widths: list = None):
        if widths is None:
            w = PW / len(headers)
            widths = [w] * len(headers)
        self.set_fill_color(*GREEN)
        self.set_text_color(*WHITE)
        self.set_font('Helvetica', 'B', 9)
        for h, w in zip(headers, widths):
            self.cell(w, 7, f' {h}', border=1, fill=True)
        self.ln()
        self.set_font('Helvetica', '', 9)
        for ri, row in enumerate(rows):
            if ri % 2 == 0:
                self.set_fill_color(248, 252, 248)
            else:
                self.set_fill_color(*WHITE)
            self.set_text_color(*TEXT)
            for val, w in zip(row, widths):
                self.cell(w, 6, f' {str(val)[:40]}', border=1, fill=True)
            self.ln()
        self.ln(3)

    def kv(self, label: str, value: str):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(*GREEN)
        self.cell(52, 6, f'{label}:')
        self.set_font('Helvetica', '', 10)
        self.set_text_color(*TEXT)
        # Truncate to fit remaining width cleanly — avoids multi_cell x issues
        self.multi_cell(PW - 52, 6, str(value))
        self.ln(1)

    def divider(self):
        self.set_draw_color(*GREEN)
        self.line(20, self.get_y(), 190, self.get_y())
        self.ln(4)


# ─────────────────────────────────────────────────────────────────────────────
#  Section writers
# ─────────────────────────────────────────────────────────────────────────────

def cover_page(pdf: Doc):
    pdf.add_page()
    pdf.set_fill_color(*GREEN)
    pdf.rect(0, 0, 210, 108, 'F')

    pdf.set_y(18)
    pdf.set_font('Helvetica', 'B', 56)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 24, 'ClaudeOS', align='C', ln=True)

    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(200, 230, 200)
    pdf.cell(0, 6, 'AI OPERATING SYSTEM', align='C', ln=True)

    pdf.ln(8)
    pdf.set_draw_color(*WHITE)
    pdf.line(55, pdf.get_y(), 155, pdf.get_y())
    pdf.ln(8)

    pdf.set_font('Helvetica', 'B', 17)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 9, 'Client Guide & Reference Manual', align='C', ln=True)

    pdf.set_y(120)
    pdf.set_font('Helvetica', '', 12)
    pdf.set_text_color(*TEXT)
    pdf.cell(0, 8, f'Version 8.0  -  {TODAY}', align='C', ln=True)
    pdf.ln(5)

    pdf.set_font('Helvetica', 'I', 10)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 6,
        'This document covers everything you need to know about ClaudeOS -- '
        'from opening the dashboard for the first time, to running automated '
        'workflows and managing your client workspace.', align='C')

    pdf.ln(12)
    pdf.set_fill_color(*LTGREEN)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 7, '  This guide includes:', fill=True, ln=True)
    items = [
        'Step-by-step instructions for using the dashboard',
        'Full reference for all 12 AI agents and 7 automated workflows',
        'Authentication, roles, and multi-user access control guide',
        'Client-specific sections: RECI Transport, Ivycandy Hair, Faiyke AI, Personal',
        'Memory system, outputs, and cloud sync guides',
        'Admin Panel: user management, API keys, audit log, security settings',
        'Technical reference for administrators and troubleshooting',
    ]
    pdf.set_fill_color(*LTGREEN)
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(*TEXT)
    for item in items:
        pdf.set_x(25)
        pdf.cell(6, 6, '-', fill=True)
        pdf.cell(0, 6, item, fill=True, ln=True)
    pdf.ln(2)

    pdf.set_fill_color(*GREEN)
    pdf.rect(0, 263, 210, 34, 'F')
    pdf.set_y(271)
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(200, 230, 200)
    pdf.cell(0, 6, 'Confidential -- For authorised clients only', align='C', ln=True)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_text_color(*WHITE)
    pdf.cell(0, 6, 'Prepared by Rigwe  |  ClaudeOS v8.0', align='C')


def toc_page(pdf: Doc, section_pages: dict, link_ids: dict):
    pdf.add_page()
    pdf.set_fill_color(*GREEN)
    pdf.set_text_color(*WHITE)
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, '  Table of Contents', fill=True, ln=True)
    pdf.ln(5)

    pdf.set_font('Helvetica', '', 11)
    for title, pg in section_pages.items():
        lid = link_ids.get(title)
        pdf.set_text_color(*GREEN)
        pdf.cell(PW - 18, 8, title, ln=False, link=lid)
        pdf.set_text_color(*MUTED)
        pdf.cell(18, 8, str(pg), align='R', ln=True, link=lid)
    pdf.ln(4)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, 'Page numbers refer to content pages (excluding cover and table of contents).', ln=True)


# ─────────────────────────────────────────────────────────────────────────────

def sec_introduction(pdf: Doc):
    pdf.h1('1. What is ClaudeOS?')
    pdf.body(
        'ClaudeOS is an AI-powered operating system built to help you and your team '
        'get more done -- faster and smarter. Think of it as a highly capable AI '
        'assistant that never sleeps, remembers everything you tell it, automatically '
        'runs tasks on a schedule, and organises all of its work neatly for you to find later.'
    )
    pdf.body(
        'Unlike a simple chatbot, ClaudeOS has multiple specialised AI agents (think: '
        'departments), a memory system (think: a filing cabinet that grows smarter over time), '
        'and automated workflows (think: recurring tasks that run themselves). '
        'Everything is controlled from a web dashboard you open in your browser.'
    )

    pdf.h2('What Problems Does It Solve?')
    pdf.bullets([
        'You need to write a client report every Friday -- ClaudeOS does it automatically.',
        'You want to research a topic and get a summary -- one click and it is done.',
        'You need to remember a client preference or decision -- save it to memory and every future AI response will know about it.',
        'You want to track all AI-generated content in one place -- every output is saved and searchable.',
        'You manage multiple clients and do not want their data to mix -- each client has their own private workspace.',
    ])

    pdf.h2('The 7 Core Modules (Plain English)')
    pdf.table(
        ['Module', 'What It Is'],
        [
            ['Dashboard', 'A web page you open in your browser to control everything'],
            ['API', 'The behind-the-scenes engine the dashboard talks to'],
            ['Memory Engine', 'A knowledge store the AI reads before every task'],
            ['Agent Registry', '12 specialised AI workers, each with a specific job'],
            ['Workflow Engine', 'Automated pipelines that run on a schedule or on demand'],
            ['Client Vault', 'Private workspaces for each client -- data never crosses over'],
            ['Output Manager', 'Saves and organises every piece of content the AI produces'],
        ],
        widths=[50, 120]
    )

    pdf.h2('Who Uses ClaudeOS?')
    pdf.body(
        'ClaudeOS is designed for two types of users:'
    )
    pdf.bullets([
        'End users -- clients and team members who use the dashboard to run agents, '
        'search memory, view outputs, and monitor workflows. No technical knowledge needed.',
        'Administrators -- the person who sets up and maintains the system. '
        'They handle configuration, API keys, and server startup. '
        'Technical reference is in Section 12 of this guide.',
    ])


# ─────────────────────────────────────────────────────────────────────────────

def sec_design_principles(pdf: Doc):
    pdf.h1('2. Design Principles')
    pdf.body(
        'ClaudeOS was built with 8 guiding principles that shape how everything works. '
        'You do not need to memorise these -- but understanding them will help you get '
        'the most out of the system.'
    )

    principles = [
        (
            '1. Windows-First',
            'ClaudeOS runs natively on Windows 10 and above. No Linux server, no cloud subscription '
            'required just to run it. Start it with a single PowerShell script and it is ready in '
            'under 30 seconds. Everything is designed to work reliably on the Windows desktop.'
        ),
        (
            '2. Client Privacy (Namespace Isolation)',
            'Every client has their own private workspace called a namespace. When an AI agent '
            'works on a RECI Transport task, it can only see RECI Transport data. '
            'Ivycandy Hair data stays in the Ivycandy Hair namespace. There is no risk of '
            'one client\'s information appearing in another client\'s output.'
        ),
        (
            '3. Smart Memory (Dual-Index)',
            'ClaudeOS has two search engines working together. The first is keyword search '
            '(like searching a document for an exact word). The second is meaning-based '
            'search (finds results even when you use different words). Together they make '
            'sure you always find what you are looking for in memory.'
        ),
        (
            '4. Background Execution',
            'When you dispatch an AI agent, ClaudeOS runs it in the background immediately. '
            'You get a run ID and can continue using the dashboard. No waiting, no frozen screens. '
            'Check back any time to see results.'
        ),
        (
            '5. Workflow Automation',
            'Workflows are sequences of AI agents that run one after another. '
            'Some run automatically on a schedule (e.g. every weekday morning). '
            'Others you trigger with one click. You can pass information between steps '
            '-- the output of one agent becomes the input of the next.'
        ),
        (
            '6. Auto-Tagging',
            'Every time the AI produces a document, report, or draft, ClaudeOS '
            'automatically reads the content and assigns relevant tags (like "client", '
            '"urgent", "report"). This means you can find any output months later '
            'without remembering exactly what it was called.'
        ),
        (
            '7. Cloud Backup',
            'ClaudeOS can automatically push your data to Supabase (a secure cloud database) '
            'every 15 minutes. This is optional but recommended. It means your memory entries, '
            'agent runs, and outputs are backed up safely even if something happens to your local machine.'
        ),
        (
            '8. Voice Matching',
            'The Writing and Communications agents adapt their tone based on who the client is. '
            'If you have saved context about a client preferring formal emails, the agent will '
            'write formally. If a client prefers a warm and casual tone, the agent matches that. '
            'This context lives in the client\'s memory namespace.'
        ),
    ]

    for title, explanation in principles:
        pdf.h3(title)
        pdf.body(explanation)
        pdf.ln(1)


# ─────────────────────────────────────────────────────────────────────────────

def sec_getting_started(pdf: Doc):
    pdf.h1('3. Getting Started')

    pdf.h2('Prerequisites')
    pdf.body('Before starting ClaudeOS for the first time, make sure the following are in place:')
    pdf.bullets([
        'Python 3.11 or newer installed on your Windows machine',
        'An Anthropic API key (this is what powers the AI -- your administrator will have this)',
        'A .env file in the ClaudeOS folder with your configuration (see Section 12)',
        'All Python packages installed (your administrator runs this once: pip install -r requirements.txt)',
    ])

    pdf.h2('Starting the System')
    pdf.body('ClaudeOS starts with a single command. Open PowerShell, navigate to the ClaudeOS folder, and run:')
    pdf.code('.\\scripts\\start.ps1')
    pdf.body('The startup script does the following automatically:')
    pdf.numbered([
        'Reads your port settings from the .env file',
        'Stops any old processes that might be running on those ports',
        'Runs any pending database updates (migrations)',
        'Starts the Flask API server in the background on port 5000',
        'Waits and checks that the API is healthy (up to 10 retries)',
        'Starts the Streamlit dashboard on port 8501',
    ])

    pdf.tip(
        'SUCCESS INDICATOR',
        'When startup is complete you will see "ClaudeOS v1.0.0 - Started" in green. '
        'The terminal stays open showing the dashboard. Press Ctrl+C to stop everything.'
    )

    pdf.h2('Opening the Dashboard')
    pdf.body('Once started, open your web browser and go to:')
    pdf.code('http://localhost:8501')
    pdf.body(
        'You will see the ClaudeOS dashboard with a green sidebar. '
        'The sidebar shows CLAUDEOS at the top, the navigation menu, '
        'an API status indicator (green dot = online), and the current date and time.'
    )

    pdf.h2('Logging In')
    pdf.body(
        'ClaudeOS requires a login before you can use the dashboard. '
        'When you open http://localhost:8501 you will see the login screen. '
        'Enter your username and password, then click Sign In. '
        'On first login you may be prompted to set a new password.'
    )
    pdf.tip(
        'SELF-REGISTRATION',
        'If your administrator has enabled self-registration, you will see a Register tab '
        'on the login screen. Enter a username, password (min 10 chars, must include uppercase, '
        'lowercase, and a digit), email, and select your namespace. Then log in separately.'
    )

    pdf.h2('Dark Mode and Light Mode')
    pdf.body(
        'ClaudeOS supports both dark and light colour themes. '
        'A toggle button sits in the bottom-left corner of every page -- including the login screen. '
        'Click it to switch between Dark and Light mode. '
        'Your preference is remembered for the session.'
    )

    pdf.h2('API Access (for developers)')
    pdf.body('The REST API runs separately and can be accessed directly:')
    pdf.code('http://localhost:5000/api/v1/health')
    pdf.body(
        'All API routes (except /health) require authentication. '
        'Use a JWT Bearer token from the login endpoint, or an X-API-Key header for legacy scripts. '
        'See Section 10 for full API reference and auth details.'
    )


# ─────────────────────────────────────────────────────────────────────────────

def sec_auth_security(pdf: Doc):
    pdf.h1('4. Authentication & Access Control')
    pdf.body(
        'ClaudeOS uses a secure login system to protect all data. '
        'Every user has a role that determines what they can see and do. '
        'All sessions are tracked and can be revoked at any time.'
    )

    pdf.h2('How to Log In')
    pdf.numbered([
        'Open http://localhost:8501 in your browser',
        'Enter your username and password on the Sign In tab',
        'Click Sign In',
        'If prompted, enter a new password (required on first login or after admin reset)',
        'You will land on the Overview page with a navigation sidebar matching your role',
    ])
    pdf.tip(
        'SESSION DURATION',
        'Your login session lasts 60 minutes. ClaudeOS silently refreshes it while you are active. '
        'After 7 days of inactivity your session expires and you will need to log in again.'
    )

    pdf.h2('Self-Registration (if enabled by admin)')
    pdf.numbered([
        'On the login screen, click the Register tab',
        'Enter a username (unique, no spaces)',
        'Enter an email address',
        'Enter a password -- must be at least 10 characters, include one uppercase letter, one lowercase letter, and one digit',
        'Confirm your password',
        'Select your namespace from the dropdown (client-type namespaces only)',
        'Click Register',
        'Go back to Sign In and log in with your new credentials',
    ])

    pdf.h2('Roles & Permissions')
    pdf.table(
        ['Role', 'Namespace Access', 'Read', 'Write', 'Run Agents', 'Admin Panel'],
        [
            ['admin', 'All namespaces', 'Yes', 'Yes', 'Yes', 'Yes'],
            ['operator', 'All namespaces', 'Yes', 'Yes', 'Yes', 'No'],
            ['client', 'Own namespace only', 'Yes', 'Yes', 'Yes', 'No'],
            ['viewer', 'Own namespace only', 'Yes', 'No', 'No', 'No'],
        ],
        widths=[26, 42, 18, 18, 24, 28]
    )
    pdf.body(
        'Clients and viewers only ever see data from their own namespace. '
        'Even if they try to access another namespace via the API, the system blocks it automatically. '
        'Admins and operators can see all namespaces.'
    )

    pdf.h2('Account Lockout')
    pdf.body(
        'After 5 consecutive failed login attempts your account is automatically locked for 15 minutes. '
        'Both thresholds are configurable by the admin in the Admin Panel > Security tab. '
        'While locked you will see a message with the remaining wait time.'
    )
    pdf.bullets([
        'Wait for the lockout period to expire and try again',
        'Or ask your administrator to unlock your account immediately via the Admin Panel > Users tab > Unlock',
    ])

    pdf.h2('Password Requirements')
    pdf.bullets([
        'Minimum 10 characters',
        'At least one uppercase letter (A-Z)',
        'At least one lowercase letter (a-z)',
        'At least one digit (0-9)',
        'Must not contain your username',
    ])

    pdf.h2('Changing Your Password')
    pdf.numbered([
        'Log in to the dashboard',
        'If the system requires a password change you will be prompted automatically',
        'Enter your current password, then your new password twice',
        'Click Change Password',
        'You will be returned to the dashboard immediately',
    ])

    pdf.h2('Logging Out')
    pdf.body(
        'Click your username in the sidebar to reveal the Logout button. '
        'Clicking Logout immediately revokes your session on the server and returns you to the login screen. '
        'Your data is never deleted when you log out.'
    )

    pdf.h2('API Authentication (developers)')
    pdf.body('Two authentication methods are supported:')
    pdf.table(
        ['Method', 'Header', 'How to get it'],
        [
            ['JWT Bearer', 'Authorization: Bearer <token>', 'POST /api/v1/auth/login with username+password'],
            ['API Key', 'X-API-Key: <key>', 'Admin Panel > API Keys tab > Create Key'],
        ],
        widths=[28, 80, 62]
    )
    pdf.code(
        '# Login and get a token\n'
        'curl -X POST http://localhost:5000/api/v1/auth/login \\\n'
        '  -H "Content-Type: application/json" \\\n'
        '  -d \'{"username":"your_user","password":"your_pass"}\'\n\n'
        '# Use the token on any route\n'
        'curl http://localhost:5000/api/v1/agents \\\n'
        '  -H "Authorization: Bearer <access_token>"'
    )
    pdf.tip(
        'REFRESH TOKENS',
        'The login response includes both an access_token (60 min) and a refresh_token (7 days). '
        'Store the refresh token securely. Use POST /api/v1/auth/refresh with the refresh token '
        'to get a new access token without logging in again.'
    )


# ─────────────────────────────────────────────────────────────────────────────

def sec_dashboard(pdf: Doc):
    pdf.h1('5. Dashboard Walkthrough')
    pdf.body(
        'The ClaudeOS dashboard has 8 pages, each accessible from the sidebar. '
        'Pages visible to you depend on your role -- admin users see all pages including the Admin Panel. '
        'Client and Viewer accounts only see pages relevant to their namespace. '
        'Click any item in the navigation list to switch pages instantly.'
    )

    pages = [
        (
            '5.1  Overview Page',
            'Your home screen -- system health, live activity, and quick dispatch.',
            'When you open the dashboard, this is the first page you see.',
            [
                'Five KPI counters at the top: total memory entries, agents, agent runs, workflows, and outputs',
                'System Status panel -- shows whether the database, API, and vector search are all running (green = healthy)',
                'Recent Events -- a live list of the last 8 agent runs with status icons',
                'Quick Dispatch -- a form on the right where you can run any agent immediately',
                'Memory by Namespace -- shows how many memory entries each client workspace has',
            ],
            [
                'Use Quick Dispatch: select an agent from the dropdown, choose a namespace (client), type your prompt, and click "Run Agent"',
                'You will receive a Run ID. You can check run results on the Agents page.',
                'Watch Recent Events to see if your agent run appears with a green tick (done) or red cross (failed)',
            ],
            'Agent starts running in the background. A success message shows the Run ID.'
        ),
        (
            '5.2  Agents Page',
            'Browse, search, and dispatch all 12 AI agents.',
            'Use this page when you need to run a specific agent and want to see its full details first.',
            [
                'Search bar -- type a word to filter agents by name, description, category, or tag',
                'Category filter -- dropdown to show only agents of one type (e.g. research, content)',
                'Agent cards -- each card shows the agent name, category badge, description, model, and token limit',
                'Dispatch Panel -- at the bottom: select agent, namespace, write prompt, toggle "Save output", and dispatch',
                'Run Status Checker -- after dispatching, click "Check run status" to see results',
                'Recent Runs Table -- last 20 agent runs with status, tokens used, and duration',
            ],
            [
                'Use the search bar to find the right agent for your task',
                'In the Dispatch Panel, select the agent, choose the correct client namespace, write your prompt, and click "Dispatch"',
                'If "Save output" is ticked, the AI\'s response will be saved to the Outputs page automatically',
            ],
            'A run starts in the background. The run ID appears. Use "Check run status" to see the response.'
        ),
        (
            '5.3  Memory Page',
            'Search, browse, and add knowledge entries that the AI remembers.',
            'Use this page to add information about a client, search for a fact you stored, or review all saved knowledge.',
            [
                'Stats bar -- shows total memory entries and a count per namespace',
                'Search tab -- search by keyword, meaning, or both. Select a namespace to narrow down',
                'Browse tab -- filter by namespace, category, and minimum confidence level',
                'Add Entry tab -- a form to add a new memory entry manually',
                'Import button -- imports memory files from the Claude Code memory folder',
            ],
            [
                'To search: go to the Search tab, type your query, choose a mode (text / semantic / both), and optionally select a namespace',
                'To add a memory: go to Add Entry, fill in the namespace, category, key (short label), value (the actual information), optional tags, and confidence level (0.0 to 1.0)',
                'To browse: use the Browse tab to see all entries for a client',
            ],
            'Search returns matching entries with category badge, confidence score, and tags. Add Entry saves the fact immediately.'
        ),
        (
            '5.4  Workflows Page',
            'View, trigger, and manage automated multi-step pipelines.',
            'Use this page to manually trigger a workflow, enable/disable scheduled workflows, or check past run history.',
            [
                'Workflows tab -- lists all 7 workflows with trigger type icon (clock = scheduled, play = manual)',
                'Each workflow can be expanded to see its description, trigger schedule, and a "Run now" button',
                'Run History tab -- all recent workflow runs with status, duration, and step details',
                'Scheduler tab -- shows the next scheduled run time for automatic workflows',
            ],
            [
                'To trigger a workflow manually: click on a workflow to expand it, select a namespace, optionally add context (key=value pairs), and click the Run button',
                'To enable or disable a workflow: click the Enable/Disable button inside the expanded workflow',
                'To view results: go to Run History, find your run, and click to expand the step log',
            ],
            'Workflow starts running. A run ID is returned. Check Run History for step-by-step results and final output.'
        ),
        (
            '5.5  Projects Page (Client Vault)',
            'Manage client namespaces, projects, and context files.',
            'Use this page to create or view client workspaces, manage projects within them, and upload context files.',
            [
                'Namespaces tab -- lists all client workspaces with icon, name, type, and workspace statistics',
                'Projects tab -- all projects grouped by client namespace, with status and priority',
                'Context Files tab -- manage per-namespace context files that agents read for background information',
                'New Namespace form -- create a new client workspace with name, description, colour, and icon',
                'New Project form -- add a project under an existing namespace',
            ],
            [
                'To view a namespace: click to expand and see workspace file stats and project count',
                'To add context: go to Context Files, select the namespace, enter a filename and content, and click Save',
                'To create a project: use the New Project form, fill in name, slug, tech stack, and priority',
            ],
            'New namespaces and projects appear immediately. Context files are saved to the vault and agents will read them on next run.'
        ),
        (
            '5.6  Outputs Page',
            'Browse, search, and download all AI-generated content.',
            'Use this page to find any report, draft, or analysis the AI has produced.',
            [
                'Browse tab -- filter outputs by namespace, type (report/draft/analysis/code/note/archive), and quantity',
                'Each output shows title, namespace, date, size, tags, and summary',
                'Actions per output: View full content, download as Markdown file, or delete',
                'Search tab -- full-text search across all outputs by keyword',
                'Stats tab -- output counts broken down by type and namespace',
            ],
            [
                'To find an output: use the Browse tab and set your filters, or go to Search and type keywords',
                'To read content: click "View" inside an output to expand the full text',
                'To download: click the Markdown download link next to the output',
                'To delete: click the Delete button and confirm',
            ],
            'Outputs display with metadata. Download delivers a .md file. Delete removes from database and file system.'
        ),
        (
            '5.7  Settings Page',
            'Monitor and control Supabase cloud sync.',
            'Use this page to check whether cloud backup is configured and to manually trigger a sync.',
            [
                'Connection badge -- green "Connected" or red "Not Configured"',
                'Summary metrics -- total rows pushed, failed rows, and auto-sync interval',
                'Manual Controls -- "Push All Now" button and per-table push option',
                'Table Sync State -- last sync time and push/fail counts per database table',
                'Sync Log -- history of the last 30 sync operations',
                'SQL Schema helper -- Supabase schema SQL for initial setup',
            ],
            [
                'To check sync status: just open the page -- the badge tells you immediately',
                'To trigger a manual sync: click "Push All Now" and wait for the success message',
                'If not configured: follow the instructions to add SUPABASE_URL and SUPABASE_SERVICE_KEY to your .env file',
            ],
            'Push All Now syncs all tables to Supabase. Results show rows pushed and any failures.'
        ),
        (
            '5.8  Admin Panel  (admin role only)',
            'Manage users, API keys, sessions, audit events, and security settings.',
            'Use this page to create or deactivate users, rotate API keys, review login history, and configure lockout policies. Only visible to admin accounts.',
            [
                'Users tab -- table of all accounts: username, role, namespace, status, last login',
                'Create User form -- username, email, password, role dropdown, namespace dropdown',
                'Per-user actions -- Deactivate, Unlock (clears lockout), Reset Password',
                'API Keys tab -- masked list of all keys, create new key, revoke any key',
                'Raw key shown once on creation -- copy it immediately, it cannot be retrieved again',
                'Audit Log tab -- paginated event log: logins, failures, lockouts, user changes',
                'Sessions tab -- active refresh token sessions with IP and device; revoke any session',
                'Security tab -- sliders for lockout threshold, lockout duration, token TTLs, self-registration toggle',
            ],
            [
                'To create a user: Users tab > fill in the Create User form > click Create',
                'To unlock a locked account: find the user row > click Unlock',
                'To force a password reset: find the user row > click Reset Password > set temp password',
                'To revoke an API key: API Keys tab > find the key > click Revoke',
                'To change lockout policy: Security tab > adjust Max Failed Attempts and Lockout Duration > Save',
            ],
            'Changes take effect immediately. Audit log records all admin actions automatically.'
        ),
    ]

    for name, purpose, when, what_you_see, what_you_do, expected in pages:
        pdf.h2(name)
        pdf.kv('Purpose', purpose)
        pdf.kv('When to use', when)
        pdf.ln(3)
        pdf.h3('What You See')
        pdf.bullets(what_you_see)
        pdf.h3('What You Do (Step-by-Step)')
        pdf.bullets(what_you_do)
        pdf.h3('Expected Output')
        pdf.body(expected)
        pdf.divider()


# ─────────────────────────────────────────────────────────────────────────────

def sec_agents(pdf: Doc):
    pdf.h1('6. AI Agents Reference')
    pdf.body(
        'ClaudeOS has 12 specialised AI agents. Each agent is built for a specific type of task. '
        'Below you will find a plain-English description of every agent, what input it needs from you, '
        'and what it produces.'
    )
    pdf.tip(
        'HOW TO USE AN AGENT',
        'Go to the Agents page (or the Quick Dispatch panel on the Overview page). '
        'Select the agent, choose the correct client namespace, write your prompt, and click Dispatch.'
    )

    agents = [
        # (name, category, purpose, input_needed, output_format, when_to_use)
        (
            'Morning Briefing Agent',
            'Operations',
            'Generates a structured daily briefing by reading recent memory and activity in the namespace.',
            'Usually runs automatically. If triggered manually, your prompt can specify focus areas (e.g. "Focus on RECI fleet issues today").',
            '5 sections: Priority Actions, Project Status, Client Updates, Scheduled Work, Notes.',
            'Every weekday morning when you want a summary of what needs attention today.'
        ),
        (
            'Research Agent',
            'Research',
            'Conducts deep, structured research on any topic. Distinguishes between high-confidence facts and uncertain claims.',
            'A clear research question or topic. Example: "Research electric vehicle adoption trends in Nigeria 2024".',
            '6 sections: Overview, Key Facts, Key Players, Implications, Sources, Next Actions.',
            'When you need thorough background information on a topic, market, or decision.'
        ),
        (
            'Writing Agent',
            'Content',
            'Drafts professional written content: reports, emails, proposals, blog posts. Adapts tone to match the namespace voice.',
            'Type of document, purpose, and key points to include. Example: "Write a 1-page project proposal for installing GPS trackers on RECI vehicles."',
            'A complete, ready-to-edit document in the requested format.',
            'When you need a first draft of any written content -- the agent does 80% of the work, you review and polish.'
        ),
        (
            'Communications Agent',
            'Communications',
            'Drafts client-facing messages: emails, WhatsApp messages, proposals. Matches the client\'s preferred communication style from memory.',
            'Who the message is for, what you need to say, and any relevant background. Example: "Draft a follow-up email to the RECI Transport client about the overdue payment."',
            'A ready-to-send message with subject line (for emails) and appropriate tone.',
            'When you need to communicate with a client and want the AI to draft it in the right tone.'
        ),
        (
            'Analysis Agent',
            'Analysis',
            'Analyses data, situations, or decisions. Produces structured findings, patterns, risks, and ranked recommendations.',
            'What you want analysed and any data or context. Example: "Analyse the booking trends from RECI Transport over the last month and identify the busiest routes."',
            '6 sections: Summary, Key Findings, Anomalies, Trends, Recommendations (ranked), Confidence Level.',
            'When you need to make sense of data or want a structured breakdown of a complex situation.'
        ),
        (
            'Client Manager Agent',
            'Operations',
            'Generates per-client status cards showing active projects, milestones, blockers, and immediate action items.',
            'A prompt describing which client or all clients. Example: "Give me a status summary for all active clients."',
            'One status card per client with: Active Projects, Next Milestone, Current Blockers, Required Actions.',
            'For weekly reviews, client meetings, or when you need a quick overview of all client work.'
        ),
        (
            'Scheduling Agent',
            'Operations',
            'Converts natural language scheduling requests into structured reminders saved to memory with expiry dates.',
            'A plain English scheduling request. Example: "Remind me to follow up with Ivycandy Hair on their wig delivery on Friday at 3pm."',
            'A confirmation message plus a memory entry saved with the correct expiry date.',
            'When you want to schedule a reminder or follow-up without leaving the dashboard.'
        ),
        (
            'RECI Transport Ops Agent',
            'Domain (RECI Transport only)',
            'Specialised analysis for RECI Transport Ltd. Reviews fleet utilisation, booking trends, revenue, and operational issues. '
            'This agent is locked to the reci-transport namespace and cannot run for other clients.',
            'A specific operational question or "Run a full fleet analysis." Example: "Which routes had the most cancellations this week?"',
            '5 sections: Fleet Utilisation, Booking Trends, Revenue Analysis, Anomalies, Action Items.',
            'For transport-specific analysis, fleet reports, or operational decision-making for RECI Transport.'
        ),
        (
            'Meta Orchestrator Agent',
            'System',
            'Breaks down a complex goal into an ordered sequence of agent tasks. '
            'Produces an execution plan that can be used to run multiple agents step by step.',
            'A high-level goal or complex task. Example: "Plan a full content strategy for Ivycandy Hair\'s social media launch next month."',
            'A JSON execution plan with steps, agents, prompts, and dependencies. Then used by the Meta Orchestration workflow.',
            'When your task is too complex for one agent and needs multiple agents working in sequence.'
        ),
        (
            'Memory Curator Agent',
            'System',
            'Reviews all memory entries in a namespace for duplicates, contradictions, and stale information. '
            'Recommends merges and expirations.',
            'Usually runs automatically (Sunday midnight). If triggered manually, specify the namespace.',
            'A list of memory recommendations: entries to merge, expire, or keep. Plus a summary.',
            'After many memory entries accumulate, or when search results seem noisy or contradictory.'
        ),
        (
            'Workflow Builder Agent',
            'System',
            'Converts a plain English description of an automation into a valid ClaudeOS workflow YAML file.',
            'A description of the automation you want. Example: "Every Monday morning, research the top 3 AI news stories and email me a summary."',
            'A complete workflow YAML definition ready to save and use.',
            'When you want to create a new automated pipeline without writing YAML yourself.'
        ),
        (
            'QA Agent',
            'Engineering',
            'Reviews code or outputs for quality, security issues (OWASP), Windows compatibility, and brand compliance.',
            'The code or content to review. Example: "Review this Python script for security issues."',
            'A markdown table: Severity | File/Item | Issue | Recommended Fix.',
            'Before deploying any code changes, or when reviewing AI-generated code for correctness.'
        ),
    ]

    for name, cat, purpose, inputs, outputs, when in agents:
        pdf.h3(name)
        pdf.kv('Category', cat)
        pdf.kv('What it does', purpose)
        pdf.kv('What to type', inputs)
        pdf.kv('Output format', outputs)
        pdf.kv('Best used for', when)
        pdf.ln(4)


# ─────────────────────────────────────────────────────────────────────────────

def sec_workflows(pdf: Doc):
    pdf.h1('7. Workflows Reference')
    pdf.body(
        'Workflows are automated pipelines -- sequences of AI agents that run one after another. '
        'Some run automatically on a schedule. Others you trigger manually with one click.'
    )
    pdf.tip(
        'HOW TO TRIGGER MANUALLY',
        'Go to the Workflows page. Click on any workflow to expand it. '
        'Select a namespace, optionally add context variables (key=value), and click the Run button.'
    )

    workflows = [
        (
            '7.1  Morning Briefing',
            'Monday to Friday, automatically at 07:00 WAT (West Africa Time)',
            'Reads all high-confidence memory entries in the chosen namespace, reviews recent agent runs, '
            'and produces a structured daily briefing covering what needs attention today.',
            'None required for automatic runs. For manual: optionally add context like "focus=fleet issues".',
            'A saved report with 5 sections: Priority Actions, Project Status, Client Updates, Scheduled Work, Notes. '
            'Appears in the Outputs page under type "report".'
        ),
        (
            '7.2  Memory Curation',
            'Automatically every Sunday at midnight WAT',
            'Reviews all memory entries for a namespace, identifies duplicates, contradictions, and stale information, '
            'and produces a set of recommendations for cleaning up the knowledge base.',
            'None. Runs automatically.',
            'A saved report listing which memory entries to merge, expire, or keep. '
            'The curator does not delete anything automatically -- a human reviews the recommendations.'
        ),
        (
            '7.3  Research Digest',
            'Manual -- triggered by you when needed',
            'Two-step pipeline: first the Research Agent does a deep dive on your topic; '
            'then the Writing Agent condenses the findings into a concise executive summary (around 300 words).',
            'topic -- the subject to research. Example: topic=solar energy trends in West Africa\n'
            'context_notes -- optional extra background. Example: context_notes=focus on off-grid solutions',
            'A saved executive summary with key findings, implications, and 3 recommended next actions.'
        ),
        (
            '7.4  Client Weekly Report',
            'Automatically every Friday at 17:00 WAT',
            'Two-step pipeline: first the Research Agent gathers a week\'s worth of activity, decisions, '
            'and outputs for the namespace; then the Writing Agent formats a professional status report.',
            'None. Runs automatically for each client namespace.',
            'A formatted weekly status report covering completed work, current blockers, and next steps. '
            'Saved to Outputs and ready to send to the client.'
        ),
        (
            '7.5  Analysis Run',
            'Manual -- triggered by you when needed',
            'Two-step pipeline: first the Analysis Agent produces a structured breakdown of the subject; '
            'then the Writing Agent reformats it into a clean, readable report under 500 words.',
            'subject -- what to analyse. Example: subject=Q3 booking data for RECI Transport\n'
            'data_summary -- any numbers or data to include\n'
            'analysis_goal -- what decision or question this analysis supports',
            'A structured analysis report with findings, patterns, risks, and ranked recommendations.'
        ),
        (
            '7.6  QA Sweep',
            'Automatically Monday to Friday at 06:00 WAT (before the morning briefing)',
            'Reviews the previous day\'s agent runs and outputs for quality issues, errors, '
            'anomalies, and anything that did not meet expected standards.',
            'None. Runs automatically.',
            'A pass/fail verdict for yesterday\'s activity, a list of flagged items, and recommended actions. '
            'Saved to Outputs as type "report".'
        ),
        (
            '7.7  Meta Orchestration',
            'Manual -- triggered when you have a complex, multi-step task',
            'Three-step pipeline: the Meta Orchestrator plans the task; the Research Agent gathers context; '
            'the Writing Agent synthesises a final action brief combining the plan and research.',
            'task -- the complex goal. Example: task=Build a content launch plan for Ivycandy Hair\'s new wig range\n'
            'namespace -- which client\n'
            'constraints -- any limits (e.g. constraints=budget under 50k, launch in 3 weeks)',
            'A comprehensive action brief combining an execution plan, supporting research, and clear next steps.'
        ),
    ]

    for name, schedule, what_it_does, inputs, output in workflows:
        pdf.h2(name)
        pdf.kv('Schedule', schedule)
        pdf.kv('What it does', what_it_does)
        pdf.kv('Inputs needed', inputs)
        pdf.kv('Output', output)
        pdf.ln(4)


# ─────────────────────────────────────────────────────────────────────────────

def sec_clients(pdf: Doc):
    pdf.h1('8. Client Workspace Sections')
    pdf.body(
        'ClaudeOS uses namespaces to keep each client\'s data completely separate. '
        'Below is a guide for each client workspace -- which agents are most relevant, '
        'which workflows apply, and example prompts to get you started.'
    )

    # RECI Transport
    pdf.h2('8.1  RECI Transport  (reci-transport)')
    pdf.body(
        'RECI Transport Ltd is a fleet and logistics client. '
        'ClaudeOS manages operational analysis, booking intelligence, fleet reporting, '
        'and weekly client status reports for this workspace.'
    )
    pdf.h3('Most Useful Agents')
    pdf.bullets([
        'RECI Transport Ops Agent -- the only agent locked exclusively to this namespace. '
        'Use for fleet utilisation, route analysis, and booking trends.',
        'Analysis Agent -- for interpreting booking data, revenue patterns, or driver performance',
        'Writing Agent -- for drafting operational reports or client communications',
        'Communications Agent -- for client-facing emails and follow-ups',
        'Briefing Agent -- for a daily summary of RECI-specific activity',
    ])
    pdf.h3('Scheduled Workflows (Automatic)')
    pdf.bullets([
        'Morning Briefing -- weekdays at 07:00 WAT: daily RECI activity summary',
        'Client Weekly Report -- Fridays at 17:00 WAT: weekly status report for RECI',
        'QA Sweep -- weekdays at 06:00 WAT: quality check on yesterday\'s outputs',
    ])
    pdf.h3('Example Prompts')
    pdf.code('Transport Ops Agent: "Analyse the booking data from this week. Which routes had the highest cancellation rate and why?"')
    pdf.code('Writing Agent: "Write a 1-page monthly fleet performance summary for the RECI Transport client."')
    pdf.code('Communications Agent: "Draft a professional follow-up email to the client reminding them about the pending invoice."')
    pdf.h3('Memory Tips for RECI Transport')
    pdf.bullets([
        'Save client contact preferences as "preference" category entries (e.g. key: email_tone, value: formal)',
        'Save fleet facts as "fact" entries (e.g. key: total_vehicles, value: 12 trucks + 4 vans)',
        'Save important decisions as "decision" entries (e.g. key: gps_install_decision, value: approved by director 15 May 2026)',
    ])
    pdf.divider()

    # Ivycandy Hair
    pdf.h2('8.2  Ivycandy Hair  (ivycandy-hair)')
    pdf.body(
        'Ivycandy Hair is a luxury wig and hair brand. '
        'ClaudeOS supports brand communications, content creation, client engagement, '
        'and business intelligence for this workspace. '
        'Note: Ivycandy Hair also has a separate order management system (ivycandy-hair-process) '
        'that handles WhatsApp orders, payment detection, and DHL shipping. '
        'ClaudeOS and the order system work independently -- ClaudeOS handles the AI/content side.'
    )
    pdf.h3('Most Useful Agents')
    pdf.bullets([
        'Writing Agent -- for blog posts, product descriptions, Instagram captions, and brand content',
        'Communications Agent -- for customer emails, WhatsApp templates, and supplier messages',
        'Research Agent -- for market research, competitor analysis, and beauty industry trends',
        'Analysis Agent -- for sales performance, customer feedback analysis, and seasonal trends',
        'Client Manager Agent -- for weekly business overview and project tracking',
    ])
    pdf.h3('Scheduled Workflows (Automatic)')
    pdf.bullets([
        'Morning Briefing -- weekdays at 07:00 WAT: daily Ivycandy business summary',
        'Client Weekly Report -- Fridays: weekly brand performance review',
        'Memory Curation -- Sundays: keeps knowledge base clean and up to date',
    ])
    pdf.h3('Example Prompts')
    pdf.code('Writing Agent: "Write 5 Instagram caption options for a new Brazilian wavy wig launch. Tone: luxurious, aspirational, Nigerian audience."')
    pdf.code('Research Agent: "Research the top wig trends for 2026 among Nigerian women aged 25-40."')
    pdf.code('Communications Agent: "Draft a professional apology email to a customer whose order was delayed by 3 days."')
    pdf.h3('Memory Tips for Ivycandy Hair')
    pdf.bullets([
        'Save brand voice as a "preference" entry (e.g. key: brand_voice, value: warm, aspirational, confident, Nigerian)',
        'Save product lines as "fact" entries (e.g. key: product_range, value: Brazilian wavy, Bone straight, Kinky curly)',
        'Save pricing as "context" entries for use in content (e.g. key: price_range, value: N25,000 - N150,000)',
    ])
    pdf.divider()

    # Faiyke AI
    pdf.h2('8.3  Faiyke AI  (faiyke-ai)')
    pdf.body(
        'Faiyke AI is an AI SaaS client. '
        'ClaudeOS supports research, technical writing, product strategy, '
        'and business analysis for this workspace.'
    )
    pdf.h3('Most Useful Agents')
    pdf.bullets([
        'Research Agent -- for AI industry research, competitor analysis, and market sizing',
        'Writing Agent -- for technical documentation, product copy, and pitch materials',
        'Analysis Agent -- for product metrics, user feedback analysis, and strategic decisions',
        'Meta Orchestrator -- for complex multi-step product or strategy tasks',
        'QA Agent -- for reviewing AI-generated code or technical outputs',
    ])
    pdf.h3('Example Prompts')
    pdf.code('Research Agent: "Research the current landscape of AI agent platforms in 2026. Focus on pricing models and target markets."')
    pdf.code('Writing Agent: "Write a 2-page executive summary for a pitch deck for Faiyke AI, positioning it as an enterprise AI automation platform."')
    pdf.code('Meta Orchestrator: "Plan a 3-month product launch campaign for Faiyke AI including research, content, and outreach strategy."')
    pdf.divider()

    # Personal / General
    pdf.h2('8.4  Personal & General  (personal / global)')
    pdf.body(
        'The "personal" and "global" namespaces are for internal use and general tasks not tied to a specific client. '
        'Use "global" for system-wide shared information. Use "personal" for your own scheduling, reminders, and research.'
    )
    pdf.h3('Common Uses')
    pdf.bullets([
        'Scheduling -- use the Scheduling Agent to create reminders (e.g. "Remind me to review Q2 accounts on June 1st")',
        'Personal research -- use the Research Agent for topics you are personally exploring',
        'System memory -- store facts that apply across all clients (e.g. your own contact details, standard rates)',
        'Draft templates -- save reusable document templates as memory entries',
    ])
    pdf.code('Scheduling Agent: "Remind me to follow up on the RECI payment on Friday 23rd May at 9am."')
    pdf.code('Research Agent (personal): "Summarise the key AI tools a digital agency should be using in 2026."')


# ─────────────────────────────────────────────────────────────────────────────

def sec_memory(pdf: Doc):
    pdf.h1('9. Memory System Guide')

    pdf.body(
        'ClaudeOS memory is like a smart filing cabinet. '
        'Every time you save a fact, decision, or preference, it gets stored with a label (key), '
        'the content (value), a category, and a confidence score. '
        'Before every agent run, ClaudeOS automatically reads the most relevant, '
        'high-confidence memory entries and includes them in the AI\'s context.'
    )
    pdf.body(
        'This means the more you save to memory, the smarter and more personalised '
        'every agent response becomes -- without you having to repeat yourself.'
    )

    pdf.h2('Memory Categories')
    pdf.table(
        ['Category', 'What It Stores', 'Example'],
        [
            ['fact', 'Objective, verifiable information', 'key: vehicle_count  value: 12 trucks'],
            ['decision', 'A choice or approval that was made', 'key: gps_install  value: approved May 2026'],
            ['context', 'Background information for a topic', 'key: q3_goals  value: expand to Abuja market'],
            ['preference', 'Client or personal preference', 'key: email_tone  value: formal and concise'],
            ['reminder', 'A time-based note to act on', 'key: invoice_followup  value: chase RECI on 30th'],
            ['insight', 'A conclusion or observation', 'key: peak_hours  value: bookings spike Friday 4-6pm'],
        ],
        widths=[28, 72, 70]
    )

    pdf.h2('How to Add a Memory Entry (Step-by-Step)')
    pdf.numbered([
        'Go to the Memory page from the sidebar',
        'Click the "Add Entry" tab',
        'Select the Namespace (e.g. reci-transport)',
        'Select the Category (e.g. fact)',
        'Enter a Key -- a short label for this entry (e.g. fleet_size)',
        'Enter a Value -- the actual information (e.g. 12 trucks and 4 vans, as of May 2026)',
        'Optionally add Tags (comma-separated, e.g. fleet, vehicles, reci)',
        'Set Confidence -- how sure you are this is correct (1.0 = certain, 0.5 = estimated)',
        'Click Save',
    ])

    pdf.h2('How to Search Memory')
    pdf.body('ClaudeOS has two search engines. You can use either or both:')
    pdf.bullets([
        'Text search -- finds entries that contain your exact words or similar keywords. '
        'Good for: "find that entry I wrote about GPS installers."',
        'Semantic search -- finds entries by meaning, even if you use completely different words. '
        'Good for: you type "vehicle tracking" and it finds an entry about "GPS monitoring."',
        'Both -- uses text and semantic together, then merges results. Best for thorough searches.',
    ])
    pdf.body('To search:')
    pdf.numbered([
        'Go to the Memory page, Search tab',
        'Type your query',
        'Select mode: text, semantic, or both',
        'Optionally select a namespace to narrow results',
        'Results appear with category badge, confidence score, and matching tags',
    ])

    pdf.h2('Confidence Scores Explained')
    pdf.table(
        ['Score', 'Meaning'],
        [
            ['1.0', 'Certain fact -- confirmed and verified'],
            ['0.9', 'Very high confidence -- strong source'],
            ['0.7', 'Reasonable confidence -- likely correct'],
            ['0.5', 'Estimated -- use with caution'],
            ['Below 0.5', 'Uncertain -- may need verification'],
        ],
        widths=[30, 140]
    )
    pdf.tip(
        'NOTE',
        'Agents only read memory entries with confidence 0.8 or above by default. '
        'Low-confidence entries are still stored and searchable, but they do not automatically '
        'influence agent responses.'
    )

    pdf.h2('Namespace Isolation')
    pdf.body(
        'Memory is completely separate per namespace. When you run an agent in the reci-transport namespace, '
        'it only reads reci-transport memory. It cannot see ivycandy-hair or personal entries. '
        'This ensures client privacy is maintained at all times.'
    )


# ─────────────────────────────────────────────────────────────────────────────

def sec_outputs(pdf: Doc):
    pdf.h1('10. Outputs Guide')

    pdf.body(
        'Every time an AI agent or workflow produces a document, report, draft, or analysis, '
        'ClaudeOS saves it automatically. These saved items are called outputs. '
        'You can browse, search, download, or delete them from the Outputs page at any time.'
    )

    pdf.h2('Output Types')
    pdf.table(
        ['Type', 'What It Contains'],
        [
            ['report', 'Completed analysis or status reports'],
            ['draft', 'Unfinished documents, proposals, or templates'],
            ['analysis', 'Data analysis, breakdowns, and findings'],
            ['code', 'Any code snippets or scripts produced by the AI'],
            ['note', 'Short notes or summaries'],
            ['archive', 'Older outputs moved to long-term storage'],
        ],
        widths=[30, 140]
    )

    pdf.h2('How to Browse Outputs (Step-by-Step)')
    pdf.numbered([
        'Go to the Outputs page from the sidebar',
        'In the Browse tab, select a Namespace (or leave as "all")',
        'Select a Type filter (or leave as "all")',
        'Set the Limit (20, 50, or 100 results)',
        'Results appear as expandable cards with title, date, size, and tags',
        'Click an output card to expand it and see the summary',
    ])

    pdf.h2('How to View Full Content')
    pdf.numbered([
        'Expand the output card',
        'Click the "View" button',
        'The full content appears below the card',
        'Click "Hide" to collapse it again',
    ])

    pdf.h2('How to Download an Output')
    pdf.numbered([
        'Expand the output card',
        'Click the "Download MD" link',
        'A Markdown (.md) file downloads to your browser\'s default download folder',
        'Open with any text editor, Word (via conversion), or Notion',
    ])

    pdf.h2('How to Search Outputs')
    pdf.numbered([
        'Go to the Outputs page, Search tab',
        'Type keywords (e.g. "RECI fleet report June")',
        'Optionally filter by namespace',
        'Click Search',
        'Results show title, namespace, type, and a relevance score',
    ])

    pdf.h2('Auto-Tagging')
    pdf.body(
        'ClaudeOS reads every output and automatically assigns relevant tags. '
        'For example, a document mentioning "fleet", "trucks", and "RECI" will be tagged with those words. '
        'This makes future searches much easier -- you do not have to remember exact titles.'
    )

    pdf.h2('Deleting an Output')
    pdf.tip(
        'WARNING',
        'Deleted outputs are permanently removed from the database and the file system. '
        'There is no undo. Download the output first if you might need it later.'
    )
    pdf.numbered([
        'Expand the output card',
        'Click the "Delete" button',
        'A confirmation prompt appears',
        'Click "Yes, delete" to confirm or "Cancel" to go back',
    ])


# ─────────────────────────────────────────────────────────────────────────────

def sec_technical(pdf: Doc):
    pdf.h1('11. Technical Reference  (Administrators)')
    pdf.body(
        'This section is for the person who installs, configures, and maintains ClaudeOS. '
        'End users do not need to read this section.'
    )

    pdf.h2('Environment Configuration (.env File)')
    pdf.body(
        'ClaudeOS reads all configuration from a .env file in the project root. '
        'Create this file before starting the system for the first time.'
    )
    pdf.code(
        '# Core\n'
        'ANTHROPIC_API_KEY=sk-ant-your-key-here\n'
        'CLAUDEOS_SECRET_KEY=change-this-to-a-random-string\n'
        'CLAUDEOS_ENV=development\n'
        'CLAUDEOS_VERSION=1.0.0\n\n'
        '# Ports\n'
        'FLASK_PORT=5000\n'
        'STREAMLIT_PORT=8501\n\n'
        '# Database\n'
        'SQLITE_PATH=data/claudeos.db\n'
        'CHROMADB_PATH=data/chromadb\n\n'
        '# Logging\n'
        'LOG_LEVEL=INFO\n'
        'LOG_PATH=logs\n\n'
        '# Optional: Supabase Cloud Sync\n'
        'SUPABASE_URL=https://your-project.supabase.co\n'
        'SUPABASE_SERVICE_KEY=your-service-role-key\n\n'
        '# Optional: Dev API key for dashboard auth\n'
        'CLAUDEOS_DEV_API_KEY=your-dev-api-key'
    )

    pdf.h2('Key File Locations')
    pdf.table(
        ['File / Folder', 'Description'],
        [
            ['data/claudeos.db', 'Main SQLite database (all tables)'],
            ['data/chromadb/', 'ChromaDB vector embeddings'],
            ['logs/api.log', 'API server log (max 5MB, rotates)'],
            ['vault/workspaces/', 'Per-namespace context and file storage'],
            ['outputs/store/', 'Saved output files organised by type/namespace'],
            ['agents/definitions/', '12 YAML agent definition files'],
            ['workflows/definitions/', '7 YAML workflow definition files'],
            ['.env', 'Environment configuration (never commit to git)'],
        ],
        widths=[60, 110]
    )

    pdf.h2('Auth & Security Database Tables')
    pdf.table(
        ['Table', 'Purpose'],
        [
            ['users', 'User accounts: username, password_hash (bcrypt), role, namespace, lockout state'],
            ['user_sessions', 'Refresh token store (stored as SHA-256 hash, never plaintext)'],
            ['auth_events', 'Full audit log: every login, failure, lockout, user action with IP and timestamp'],
            ['system_config', 'Runtime security settings: lockout threshold, token TTLs, self-register toggle'],
            ['api_keys', 'API keys for legacy/script access (stored as SHA-256 hash)'],
        ],
        widths=[40, 130]
    )

    pdf.h2('First-Time Setup Commands')
    pdf.body('Run these once after cloning the project:')
    pdf.code(
        'pip install -r requirements.txt\n'
        'python scripts/migrate.py\n'
        'python scripts/seed_agents.py\n'
        'python scripts/seed_workflows.py\n'
        'python scripts/seed_namespaces.py\n'
        'python scripts/create_admin.py --username admin --password Admin123!'
    )
    pdf.tip(
        'FIRST ADMIN',
        'The create_admin.py script creates the first admin account. '
        'Run it exactly once after migration. '
        'It will refuse to run if an admin already exists. '
        'Choose a strong password -- this account has full system access.'
    )

    pdf.h2('API Quick Reference')
    pdf.body('Auth endpoints (no token required):')
    pdf.table(
        ['Method', 'Endpoint', 'Description'],
        [
            ['GET', '/api/v1/health', 'Public health check (no auth)'],
            ['POST', '/api/v1/auth/login', 'Login -- returns access + refresh tokens'],
            ['POST', '/api/v1/auth/register', 'Self-register (if allow_self_register=1)'],
            ['POST', '/api/v1/auth/refresh', 'Renew access token using refresh token'],
            ['POST', '/api/v1/auth/logout', 'Revoke current session'],
            ['GET', '/api/v1/auth/me', 'Current user info'],
            ['POST', '/api/v1/auth/change-password', 'Change own password'],
        ],
        widths=[20, 75, 75]
    )
    pdf.body('All routes below require Authorization: Bearer <token> or X-API-Key header:')
    pdf.table(
        ['Method', 'Endpoint', 'Description'],
        [
            ['GET', '/api/v1/system/status', 'Full system health check'],
            ['GET', '/api/v1/agents', 'List all agents'],
            ['POST', '/api/v1/agents/{name}/run', 'Run an agent (returns run_id)'],
            ['GET', '/api/v1/agents/runs/{id}', 'Check agent run status'],
            ['POST', '/api/v1/memory/search', 'Search memory entries'],
            ['POST', '/api/v1/memory', 'Create memory entry'],
            ['GET', '/api/v1/workflows', 'List all workflows'],
            ['POST', '/api/v1/workflows/{name}/run', 'Trigger workflow'],
            ['GET', '/api/v1/outputs', 'List outputs'],
            ['GET', '/api/v1/sync/status', 'Check Supabase sync status'],
            ['POST', '/api/v1/sync/push', 'Push data to Supabase'],
        ],
        widths=[20, 75, 75]
    )
    pdf.body('Admin-only routes (admin role required):')
    pdf.table(
        ['Method', 'Endpoint', 'Description'],
        [
            ['GET/POST', '/api/v1/admin/users', 'List or create users'],
            ['PATCH/DELETE', '/api/v1/admin/users/{id}', 'Update or deactivate user'],
            ['POST', '/api/v1/admin/users/{id}/unlock', 'Clear lockout on user'],
            ['GET', '/api/v1/admin/audit', 'Paginated auth event log'],
            ['GET/DELETE', '/api/v1/admin/sessions', 'List or revoke sessions'],
            ['GET/POST', '/api/v1/admin/api-keys', 'List or create API keys'],
            ['GET/PATCH', '/api/v1/admin/security-settings', 'Read or update security config'],
        ],
        widths=[25, 80, 65]
    )

    pdf.h2('Supabase Cloud Sync Setup')
    pdf.numbered([
        'Create a free Supabase project at supabase.com',
        'In Supabase, go to SQL Editor and run the schema SQL from: sync/supabase_schema.sql',
        'Copy your Project URL and Service Role key from Supabase Settings > API',
        'Add SUPABASE_URL and SUPABASE_SERVICE_KEY to your .env file',
        'Restart ClaudeOS (start.ps1)',
        'Open the Settings page in the dashboard -- the badge should show green "Connected"',
        'Click "Push All Now" for the first full sync',
    ])


# ─────────────────────────────────────────────────────────────────────────────

def sec_troubleshooting(pdf: Doc):
    pdf.h1('12. Troubleshooting')

    issues = [
        (
            'Login screen does not appear -- dashboard loads directly',
            [
                'JWT token still in browser session from a previous login',
                'theme_toggle() or inject() not called before auth gate in app.py',
            ],
            [
                'Close and reopen the browser tab to force a new session',
                'If persistent: check dashboard/app.py that theme_toggle() and inject() are called BEFORE the jwt_token check',
            ]
        ),
        (
            'Login fails with "Invalid username or password"',
            [
                'Username or password typed incorrectly',
                'Account does not exist (admin has not created it yet)',
                'Account is deactivated',
            ],
            [
                'Double-check username and password (case-sensitive)',
                'Ask your administrator to confirm your account exists and is active',
                'If self-registration is enabled, try the Register tab to create a new account',
            ]
        ),
        (
            'Login fails with "Account locked" or "retry_after_seconds"',
            [
                '5 or more consecutive failed login attempts triggered automatic lockout',
            ],
            [
                'Wait for the lockout period to expire (default: 15 minutes)',
                'Or ask your administrator to unlock your account: Admin Panel > Users > Unlock',
                'After unlocking you can log in immediately',
            ]
        ),
        (
            '"Must change password" prompt appears on login',
            [
                'Administrator has flagged your account to require a password change',
                'This also occurs on first login if admin set must_change_password=1',
            ],
            [
                'Enter your current (temporary) password in the first field',
                'Enter your new password twice (min 10 chars, upper + lower + digit)',
                'Click Change Password -- you will be taken to the dashboard immediately',
            ]
        ),
        (
            'API returns 401 on every request',
            [
                'Access token has expired (default: 60 minutes)',
                'Wrong or missing Authorization header',
                'CLAUDEOS_SECRET_KEY changed since token was issued',
            ],
            [
                'Log out of the dashboard and log back in to get a fresh token',
                'For API scripts: re-call POST /auth/login to get a new token',
                'Verify the Authorization header is exactly: "Bearer <token>" (with the word Bearer)',
                'If secret key changed: all existing tokens are invalid -- all users must re-login',
            ]
        ),
        (
            'Self-registration tab is missing on login screen',
            [
                'allow_self_register is set to 0 in system_config',
            ],
            [
                'Ask your administrator to enable self-registration: Admin Panel > Security > Self-Registration toggle',
            ]
        ),
        (
            'API shows red dot (offline) in sidebar',
            [
                'The Flask API is not running',
                'A previous process is still holding port 5000',
                'An error occurred during startup',
            ],
            [
                'Open PowerShell and run: .\\scripts\\start.ps1',
                'Check the terminal for red error messages during startup',
                'Check logs/api.log for detailed error information',
                'If port 5000 is blocked: run netstat -ano | findstr :5000, then taskkill /F /PID <number>',
            ]
        ),
        (
            'Dashboard will not open (http://localhost:8501)',
            [
                'Streamlit has not started yet',
                'Port 8501 is in use by another process',
            ],
            [
                'Wait 10 seconds after running start.ps1 and try again',
                'Check the PowerShell terminal -- Streamlit startup messages should appear',
                'Kill port 8501: netstat -ano | findstr :8501 then taskkill /F /PID <number>',
                'Restart with: .\\scripts\\start.ps1',
            ]
        ),
        (
            'Agent run shows "failed" status',
            [
                'Prompt was empty or too short',
                'Anthropic API key is missing or expired',
                'The agent hit its token limit',
            ],
            [
                'Check the error message in the Run Status panel on the Agents page',
                'Verify ANTHROPIC_API_KEY is set in your .env file and is valid',
                'Try a shorter, more focused prompt',
                'Check logs/api.log for the detailed Python error',
            ]
        ),
        (
            'Memory search returns no results',
            [
                'No memory entries exist for this namespace yet',
                'Search terms do not match stored entries',
                'ChromaDB vector store is not initialised',
            ],
            [
                'Go to the Memory page, Browse tab -- check if any entries exist',
                'Try switching between text, semantic, and both search modes',
                'Try broader or different search terms',
                'Restart the server to reinitialise ChromaDB: .\\scripts\\start.ps1',
            ]
        ),
        (
            'Supabase sync shows "Not Configured"',
            [
                'SUPABASE_URL or SUPABASE_SERVICE_KEY is missing from .env',
                'Server has not been restarted after adding credentials',
            ],
            [
                'Open .env and verify both SUPABASE_URL and SUPABASE_SERVICE_KEY are present',
                'Restart the server: .\\scripts\\start.ps1',
                'Open Settings page and check the connection badge',
                'If still failing: check your Supabase project is active and the SQL schema has been run',
            ]
        ),
        (
            'Workflow did not run automatically',
            [
                'Workflow is disabled',
                'APScheduler did not start correctly',
                'Server was not running at the scheduled time',
            ],
            [
                'Go to Workflows page and check if the workflow shows as enabled (green dot)',
                'Check the Scheduler tab -- does the workflow appear with a next run time?',
                'Click "Reload Scheduler from DB" in the Scheduler tab',
                'Ensure the server runs continuously if you rely on scheduled workflows',
            ]
        ),
    ]

    for issue, causes, solutions in issues:
        pdf.h3(f'Problem: {issue}')
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(*GREEN)
        pdf.cell(0, 6, 'Possible causes:', ln=True)
        pdf.set_text_color(*TEXT)
        pdf.bullets(causes, indent=5)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(*GREEN)
        pdf.cell(0, 6, 'How to fix:', ln=True)
        pdf.set_text_color(*TEXT)
        pdf.bullets(solutions, indent=5)
        pdf.ln(3)


# ─────────────────────────────────────────────────────────────────────────────

def sec_glossary(pdf: Doc):
    pdf.h1('13. Glossary')
    pdf.body('Key terms used in this guide, explained in plain English.')

    terms = [
        ('Access Token', 'A short-lived JWT (60 minutes by default) sent in the Authorization header of every API request. Proves your identity without sharing your password.'),
        ('Admin Panel', 'A dashboard page visible only to admin-role users. Manages users, API keys, sessions, audit log, and security settings.'),
        ('Agent', 'A specialised AI worker with a specific job. ClaudeOS has 12 agents, each designed for a different task type.'),
        ('API', 'Application Programming Interface. The behind-the-scenes engine that the dashboard talks to. Runs on port 5000.'),
        ('APScheduler', 'The scheduling engine that runs workflows automatically at the right time. Starts with the server.'),
        ('Audit Log', 'A permanent record of every security-relevant action: logins, failures, logouts, user creation, lockout events, and password changes. Stored in the auth_events table.'),
        ('bcrypt', 'The password hashing algorithm used by ClaudeOS. 12 rounds of hashing means even if the database were stolen, passwords cannot be recovered. Never stored as plaintext.'),
        ('Bearer Token', 'The format for sending a JWT in an API request: Authorization: Bearer <token>. The word "Bearer" must be included exactly.'),
        ('ChromaDB', 'The vector database that powers semantic (meaning-based) memory search.'),
        ('Confidence Score', 'A number from 0.0 to 1.0 indicating how reliable a memory entry is. Agents only read entries above 0.8 by default.'),
        ('Dispatch', 'The action of sending a task to an AI agent. You dispatch an agent by writing a prompt and clicking Run.'),
        ('FTS5', 'Full-Text Search version 5. The SQLite keyword search engine used for memory and output text search.'),
        ('JWT', 'JSON Web Token. A digitally signed token that proves who you are. ClaudeOS issues JWTs on login and validates them on every API request.'),
        ('Lockout', 'An automatic security measure that temporarily blocks login after too many failed attempts. Default: 5 failures triggers a 15-minute lockout. Admin can unlock accounts early.'),
        ('Namespace', 'A private workspace for a specific client or project. Data does not cross between namespaces.'),
        ('Memory Entry', 'A saved piece of knowledge with a key, value, category, and confidence score. Agents read these automatically.'),
        ('Output', 'Any document, report, draft, or analysis produced by an AI agent and saved by ClaudeOS.'),
        ('PowerShell', 'The Windows command-line tool used to start ClaudeOS. Run it by right-clicking and selecting "Run as administrator".'),
        ('Refresh Token', 'A long-lived (7 days) opaque token used to get a new access token without logging in again. Stored as a secure hash. Keep it secret -- it cannot be recovered if lost.'),
        ('Role', 'The permission level assigned to a user account: admin, operator, client, or viewer. Determines which pages and data the user can access.'),
        ('Run ID', 'A unique identifier assigned to each agent or workflow run. Use it to check the status and results.'),
        ('Semantic Search', 'Searching by meaning rather than exact words. Finds relevant results even when you phrase things differently.'),
        ('Session', 'A login session stored in the user_sessions table. Contains the hashed refresh token, IP address, and device info. Admins can revoke sessions from the Admin Panel.'),
        ('SQLite', 'The local database file (claudeos.db) where all data is stored on disk.'),
        ('Streamlit', 'The Python framework that powers the ClaudeOS web dashboard. Runs on port 8501.'),
        ('Supabase', 'A cloud database service used for optional backup and sync. Configured in Settings page.'),
        ('WSGI', 'Web Server Gateway Interface. ClaudeOS uses "waitress" as its WSGI server (Windows-compatible, no Gunicorn needed).'),
        ('Waitress', 'The Windows-compatible web server that hosts the Flask API. Starts automatically via start.ps1.'),
        ('Watermark', 'The last-synced timestamp used by Supabase sync to only push new data, not re-send everything.'),
        ('Workflow', 'An automated pipeline of one or more AI agents that run in sequence. Can be scheduled or manually triggered.'),
        ('X-API-Key', 'A legacy authentication header for scripts and tools. Sent as X-API-Key: <key>. Keys are created in the Admin Panel and stored as SHA-256 hashes.'),
    ]

    for term, definition in terms:
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_text_color(*GREEN)
        pdf.cell(40, 6, term, ln=False)
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(*TEXT)
        pdf.multi_cell(0, 6, definition)
        pdf.ln(1)


# ─────────────────────────────────────────────────────────────────────────────
#  Build the PDF (two-pass for accurate TOC)
# ─────────────────────────────────────────────────────────────────────────────

def build(toc_offset: int = 0, page_map: dict = None, link_ids: dict = None) -> Doc:
    pdf = Doc(toc_offset=toc_offset, link_ids=link_ids)

    cover_page(pdf)

    if page_map is not None:
        toc_page(pdf, page_map, link_ids or {})

    sec_introduction(pdf)
    sec_design_principles(pdf)
    sec_getting_started(pdf)
    sec_auth_security(pdf)
    sec_dashboard(pdf)
    sec_agents(pdf)
    sec_workflows(pdf)
    sec_clients(pdf)
    sec_memory(pdf)
    sec_outputs(pdf)
    sec_technical(pdf)
    sec_troubleshooting(pdf)
    sec_glossary(pdf)

    return pdf


def main():
    print("ClaudeOS Documentation Generator")
    print("=" * 40)

    # Pass 1: no TOC, collect page numbers
    print("Pass 1: collecting section page numbers...")
    pdf1 = build(toc_offset=0, page_map=None, link_ids=None)
    raw_pages = pdf1._sections

    # Adjust: +1 for TOC page added in pass 2; -1 to show content page numbers
    content_pages = {title: pg for title, pg in raw_pages.items()}

    print(f"  Found {len(content_pages)} sections")

    # Pass 2: pre-create link IDs so TOC entries can reference them before
    # sections are rendered (links point forward into the document)
    print("Pass 2: generating final PDF with clickable table of contents...")
    pdf2 = Doc(toc_offset=1)
    link_ids = {title: pdf2.add_link() for title in raw_pages}
    # Pre-assign page=1 so links are valid before h1() updates them to correct pages
    for lid in link_ids.values():
        pdf2.set_link(lid, page=1)
    pdf2._link_ids = link_ids

    adjusted_pages = {title: pg - 1 for title, pg in content_pages.items()}

    cover_page(pdf2)
    toc_page(pdf2, adjusted_pages, link_ids)
    sec_introduction(pdf2)
    sec_design_principles(pdf2)
    sec_getting_started(pdf2)
    sec_auth_security(pdf2)
    sec_dashboard(pdf2)
    sec_agents(pdf2)
    sec_workflows(pdf2)
    sec_clients(pdf2)
    sec_memory(pdf2)
    sec_outputs(pdf2)
    sec_technical(pdf2)
    sec_troubleshooting(pdf2)
    sec_glossary(pdf2)

    pdf2.output(str(OUT))
    size_kb = round(OUT.stat().st_size / 1024, 1)
    print(f"\nDone! Output: {OUT}")
    print(f"Size: {size_kb} KB  |  Pages: {pdf2.page_no()}")
    print("\nOpen the PDF to review. Share the file at:")
    print(f"  {OUT}")


if __name__ == "__main__":
    main()
