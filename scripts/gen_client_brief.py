"""
Generate FaiykeOS Client Brief PDF — two-pager for client presentations.
Output: docs/FaiykeOS_Client_Brief.pdf
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import os

# ── Brand ────────────────────────────────────────────────────────────────────
GREEN      = colors.HexColor("#407E3C")
GREEN_DARK = colors.HexColor("#2e5c2b")
GREEN_LITE = colors.HexColor("#e8f5e5")
WHITE      = colors.white
GREY_DARK  = colors.HexColor("#1a1a1a")
GREY_MID   = colors.HexColor("#4a4a4a")
GREY_LITE  = colors.HexColor("#f5f5f5")
GREY_RULE  = colors.HexColor("#d0d0d0")

W, H = A4   # 595.28 x 841.89 pts
ML = MR = 18*mm
MT = MB = 16*mm

# ── Styles ───────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def S(name, **kw):
    return ParagraphStyle(name, **kw)

hero_title = S("HeroTitle",
    fontName="Helvetica-Bold", fontSize=26, leading=32,
    textColor=WHITE, alignment=TA_LEFT, spaceAfter=4)

hero_sub = S("HeroSub",
    fontName="Helvetica", fontSize=11, leading=16,
    textColor=colors.HexColor("#d4ecd1"), alignment=TA_LEFT)

page_label = S("PageLabel",
    fontName="Helvetica-Bold", fontSize=7, leading=9,
    textColor=WHITE, alignment=TA_LEFT, spaceBefore=0, spaceAfter=0)

section_head = S("SectionHead",
    fontName="Helvetica-Bold", fontSize=13, leading=16,
    textColor=GREEN_DARK, spaceBefore=10, spaceAfter=4)

sub_head = S("SubHead",
    fontName="Helvetica-Bold", fontSize=10, leading=13,
    textColor=GREY_DARK, spaceBefore=6, spaceAfter=2)

body = S("Body",
    fontName="Helvetica", fontSize=9, leading=14,
    textColor=GREY_MID, alignment=TA_JUSTIFY, spaceAfter=4)

body_bold = S("BodyBold",
    fontName="Helvetica-Bold", fontSize=9, leading=14,
    textColor=GREY_DARK, spaceAfter=2)

pitch = S("Pitch",
    fontName="Helvetica-BoldOblique", fontSize=11, leading=16,
    textColor=GREEN_DARK, alignment=TA_CENTER,
    spaceBefore=6, spaceAfter=6)

footer_style = S("Footer",
    fontName="Helvetica", fontSize=7.5, leading=10,
    textColor=colors.HexColor("#888888"), alignment=TA_CENTER)

# ── Table helpers ─────────────────────────────────────────────────────────────
def make_table(data, col_widths, header_bg=GREEN, row_shade=GREEN_LITE):
    """Styled two-column comparison or feature table."""
    style = TableStyle([
        # Header row
        ("BACKGROUND",    (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 8.5),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("LEFTPADDING",   (0, 0), (-1, 0), 8),
        ("RIGHTPADDING",  (0, 0), (-1, 0), 8),
        # Body rows
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("TEXTCOLOR",     (0, 1), (-1, -1), GREY_MID),
        ("TOPPADDING",    (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING",   (0, 1), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 1), (-1, -1), 8),
        # Alternating rows — bounded to actual row count
        *[("BACKGROUND", (0, i), (-1, i), row_shade if i % 2 == 1 else WHITE)
          for i in range(1, len(data))],
        # Grid
        ("GRID",          (0, 0), (-1, -1), 0.4, GREY_RULE),
        ("LINEABOVE",     (0, 0), (-1, 0), 1.5, header_bg),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ])
    t = Table(data, colWidths=col_widths)
    t.setStyle(style)
    return t

def cell(text, bold=False, color=None):
    st = body_bold if bold else body
    if color:
        return Paragraph(f'<font color="{color}">{text}</font>', st)
    return Paragraph(text, st)

# ── Hero banner (drawn on canvas, not flowable) ───────────────────────────────
class HeroBanner:
    """Full-width green header block drawn directly on the canvas."""
    def __init__(self, page_num, title_line1, title_line2, subtitle):
        self.page_num = page_num
        self.l1 = title_line1
        self.l2 = title_line2
        self.sub = subtitle

    def wrap(self, aw, ah): return (aw, 52*mm)
    def draw(self): pass  # handled in onFirstPage / onLaterPages

def build_hero(canvas, doc, page_num, l1, l2, sub):
    canvas.saveState()
    bh = 52*mm
    y0 = H - bh
    # background
    canvas.setFillColor(GREEN)
    canvas.rect(0, y0, W, bh, fill=1, stroke=0)
    # subtle dark strip at bottom of banner
    canvas.setFillColor(GREEN_DARK)
    canvas.rect(0, y0, W, 2, fill=1, stroke=0)
    # page label pill
    pill_x, pill_y = ML, H - 11*mm
    canvas.setFillColor(GREEN_DARK)
    canvas.roundRect(pill_x, pill_y, 38*mm, 5*mm, 2, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 7)
    canvas.drawString(pill_x + 3*mm, pill_y + 1.5*mm,
                      f"PAGE {page_num} OF 2  ·  CLIENT BRIEF")
    # title
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 24)
    canvas.drawString(ML, H - 22*mm, l1)
    canvas.setFont("Helvetica-Bold", 24)
    canvas.drawString(ML, H - 33*mm, l2)
    # subtitle
    canvas.setFillColor(colors.HexColor("#c8e6c4"))
    canvas.setFont("Helvetica", 10)
    canvas.drawString(ML, H - 43*mm, sub)
    canvas.restoreState()

def build_footer(canvas, doc, page_num):
    canvas.saveState()
    canvas.setFillColor(GREEN)
    canvas.rect(0, 0, W, 8*mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(W/2, 2.8*mm,
        "FaiykeOS  ·  faiyke.ai  ·  Confidential — for client use only")
    canvas.restoreState()

# ── Document builder ──────────────────────────────────────────────────────────
def build():
    out_path = os.path.join(os.path.dirname(__file__), "..", "docs", "FaiykeOS_Client_Brief.pdf")
    out_path = os.path.normpath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=A4,
        leftMargin=ML, rightMargin=MR,
        topMargin=55*mm,   # leave room for hero banner
        bottomMargin=14*mm,
        title="FaiykeOS — Client Brief",
        author="Faiyke AI",
        subject="AI Operating System — Two-Page Overview",
    )

    CW = W - ML - MR  # content width

    # ── Page 1 content ────────────────────────────────────────────────────────
    p1 = []

    p1.append(Paragraph("The Problem It Solves", section_head))
    p1.append(Paragraph(
        "Most businesses using AI end up with a fragmented mess — one tool for chat, another for "
        "automation, manual copy-paste between systems, no audit trail, no memory across sessions, "
        "no control over who sees what. Every conversation starts from zero. Every output lives "
        "somewhere random. <b>FaiykeOS fixes this.</b>",
        body))

    p1.append(Spacer(1, 3*mm))
    p1.append(Paragraph("What FaiykeOS Is", section_head))
    p1.append(Paragraph(
        "<b>FaiykeOS is an AI Operating System</b> — a private, self-hosted control center that "
        "unifies AI agents, automated workflows, persistent memory, and client management into one "
        "authenticated platform.",
        body))
    p1.append(Paragraph(
        "Think of it as your own private AI brain: it <b>remembers everything</b>, executes work "
        "autonomously, routes tasks to the right agent, and delivers outputs you can track, search, "
        "and export — all behind a secure login. Built on <b>Claude Sonnet</b> (Anthropic's flagship "
        "model), it runs entirely on your infrastructure. No data leaves to a third party.",
        body))

    p1.append(Spacer(1, 3*mm))
    p1.append(Paragraph("Who It's For", section_head))

    who_data = [
        [Paragraph("<b>Who</b>", body_bold), Paragraph("<b>How They Use It</b>", body_bold)],
        [cell("Agencies"), cell("Isolated AI workspace per client — white-labeled with client branding")],
        [cell("Businesses"), cell("AI agents doing real operational work: analysis, research, briefings, reports")],
        [cell("Teams"), cell("Role-based access — admins, operators, clients, viewers all scoped correctly")],
    ]
    p1.append(make_table(who_data, [CW * 0.28, CW * 0.72]))

    p1.append(Spacer(1, 4*mm))
    p1.append(Paragraph("The Core Capability Stack", section_head))

    stack_data = [
        [Paragraph("<b>Layer</b>", body_bold), Paragraph("<b>What It Does</b>", body_bold)],
        [cell("AI Agent Registry"),
         cell("12 specialized agents — analysis, research, briefing, writing, client management. "
              "Streaming responses. Every run scored for quality automatically.")],
        [cell("Memory Engine"),
         cell("Hybrid BM25 + vector search (RAG). Agents remember your business, clients, and history "
              "across every session. Memory consolidates automatically every 4 hours.")],
        [cell("Workflow Automation"),
         cell("7 pre-built pipelines. Schedule on a cron, trigger via webhook from any external tool, "
              "or run on demand. No human in the loop required.")],
        [cell("Client Vault"),
         cell("Each client gets a namespace-isolated workspace. Their data never touches another "
              "client's data.")],
        [cell("Output Manager"),
         cell("Every AI output is tagged, saved, full-text searchable, and exportable across all "
              "historical sessions.")],
        [cell("Ticketing System"),
         cell("Built-in task tracker with SLA tiers, staff assignment, and email notifications.")],
    ]
    p1.append(make_table(stack_data, [CW * 0.26, CW * 0.74]))

    # ── Page 2 content ────────────────────────────────────────────────────────
    p2 = []

    p2.append(Paragraph("The Dashboard — Role-Based Experience", section_head))
    p2.append(Paragraph(
        "Users log into a branded web interface that adapts entirely by role. Every client sees "
        "only their namespace: their AI runs, their outputs, their usage stats, their tickets. "
        "A <b>Namespace Pulse Score</b> (0–100 composite) shows namespace health at a glance.",
        body))

    roles_data = [
        [Paragraph("<b>Role</b>", body_bold), Paragraph("<b>What They See</b>", body_bold)],
        [cell("Admin"),     cell("Everything — agents, workflows, memory, vaults, audit logs, user management, system observability")],
        [cell("Operator"),  cell("All namespaces: run agents + workflows; no user management access")],
        [cell("Client"),    cell("Own namespace only: AI runs, outputs, usage dashboard, tickets, Pulse Score")],
        [cell("Viewer"),    cell("Own namespace, read-only")],
        [cell("Staff"),     cell("Assigned tickets only")],
    ]
    p2.append(make_table(roles_data, [CW * 0.18, CW * 0.82]))

    p2.append(Spacer(1, 4*mm))
    p2.append(Paragraph("A Day in the Platform", section_head))

    steps = [
        ("1  Login", "Client logs in to their branded dashboard — company colors, name, and logo."),
        ("2  Run Agent", "Submit a request to the Analysis Agent. Streaming response in seconds, saved automatically to output history."),
        ("3  Automation", "Workflow Engine fires a scheduled morning briefing. No human trigger needed."),
        ("4  Tickets", "A task is raised; assigned staff notified by email; SLA clock starts."),
        ("5  Export", "At end of week, client exports all outputs as a report. Full history searchable."),
    ]
    step_data = [[Paragraph(f"<b>{s}</b>", body_bold), Paragraph(d, body)] for s, d in steps]
    step_data.insert(0, [Paragraph("<b>Step</b>", body_bold), Paragraph("<b>What Happens</b>", body_bold)])
    p2.append(make_table(step_data, [CW * 0.22, CW * 0.78]))

    p2.append(Spacer(1, 4*mm))
    p2.append(Paragraph("FaiykeOS vs Generic AI Tools", section_head))

    vs_data = [
        [Paragraph("<b>Generic AI (ChatGPT etc.)</b>", body_bold), Paragraph("<b>FaiykeOS</b>", body_bold)],
        [cell("No memory between sessions"),           cell("Persistent hybrid RAG memory — agents remember context")],
        [cell("Single user, single conversation"),     cell("Multi-user, role-based, namespace-isolated")],
        [cell("No audit trail"),                       cell("Full audit log on every action, every run")],
        [cell("No automation"),                        cell("7 workflows + webhook triggers + cron scheduling")],
        [cell("Data sent to external servers"),        cell("Self-hosted — your data never leaves your machine")],
        [cell("No client management"),                 cell("White-labeled per client with usage dashboards")],
        [cell("No quality control"),                   cell("Every AI response scored by LLM-as-Judge automatically")],
    ]
    p2.append(make_table(vs_data, [CW * 0.46, CW * 0.54]))

    p2.append(Spacer(1, 4*mm))
    p2.append(Paragraph("Security & Reliability", section_head))

    sec_items = [
        "JWT authentication — 60-minute access tokens, 24-hour session window, bcrypt password hashing",
        "Account lockout after 5 failed attempts · All routes require authentication",
        "Rate limiting, CORS controls, full security response headers on every API response",
        "Automatic daily database backup with 7-backup retention",
        "115 automated tests in the test suite · Zero public endpoints except /health",
    ]
    for item in sec_items:
        p2.append(Paragraph(f"<b>·</b>  {item}", body))

    p2.append(Spacer(1, 4*mm))
    p2.append(Paragraph("Pricing", section_head))

    price_data = [
        [Paragraph("<b>Tier</b>", body_bold),
         Paragraph("<b>Price</b>", body_bold),
         Paragraph("<b>Best For</b>", body_bold)],
        [cell("Developer"), cell("$197 one-time"),           cell("Solo operator, personal use")],
        [cell("Business"),  cell("$997 + $147/mo"),          cell("Small team, 1–3 client namespaces")],
        [cell("Agency"),    cell("$997 flat or $497+$97/mo"), cell("Unlimited client namespaces + reseller rights")],
    ]
    p2.append(make_table(price_data, [CW * 0.22, CW * 0.30, CW * 0.48]))

    p2.append(Spacer(1, 5*mm))
    p2.append(HRFlowable(width=CW, thickness=1.5, color=GREEN, spaceAfter=5*mm))
    p2.append(Paragraph(
        "\u201cFaiykeOS gives you a private AI command center — your agents, your memory, "
        "your clients, your workflows — running on your terms, not a third party\u2019s.\u201d",
        pitch))

    # ── Assemble with page callbacks ──────────────────────────────────────────
    story = []

    # Page 1 sentinel
    class Page1Start:
        def wrap(self, aw, ah): return (0, 0)
        def draw(self): pass
        def __repr__(self): return "Page1Start"

    story += p1

    from reportlab.platypus import PageBreak
    story.append(PageBreak())
    story += p2

    page_meta = {1: ("THE PROBLEM & THE PLATFORM",
                     "What FaiykeOS is and why it exists",
                     "Your AI. Your Data. Your Rules."),
                 2: ("THE PLATFORM IN PRACTICE",
                     "Dashboard, security, comparison, pricing",
                     "From login to delivered output — no human in the loop.")}

    def on_page(canvas, doc):
        pn = doc.page
        l1, l2, sub = page_meta.get(pn, ("", "", ""))
        build_hero(canvas, doc, pn, l1, l2, sub)
        build_footer(canvas, doc, pn)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF written -> {out_path}")
    return out_path

if __name__ == "__main__":
    build()
