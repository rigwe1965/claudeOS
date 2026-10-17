"""Convert QA_TEST_PLAN.md to PDF using reportlab."""
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Brand colors
GREEN = colors.HexColor("#407E3C")
GREEN_LIGHT = colors.HexColor("#5a9e56")
GREEN_BG = colors.HexColor("#e8f5e2")
DARK = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#555555")
CODE_BG = colors.HexColor("#f4f4f4")
WHITE = colors.white
TABLE_HEADER_BG = colors.HexColor("#407E3C")
TABLE_ROW_ALT = colors.HexColor("#f0f8ee")

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def build_styles():
    base = getSampleStyleSheet()

    styles = {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=22,
            textColor=WHITE, alignment=TA_CENTER,
            spaceAfter=4, spaceBefore=0,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontName="Helvetica", fontSize=10,
            textColor=WHITE, alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "h1": ParagraphStyle(
            "h1", fontName="Helvetica-Bold", fontSize=14,
            textColor=WHITE, spaceBefore=14, spaceAfter=4,
            backColor=GREEN, borderPad=5, leading=20,
        ),
        "h2": ParagraphStyle(
            "h2", fontName="Helvetica-Bold", fontSize=11,
            textColor=GREEN, spaceBefore=10, spaceAfter=3,
            borderPad=2,
        ),
        "h3": ParagraphStyle(
            "h3", fontName="Helvetica-Bold", fontSize=10,
            textColor=DARK, spaceBefore=7, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=9,
            textColor=DARK, spaceAfter=3, leading=14,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName="Helvetica", fontSize=9,
            textColor=DARK, spaceAfter=2, leading=13,
            leftIndent=14, bulletIndent=4,
        ),
        "code": ParagraphStyle(
            "code", fontName="Courier", fontSize=8,
            textColor=DARK, backColor=CODE_BG,
            spaceAfter=6, spaceBefore=4, leading=12,
            leftIndent=8, rightIndent=8, borderPad=4,
        ),
        "blockquote": ParagraphStyle(
            "blockquote", fontName="Helvetica-Oblique", fontSize=9,
            textColor=MUTED, leftIndent=16, spaceAfter=4,
            borderPad=3, backColor=GREEN_BG,
        ),
    }
    return styles


def escape(text: str) -> str:
    """Escape reportlab XML special chars."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_table(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        if re.match(r"^\s*\|[-:| ]+\|\s*$", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def build_table_flowable(rows: list[list[str]], styles: dict):
    if not rows:
        return None
    col_count = max(len(r) for r in rows)
    # Normalize row lengths
    rows = [r + [""] * (col_count - len(r)) for r in rows]

    # Header row styled separately
    header = [Paragraph(f"<b>{escape(c)}</b>", ParagraphStyle(
        "th", fontName="Helvetica-Bold", fontSize=8,
        textColor=WHITE, alignment=TA_CENTER,
    )) for c in rows[0]]

    data = [header]
    for i, row in enumerate(rows[1:], 1):
        data.append([Paragraph(escape(c), ParagraphStyle(
            "td", fontName="Helvetica", fontSize=8,
            textColor=DARK, alignment=TA_LEFT, leading=11,
        )) for c in row])

    col_width = (PAGE_W - 2 * MARGIN) / col_count
    t = Table(data, colWidths=[col_width] * col_count, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, TABLE_ROW_ALT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def md_to_flowables(md_text: str, styles: dict) -> list:
    flowables = []
    lines = md_text.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code block
        if line.strip().startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_text = "\n".join(code_lines)
            flowables.append(Paragraph(escape(code_text).replace("\n", "<br/>"), styles["code"]))
            i += 1
            continue

        # Table
        if line.strip().startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = parse_table(table_lines)
            t = build_table_flowable(rows, styles)
            if t:
                flowables.append(Spacer(1, 4))
                flowables.append(t)
                flowables.append(Spacer(1, 6))
            continue

        # Headings
        if line.startswith("# "):
            text = line[2:].strip()
            flowables.append(Spacer(1, 6))
            # Title banner
            data = [[Paragraph(escape(text), styles["title"])]]
            banner = Table(data, colWidths=[PAGE_W - 2 * MARGIN])
            banner.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), GREEN),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ]))
            flowables.append(banner)
            flowables.append(Spacer(1, 6))
            i += 1
            continue

        if line.startswith("## "):
            text = line[3:].strip()
            flowables.append(Spacer(1, 8))
            flowables.append(HRFlowable(width="100%", thickness=1.5, color=GREEN))
            flowables.append(Paragraph(escape(text), styles["h2"]))
            i += 1
            continue

        if line.startswith("### "):
            text = line[4:].strip()
            flowables.append(Paragraph(escape(text), styles["h3"]))
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            text = line[2:].strip()
            flowables.append(Paragraph(escape(text), styles["blockquote"]))
            i += 1
            continue

        # HR
        if re.match(r"^---+$", line.strip()):
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # Bullet / numbered list
        bullet_match = re.match(r"^(\s*)[-*]\s+(.*)", line)
        num_match = re.match(r"^(\s*)\d+\.\s+(.*)", line)
        if bullet_match or num_match:
            m = bullet_match or num_match
            indent_level = len(m.group(1)) // 2
            text = m.group(2)
            # inline bold/code
            text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(text))
            text = re.sub(r"`(.+?)`", r'<font name="Courier">\1</font>', text)
            style = ParagraphStyle(
                "bullet_i", parent=styles["bullet"],
                leftIndent=14 + indent_level * 12,
            )
            num_prefix_match = re.match(r"^\s*(\d+)\.", line)
            prefix = "• " if bullet_match else f"{num_prefix_match.group(1) if num_prefix_match else '1'}. "
            flowables.append(Paragraph(prefix + text, style))
            i += 1
            continue

        # Empty line
        if not line.strip():
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # Normal paragraph — handle inline bold/code/italic
        text = escape(line)
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
        text = re.sub(r"`(.+?)`", r'<font name="Courier" fontSize="8">\1</font>', text)
        flowables.append(Paragraph(text, styles["body"]))
        i += 1

    return flowables


def convert(md_path: str, pdf_path: str):
    md_text = Path(md_path).read_text(encoding="utf-8")
    styles = build_styles()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title="ClaudeOS QA Test Plan",
        author="ClaudeOS",
    )

    # Cover header
    cover_data = [[
        Paragraph("ClaudeOS", ParagraphStyle(
            "cv", fontName="Helvetica-Bold", fontSize=28,
            textColor=WHITE, alignment=TA_CENTER,
        )),
        Paragraph("QA Test Plan", ParagraphStyle(
            "cv2", fontName="Helvetica", fontSize=16,
            textColor=WHITE, alignment=TA_CENTER,
        )),
    ]]

    story = []

    # Build content
    story.extend(md_to_flowables(md_text, styles))

    # Page number footer
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(
            PAGE_W - MARGIN, 10 * mm,
            f"Page {doc.page}  |  ClaudeOS QA Test Plan"
        )
        canvas.setStrokeColor(GREEN)
        canvas.setLineWidth(1)
        canvas.line(MARGIN, 12 * mm, PAGE_W - MARGIN, 12 * mm)
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"PDF written: {pdf_path}")


if __name__ == "__main__":
    base = Path(__file__).parent.parent
    md = str(base / "QA_TEST_PLAN.md")
    pdf = str(base / "QA_TEST_PLAN.pdf")
    convert(md, pdf)
