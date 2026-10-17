# -*- coding: utf-8 -*-
"""Generate ClaudeOS Agents Documentation PDF."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import os

OUTPUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ClaudeOS_Agents_Documentation.pdf")

GREEN = HexColor("#407E3C")
LIGHT_GREEN = HexColor("#e8f5e9")
DARK = HexColor("#1a1a1a")
GRAY = HexColor("#555555")
LIGHT_GRAY = HexColor("#f5f5f5")
ACCENT = HexColor("#5a9e56")

AGENTS = [
    {
        "id": "01",
        "name": "Morning Briefing Agent",
        "agent_id": "agent-briefing-001",
        "category": "OPS",
        "description": (
            "The Morning Briefing Agent synthesises overnight context into a structured, "
            "actionable daily brief every weekday. It scans memory for urgent items, project "
            "updates, client activities, and scheduled workflows, then delivers a concise "
            "five-section report: Priority Actions (top 3 items), Project Status (one-line "
            "per active project), Client Updates, Scheduled Work, and Notes. It operates "
            "on WAT (UTC+1) timezone and pulls exclusively from live memory context — "
            "nothing is invented. Urgent or reminder-tagged items are always surfaced first. "
            "Designed for Rigwe's automation-first workflow, it eliminates the daily "
            "overhead of manually checking project states across multiple client namespaces."
        ),
        "example": (
            "Prompt: 'Generate morning briefing for Friday 22 May 2026.'\n"
            "Output: Priority action — 'RECI Dashboard: await Chinedu reply, June 15 "
            "deadline is 24 days out.' Project status table across 4 active projects. "
            "Client update noting follow-up email sent to chinedu@recitransport.com."
        ),
    },
    {
        "id": "02",
        "name": "Client Manager Agent",
        "agent_id": "agent-client-manager-001",
        "category": "OPS",
        "description": (
            "The Client Manager Agent generates structured status cards for every active "
            "client namespace. Each card contains: client name and type, active projects "
            "with on-track / at-risk / blocked status, next milestone with date, current "
            "blockers, actions required from Rigwe, and actions required from the client. "
            "It draws data from memory context and flags any missing information as "
            "[UNKNOWN] rather than inventing details — ensuring cards are always accurate. "
            "This agent is the primary tool for weekly client reviews, keeping deliverables "
            "visible and accountability clear across all three client namespaces: "
            "Ivycandy Hair, RECI Transport, and Website Portal."
        ),
        "example": (
            "Prompt: 'Generate status cards for all 3 clients.'\n"
            "Output: Three markdown cards — Ivycandy Hair (Design System: active, no "
            "deadline set), RECI Transport (Client Dashboard: blocked, June 15 target), "
            "Website Portal (Client Portal: active, role matrix undocumented)."
        ),
    },
    {
        "id": "03",
        "name": "Communications Agent",
        "agent_id": "agent-comms-001",
        "category": "COMMS",
        "description": (
            "The Communications Agent drafts all client-facing communications — emails, "
            "WhatsApp messages, proposals, and follow-ups. It tone-matches per client by "
            "reading their profile from memory context. The default register is professional "
            "but warm, aligned with Nigeria B2B communication standards. It never invents "
            "facts or figures; unknowns are clearly marked as [FILL IN] placeholders so "
            "the user can complete before sending. Email output always includes a subject "
            "line and signature block. WhatsApp messages are shorter and conversational "
            "with no formal headers. All output is ready-to-send with no internal "
            "ClaudeOS references included."
        ),
        "example": (
            "Prompt: 'Send a follow-up email to RECI Transport about the dashboard.'\n"
            "Output: Subject: 'Client Dashboard Project — Quick Alignment on Data, KPIs "
            "& Go-Live Date.' Professional email body requesting confirmation on data "
            "source, KPI scope, and June 15 deadline. Signed by Romanus Igwe, Operations."
        ),
    },
    {
        "id": "04",
        "name": "Research Agent",
        "agent_id": "agent-research-001",
        "category": "RESEARCH",
        "description": (
            "The Research Agent conducts deep, structured research on any topic and "
            "synthesises findings into a validated report. For every request it identifies "
            "what is known versus what requires verification, structures findings into "
            "Overview, Key Facts, Key Players, Implications, and Sources sections, and "
            "distinguishes high-confidence facts from uncertain claims. Each claim is "
            "labelled by source type: memory, known fact, or inference. Gaps — things "
            "that could not be verified — are explicitly flagged. Every report ends with "
            "three recommended next actions. It operates at 8,192 max tokens, making it "
            "the highest-capacity agent in the registry."
        ),
        "example": (
            "Prompt: 'What is the best data source for the RECI dashboard: SQLite or Supabase?'\n"
            "Output: Full comparison table across 7 factors (offline access, multi-user, "
            "Nigeria network, cost, complexity). Recommendation: start with SQLite, "
            "migrate to Supabase when team size confirmed. Three next actions listed."
        ),
    },
    {
        "id": "05",
        "name": "Analysis Agent",
        "agent_id": "agent-analysis-001",
        "category": "ANALYSIS",
        "description": (
            "The Analysis Agent processes raw data and produces structured analytical "
            "reports. Every report follows a fixed six-part structure: Executive Summary "
            "(2-3 sentences), Key Findings (bullet list), Anomalies (unusual or concerning "
            "patterns), Trends (patterns over time), Recommendations (3-5 concrete next "
            "actions ranked by impact), and a Confidence rating of HIGH / MEDIUM / LOW "
            "with justification. It never speculates beyond the provided data, flags data "
            "quality issues explicitly, and uses exact numbers without rounding unless "
            "noted. Temperature is set to 0.2 — the most deterministic of the non-system "
            "agents — ensuring consistent, repeatable analytical outputs."
        ),
        "example": (
            "Prompt: 'Analyse RECI Transport booking data for Q1 2026.'\n"
            "Output: Executive summary of volume trends, key finding that Lagos-Abuja "
            "route accounts for 42% of bookings, anomaly flagging a 30% drop in week 8, "
            "trend showing Friday peak bookings, and three recommendations including "
            "dynamic pricing for peak slots."
        ),
    },
    {
        "id": "06",
        "name": "Writing Agent",
        "agent_id": "agent-writing-001",
        "category": "CONTENT",
        "description": (
            "The Writing Agent produces polished written content matched to the voice and "
            "tone of the active namespace. It strictly avoids mixing client voices or "
            "styles — Ivycandy Hair copy reads differently from RECI Transport reports. "
            "Facts are never invented; unknowns are marked as [FILL IN]. Client-facing "
            "content uses professional, jargon-free British English (Nigeria business "
            "standard). Internal content is direct and terse. It handles drafts, reports, "
            "proposals, landing page copy, and formatted documentation. Operating at "
            "temperature 0.7 — the highest among content agents — it produces natural, "
            "varied prose rather than mechanical output."
        ),
        "example": (
            "Prompt: 'Write a project proposal for the Ivycandy Hair Design System.'\n"
            "Output: Professional proposal with executive summary, scope of work "
            "(brand tokens, component library, competitive analysis of 5 hair stores), "
            "deliverables list, timeline, and investment section with [FILL IN] "
            "placeholder for pricing."
        ),
    },
    {
        "id": "07",
        "name": "QA Agent",
        "agent_id": "agent-qa-001",
        "category": "ENGINEERING",
        "description": (
            "The QA Agent reviews code for bugs, security vulnerabilities, and quality "
            "issues. It checks against OWASP Top 10 (SQL injection, XSS, IDOR, and more), "
            "Windows compatibility (UTF-8 encoding, PowerShell syntax, no Unix-only "
            "commands), hardcoded secrets, brand compliance (#407E3C green + white for UI "
            "code), and common bugs including off-by-one errors, null handling, and "
            "exception swallowing. Output is a structured markdown table with columns: "
            "Severity, File, Line, Issue, Fix. Severity levels are CRITICAL (security / "
            "data loss), HIGH (correctness bugs), MED (quality issues), LOW (optional "
            "improvements), and INFO."
        ),
        "example": (
            "Prompt: 'Review core/auth.py for security issues.'\n"
            "Output: Table finding CRITICAL — hardcoded fallback secret key on line 47; "
            "HIGH — bare except swallowing auth exceptions on line 112; MED — "
            "missing LOWER() on username lookup causing case-sensitive login failure. "
            "Each finding includes the exact fix."
        ),
    },
    {
        "id": "08",
        "name": "RECI Transport Ops Agent",
        "agent_id": "agent-transport-ops-001",
        "category": "DOMAIN",
        "description": (
            "The RECI Transport Ops Agent is the only namespace-locked agent in ClaudeOS "
            "— it operates exclusively on reci-transport data and refuses cross-namespace "
            "access. It is the domain expert for Nigerian transport and fleet operations. "
            "Every report covers Fleet Utilisation (% vehicles booked vs available), "
            "Booking Trends (volume, peak times, popular routes), Revenue Snapshot, "
            "Anomalies, and Action Items. It understands Nigerian context: prices in NGN, "
            "major hubs (Lagos, Abuja, Port Harcourt), peak seasons (December, Easter, "
            "Eid), and fuel cost as a key variable. Output uses tables for all numbers."
        ),
        "example": (
            "Prompt: 'Generate fleet utilisation report for May 2026.'\n"
            "Output: Fleet at 73% utilisation, Lagos-Abuja at capacity Friday-Sunday, "
            "revenue NGN 4.2M for the month, anomaly flagging two vehicles with zero "
            "bookings for 3 consecutive weeks (maintenance risk), action: reassign "
            "idle vehicles to Ibadan route where demand exceeds supply."
        ),
    },
    {
        "id": "09",
        "name": "Scheduling Agent",
        "agent_id": "agent-scheduling-001",
        "category": "OPS",
        "description": (
            "The Scheduling Agent converts natural language scheduling requests into "
            "structured memory reminder entries with ISO 8601 datetimes and automatic "
            "expiry. It always converts relative times ('next Friday', 'in two weeks') "
            "to absolute UTC datetimes, uses WAT (UTC+1) for Nigeria-based tasks, and "
            "sets expiry one hour after the scheduled time so the reminder remains visible "
            "until actioned. Output is pure JSON — no explanation — containing the action, "
            "when, namespace, full memory entry definition, and a plain-English "
            "confirmation string. If the request is ambiguous, it makes the best "
            "interpretation and notes the ambiguity."
        ),
        "example": (
            "Prompt: 'Remind me to chase Chinedu on Friday if no reply.'\n"
            "Output JSON: action — 'Follow up with Chinedu re: RECI dashboard data source', "
            "when — '2026-05-29T08:00:00+01:00', namespace — 'reci-transport', "
            "expires_at — '2026-05-29T09:00:00+01:00', confirmation — 'Scheduled chase "
            "reminder for Friday 29 May at 08:00 WAT.'"
        ),
    },
    {
        "id": "10",
        "name": "Memory Curator Agent",
        "agent_id": "agent-memory-curator-001",
        "category": "SYSTEM",
        "description": (
            "The Memory Curator Agent maintains quality and hygiene across the ClaudeOS "
            "memory store. Given a batch of memory entries, it identifies duplicates "
            "(same key or >90% similar value), contradictions (same key, conflicting "
            "values), and stale entries (outdated by age and category). It recommends "
            "merges (keeping the newest, highest-confidence entry), expirations, and "
            "entries to keep unchanged. Output is structured JSON with merge, expire, "
            "keep, and summary keys. It is the most conservative agent in the system: "
            "when in doubt it keeps entries, and it never expires permanent categories "
            "(fact, decision, preference) unless confidence falls below 0.3."
        ),
        "example": (
            "Prompt: 'Curate global namespace memory (6 entries).'\n"
            "Output JSON: expire — ['test.handover' (superseded by handover.final)], "
            "keep — 5 entries including user profile, build skill, and handover marker. "
            "Summary: 'No duplicates or contradictions found. One redundant draft entry "
            "recommended for expiration.'"
        ),
    },
    {
        "id": "11",
        "name": "Meta Orchestrator Agent",
        "agent_id": "agent-meta-001",
        "category": "SYSTEM",
        "description": (
            "The Meta Orchestrator Agent is the coordination brain of ClaudeOS. It "
            "decomposes complex, multi-step goals into ordered agent invocation chains "
            "of up to five steps. For each step it specifies: which agent to use, the "
            "exact ready-to-execute prompt, the namespace, dependencies on prior steps, "
            "output variable names for chaining, and a rationale. Output is pure JSON — "
            "a complete execution plan. It does not execute the plan itself; it produces "
            "the blueprint that drives multi-agent workflows. It knows all 11 registered "
            "agents and their specialisations, and enforces the rule that transport "
            "operations always route to transport-ops-agent."
        ),
        "example": (
            "Prompt: 'Generate status cards for all 3 clients.'\n"
            "Output JSON plan: Step 1-3 — run client-manager-agent on each namespace "
            "in parallel (ivycandy-hair, reci-transport, website-portal). Step 4 — "
            "pass all three outputs to writing-agent to format into polished cards. "
            "Estimated 4 steps, 4,800 tokens."
        ),
    },
    {
        "id": "12",
        "name": "Workflow Builder Agent",
        "agent_id": "agent-workflow-builder-001",
        "category": "SYSTEM",
        "description": (
            "The Workflow Builder Agent converts plain-English automation descriptions "
            "into complete, valid ClaudeOS workflow YAML definitions. Given a description "
            "like 'run a morning briefing every weekday at 7am', it outputs a fully "
            "structured YAML with name, trigger type (cron, manual, or event), cron "
            "expression in WAT timezone, namespace, and ordered steps — each specifying "
            "the agent, input parameters, and output variable for chaining. Step IDs use "
            "snake_case. It validates agent names against the registered registry and uses "
            "{{variable}} syntax for passing outputs between steps. Output is YAML only — "
            "no explanation or commentary."
        ),
        "example": (
            "Prompt: 'Build a workflow that runs the briefing agent every weekday morning.'\n"
            "Output YAML: name — daily-morning-briefing, trigger — cron '0 6 * * 1-5' "
            "(07:00 WAT), namespace — global, step — briefing-agent with prompt 'Generate "
            "morning briefing for today', output_key — briefing_output."
        ),
    },
]


def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        rightMargin=2*cm,
        leftMargin=2*cm,
        topMargin=2*cm,
        bottomMargin=2*cm,
        title="ClaudeOS Agents Documentation",
        author="ClaudeOS v1.0",
    )

    styles = getSampleStyleSheet()

    style_cover_title = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontSize=28,
        textColor=white,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        spaceAfter=8,
    )
    style_cover_sub = ParagraphStyle(
        "CoverSub",
        parent=styles["Normal"],
        fontSize=13,
        textColor=HexColor("#c8e6c9"),
        alignment=TA_CENTER,
        fontName="Helvetica",
        spaceAfter=4,
    )
    style_cover_meta = ParagraphStyle(
        "CoverMeta",
        parent=styles["Normal"],
        fontSize=10,
        textColor=HexColor("#a5d6a7"),
        alignment=TA_CENTER,
        fontName="Helvetica",
    )
    style_agent_num = ParagraphStyle(
        "AgentNum",
        parent=styles["Normal"],
        fontSize=10,
        textColor=white,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    style_agent_name = ParagraphStyle(
        "AgentName",
        parent=styles["Normal"],
        fontSize=15,
        textColor=DARK,
        fontName="Helvetica-Bold",
        spaceBefore=10,
        spaceAfter=3,
    )
    style_agent_id = ParagraphStyle(
        "AgentId",
        parent=styles["Normal"],
        fontSize=8,
        textColor=GRAY,
        fontName="Helvetica",
        spaceAfter=6,
    )
    style_label = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        fontSize=8,
        textColor=white,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    style_body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=9.5,
        textColor=DARK,
        fontName="Helvetica",
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=8,
    )
    style_example_label = ParagraphStyle(
        "ExLabel",
        parent=styles["Normal"],
        fontSize=8.5,
        textColor=GREEN,
        fontName="Helvetica-Bold",
        spaceBefore=4,
        spaceAfter=3,
    )
    style_example_body = ParagraphStyle(
        "ExBody",
        parent=styles["Normal"],
        fontSize=9,
        textColor=HexColor("#2e4a2c"),
        fontName="Helvetica-Oblique",
        leading=13,
        alignment=TA_JUSTIFY,
    )
    style_toc_title = ParagraphStyle(
        "TocTitle",
        parent=styles["Normal"],
        fontSize=18,
        textColor=GREEN,
        fontName="Helvetica-Bold",
        spaceAfter=16,
        alignment=TA_CENTER,
    )
    style_toc_item = ParagraphStyle(
        "TocItem",
        parent=styles["Normal"],
        fontSize=10,
        textColor=DARK,
        fontName="Helvetica",
        leading=18,
    )

    story = []

    # ── COVER PAGE ──────────────────────────────────────────────────────────────
    cover_data = [[
        Paragraph("ClaudeOS", style_cover_title),
    ]]
    cover_table = Table(cover_data, colWidths=[17*cm])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 60),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(cover_table)

    sub_data = [[
        Paragraph("AI Operating System", style_cover_sub),
    ]]
    sub_table = Table(sub_data, colWidths=[17*cm])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
    ]))
    story.append(sub_table)

    divider_data = [[""]]
    divider_table = Table(divider_data, colWidths=[17*cm])
    divider_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(divider_table)

    meta_data = [[
        Paragraph("Agent Registry Documentation  •  Version 1.0  •  May 2026", style_cover_meta),
    ]]
    meta_table = Table(meta_data, colWidths=[17*cm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#2d5a29")),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 1*cm))

    overview_text = (
        "ClaudeOS is an AI Operating System built for automation-first power users. "
        "It unifies 12 specialised agents, a persistent memory engine, workflow automation, "
        "client namespace isolation, and a full authentication layer into a single "
        "authenticated control centre. This document describes each agent — what it does, "
        "how it works, and a practical example of its output."
    )
    overview_style = ParagraphStyle(
        "Overview",
        parent=styles["Normal"],
        fontSize=10,
        textColor=GRAY,
        fontName="Helvetica",
        leading=16,
        alignment=TA_JUSTIFY,
    )
    story.append(Paragraph(overview_text, overview_style))
    story.append(Spacer(1, 0.5*cm))

    # Stats bar
    stats = [
        ("12", "Agents"),
        ("8", "Categories"),
        ("claude-sonnet-4-6", "Model"),
        ("SQLite + ChromaDB", "Memory"),
    ]
    stats_data = [[Paragraph(f"<b>{v}</b><br/><font size=7>{l}</font>", ParagraphStyle(
        "stat", parent=styles["Normal"], fontSize=11, textColor=white,
        fontName="Helvetica-Bold", alignment=TA_CENTER, leading=14
    )) for v, l in stats]]
    stats_table = Table(stats_data, colWidths=[4.25*cm]*4)
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, white),
    ]))
    story.append(stats_table)
    story.append(PageBreak())

    # ── TABLE OF CONTENTS ────────────────────────────────────────────────────────
    story.append(Paragraph("Table of Contents", style_toc_title))
    story.append(HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=12))

    cat_colors = {
        "OPS": HexColor("#407E3C"),
        "COMMS": HexColor("#1565C0"),
        "RESEARCH": HexColor("#6A1B9A"),
        "ANALYSIS": HexColor("#E65100"),
        "CONTENT": HexColor("#00695C"),
        "ENGINEERING": HexColor("#B71C1C"),
        "DOMAIN": HexColor("#1B5E20"),
        "SYSTEM": HexColor("#37474F"),
    }

    toc_data = []
    for agent in AGENTS:
        cat = agent["category"]
        cat_color = cat_colors.get(cat, GREEN)
        cat_cell = Table([[Paragraph(cat, style_label)]], colWidths=[1.8*cm])
        cat_cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cat_color),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        toc_data.append([
            Paragraph(f"<b>{agent['id']}</b>", style_toc_item),
            Paragraph(agent["name"], style_toc_item),
            cat_cell,
            Paragraph(agent["agent_id"], ParagraphStyle(
                "toc_id", parent=styles["Normal"], fontSize=8,
                textColor=GRAY, fontName="Helvetica"
            )),
        ])

    toc_table = Table(toc_data, colWidths=[1*cm, 6.5*cm, 2.2*cm, 7.3*cm])
    toc_table.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [white, LIGHT_GRAY]),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, HexColor("#e0e0e0")),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    # ── AGENT PAGES ─────────────────────────────────────────────────────────────
    for i, agent in enumerate(AGENTS):
        cat = agent["category"]
        cat_color = cat_colors.get(cat, GREEN)

        # Header bar
        num_cell = Table([[Paragraph(agent["id"], style_agent_num)]], colWidths=[1.2*cm])
        num_cell.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cat_color),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        cat_badge = Table([[Paragraph(cat, style_label)]], colWidths=[2*cm])
        cat_badge.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cat_color),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        name_style = ParagraphStyle(
            f"hname_{i}",
            parent=styles["Normal"],
            fontSize=14,
            textColor=white,
            fontName="Helvetica-Bold",
        )
        id_style = ParagraphStyle(
            f"hid_{i}",
            parent=styles["Normal"],
            fontSize=8,
            textColor=HexColor("#c8e6c9"),
            fontName="Helvetica",
        )

        header_content = Table([[
            Paragraph(agent["name"], name_style),
            Paragraph(agent["agent_id"], id_style),
        ]], colWidths=[10*cm, 5.8*cm])
        header_content.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GREEN),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))

        header_row = Table([[num_cell, header_content, cat_badge]], colWidths=[1.2*cm, 13.5*cm, 2.3*cm])
        header_row.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(header_row)
        story.append(Spacer(1, 0.3*cm))

        # Description
        story.append(Paragraph(agent["description"], style_body))

        # Example box
        ex_box_data = [[
            Paragraph("EXAMPLE", style_example_label),
        ], [
            Paragraph(agent["example"].replace("\n", "<br/>"), style_example_body),
        ]]
        ex_table = Table(ex_box_data, colWidths=[17*cm])
        ex_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GREEN),
            ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GREEN),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("LINEAFTER", (0, 0), (0, -1), 3, GREEN),
            ("LINEBEFORE", (0, 0), (0, -1), 3, GREEN),
        ]))
        story.append(ex_table)

        if i < len(AGENTS) - 1:
            story.append(Spacer(1, 0.4*cm))
            story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#e0e0e0"), spaceAfter=6))

        if i % 2 == 1 and i < len(AGENTS) - 1:
            story.append(PageBreak())

    # ── BACK PAGE ────────────────────────────────────────────────────────────────
    story.append(PageBreak())
    back_data = [[
        Paragraph("ClaudeOS v1.0", ParagraphStyle(
            "back", parent=styles["Normal"], fontSize=22, textColor=white,
            fontName="Helvetica-Bold", alignment=TA_CENTER
        )),
    ]]
    back_table = Table(back_data, colWidths=[17*cm])
    back_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREEN),
        ("TOPPADDING", (0, 0), (-1, -1), 50),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 50),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(back_table)

    sub2_data = [[
        Paragraph(
            "12 agents  •  Persistent memory  •  Role-based auth  •  Multi-client namespaces",
            ParagraphStyle("back2", parent=styles["Normal"], fontSize=10, textColor=HexColor("#c8e6c9"),
                           fontName="Helvetica", alignment=TA_CENTER)
        ),
    ]]
    sub2_table = Table(sub2_data, colWidths=[17*cm])
    sub2_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#2d5a29")),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(sub2_table)

    doc.build(story)
    print(f"PDF generated: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
