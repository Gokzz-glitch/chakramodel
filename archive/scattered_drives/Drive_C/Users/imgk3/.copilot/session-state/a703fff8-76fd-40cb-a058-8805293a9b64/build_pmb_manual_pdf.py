from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)
from xml.sax.saxutils import escape


BASE = Path(__file__).parent
SOURCE = BASE / "PMB_USER_MANUAL.md"
OUTPUT = BASE / "PMB_User_Manual.pdf"


def inline_markup(text: str) -> str:
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    return text


def build_story():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ManualTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17365D"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ManualSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#555555"),
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1Manual",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#17365D"),
            spaceBefore=13,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2Manual",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#1F4E79"),
            spaceBefore=9,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyManual",
            parent=styles["BodyText"],
            fontSize=9.4,
            leading=13.5,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletManual",
            parent=styles["BodyText"],
            fontSize=9.4,
            leading=13.5,
            leftIndent=13,
            firstLineIndent=-8,
            bulletIndent=3,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeManual",
            fontName="Courier",
            fontSize=7.7,
            leading=10,
            leftIndent=8,
            rightIndent=8,
            borderColor=colors.HexColor("#D9E2F3"),
            borderWidth=0.5,
            borderPadding=6,
            backColor=colors.HexColor("#F4F7FB"),
            spaceBefore=3,
            spaceAfter=8,
        )
    )

    story = []
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    in_code = False
    code_lines = []
    paragraph_lines = []

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(x.strip() for x in paragraph_lines)
            story.append(Paragraph(inline_markup(text), styles["BodyManual"]))
            paragraph_lines = []

    def flush_code():
        nonlocal code_lines
        if code_lines:
            story.append(Preformatted("\n".join(code_lines), styles["CodeManual"]))
            code_lines = []

    for line in lines:
        if line.strip() == "```":
            flush_paragraph()
            if in_code:
                flush_code()
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            story.append(Spacer(1, 2))
            continue
        if line.startswith("# "):
            flush_paragraph()
            story.append(Paragraph(inline_markup(line[2:]), styles["ManualTitle"]))
            story.append(
                Paragraph(
                    "Windows-focused guide to local AI memory, shared clients, project analysis, and safe prompt workflows.",
                    styles["ManualSubtitle"],
                )
            )
        elif line.startswith("## "):
            flush_paragraph()
            story.append(Paragraph(inline_markup(line[3:]), styles["H1Manual"]))
        elif line.startswith("### "):
            flush_paragraph()
            story.append(Paragraph(inline_markup(line[4:]), styles["H2Manual"]))
        elif line.startswith("- "):
            flush_paragraph()
            story.append(
                Paragraph(
                    inline_markup(line[2:]),
                    styles["BulletManual"],
                    bulletText="•",
                )
            )
        elif re.match(r"^\d+\.\s+", line):
            flush_paragraph()
            number, text = line.split(".", 1)
            story.append(
                Paragraph(
                    inline_markup(text.strip()),
                    styles["BulletManual"],
                    bulletText=f"{number}.",
                )
            )
        else:
            paragraph_lines.append(line)

    flush_paragraph()
    flush_code()
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawString(18 * mm, 10 * mm, "PMB AI Local Memory User Manual")
    canvas.drawRightString(192 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


doc = SimpleDocTemplate(
    str(OUTPUT),
    pagesize=A4,
    rightMargin=17 * mm,
    leftMargin=17 * mm,
    topMargin=16 * mm,
    bottomMargin=16 * mm,
    title="PMB AI Local Memory User Manual",
    author="GitHub Copilot",
)
doc.build(build_story(), onFirstPage=footer, onLaterPages=footer)
print(OUTPUT)
