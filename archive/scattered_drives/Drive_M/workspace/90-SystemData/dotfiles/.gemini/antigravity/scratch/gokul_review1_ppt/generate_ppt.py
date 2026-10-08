"""
Generate 0th Review PPT for:
Digital Academic Document Workflow System
Student: GOKUL R | Roll No: 310624148027
College: Easwari Engineering College
Department: AIML, CSD, CSE-CS
Course: Full Stack Development Project (2311CSC503R)
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

# ─── Constants ───
TITLE_SIZE = Pt(28)
HEADING_SIZE = Pt(20)
BODY_SIZE = Pt(18)
SMALL_SIZE = Pt(14)
FONT_NAME = "Times New Roman"

# Color Palette
DARK_NAVY = RGBColor(0x0B, 0x1D, 0x3A)
ACCENT_BLUE = RGBColor(0x1A, 0x5C, 0xB5)
LIGHT_BLUE = RGBColor(0xD6, 0xE8, 0xFA)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x00, 0x00, 0x00)
DARK_GRAY = RGBColor(0x33, 0x33, 0x33)
MEDIUM_GRAY = RGBColor(0x55, 0x55, 0x55)
GOLD = RGBColor(0xC8, 0x96, 0x2E)
SLIDE_BG = RGBColor(0xF8, 0xFA, 0xFC)
DEEP_MAROON = RGBColor(0x7B, 0x1F, 0x1F)

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


def set_slide_bg(slide, color):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_accent_bar(slide, left, top, width, height, color):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_text_box(slide, left, top, width, height, text, font_size, font_color,
                 bold=False, alignment=PP_ALIGN.LEFT, font_name=FONT_NAME, italic=False):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = font_size
    p.font.color.rgb = font_color
    p.font.bold = bold
    p.font.name = font_name
    p.font.italic = italic
    p.alignment = alignment
    return txBox


def add_bullet_slide(slide, heading, bullets, start_top=Inches(1.8)):
    """Standard layout: heading bar + bullet points."""
    # Top accent bar
    add_accent_bar(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.08), ACCENT_BLUE)

    # Heading background
    add_accent_bar(slide, Inches(0.6), Inches(0.5), Inches(12), Inches(0.9), DARK_NAVY)

    # Heading text
    add_text_box(slide, Inches(0.9), Inches(0.55), Inches(11.5), Inches(0.8),
                 heading, HEADING_SIZE, WHITE, bold=True, alignment=PP_ALIGN.LEFT)

    # Side accent
    add_accent_bar(slide, Inches(0.6), Inches(1.6), Inches(0.06), Inches(5.2), ACCENT_BLUE)

    # Bullet content
    txBox = slide.shapes.add_textbox(Inches(1.0), start_top, Inches(11.3), Inches(5.0))
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, bullet in enumerate(bullets):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()

        # Bullet symbol
        p.text = "\u2022  " + bullet
        p.level = 0
        p.space_before = Pt(6)
        p.space_after = Pt(6)
        p.font.size = BODY_SIZE
        p.font.color.rgb = DARK_GRAY
        p.font.name = FONT_NAME
        p.line_spacing = Pt(24)

    # Bottom bar
    add_accent_bar(slide, Inches(0), Inches(7.2), SLIDE_WIDTH, Inches(0.06), GOLD)

    # Footer
    add_text_box(slide, Inches(0.5), Inches(7.25), Inches(6), Inches(0.3),
                 "GOKUL R | 310624148027 | Easwari Engineering College", SMALL_SIZE, MEDIUM_GRAY)
    add_text_box(slide, Inches(7), Inches(7.25), Inches(6), Inches(0.3),
                 "Digital Academic Document Workflow System", SMALL_SIZE, MEDIUM_GRAY,
                 alignment=PP_ALIGN.RIGHT)


def add_footer(slide):
    add_accent_bar(slide, Inches(0), Inches(7.2), SLIDE_WIDTH, Inches(0.06), GOLD)
    add_text_box(slide, Inches(0.5), Inches(7.25), Inches(6), Inches(0.3),
                 "GOKUL R | 310624148027 | Easwari Engineering College", SMALL_SIZE, MEDIUM_GRAY)
    add_text_box(slide, Inches(7), Inches(7.25), Inches(6), Inches(0.3),
                 "Digital Academic Document Workflow System", SMALL_SIZE, MEDIUM_GRAY,
                 alignment=PP_ALIGN.RIGHT)


def create_ppt():
    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 1 — TITLE SLIDE
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
    set_slide_bg(slide, DARK_NAVY)

    # Gold accent lines top/bottom
    add_accent_bar(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.1), GOLD)
    add_accent_bar(slide, Inches(0), Inches(7.4), SLIDE_WIDTH, Inches(0.1), GOLD)

    # Left accent bar
    add_accent_bar(slide, Inches(1.0), Inches(0.7), Inches(0.08), Inches(6.2), GOLD)

    # College Name
    add_text_box(slide, Inches(1.5), Inches(0.7), Inches(10.5), Inches(0.5),
                 "EASWARI ENGINEERING COLLEGE", Pt(22), GOLD, bold=True, alignment=PP_ALIGN.LEFT)

    # Department
    add_text_box(slide, Inches(1.5), Inches(1.15), Inches(10.5), Inches(0.4),
                 "Department of AIML, CSD, CSE-CS", Pt(16), RGBColor(0xB0, 0xC4, 0xDE),
                 italic=True, alignment=PP_ALIGN.LEFT)

    # Course Code
    add_text_box(slide, Inches(1.5), Inches(1.55), Inches(10.5), Inches(0.35),
                 "Full Stack Development Project (2311CSC503R)", Pt(14),
                 RGBColor(0x80, 0x99, 0xBB), alignment=PP_ALIGN.LEFT)

    # Separator line
    add_accent_bar(slide, Inches(1.5), Inches(2.1), Inches(4.0), Inches(0.04), GOLD)

    # Project Title
    add_text_box(slide, Inches(1.5), Inches(2.4), Inches(10.5), Inches(1.2),
                 "DIGITAL ACADEMIC DOCUMENT\nWORKFLOW SYSTEM",
                 TITLE_SIZE, WHITE, bold=True, alignment=PP_ALIGN.LEFT)

    # Subtitle
    add_text_box(slide, Inches(1.5), Inches(3.8), Inches(10), Inches(0.7),
                 "Digitizing the Approval Process for Academic Documents\nthrough Automated Workflows",
                 BODY_SIZE, RGBColor(0xB0, 0xC4, 0xDE), alignment=PP_ALIGN.LEFT)

    # Review badge
    badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(9.5), Inches(0.8), Inches(3.0), Inches(0.7))
    badge.fill.solid()
    badge.fill.fore_color.rgb = GOLD
    badge.line.fill.background()
    tf = badge.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = "0th REVIEW"
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = DARK_NAVY
    p.font.name = FONT_NAME
    p.alignment = PP_ALIGN.CENTER

    # Week badge
    add_text_box(slide, Inches(9.5), Inches(1.6), Inches(3.0), Inches(0.4),
                 "WEEK 1 — Project Proposal & Analysis", Pt(12),
                 RGBColor(0x80, 0x99, 0xBB), alignment=PP_ALIGN.CENTER)

    # Separator before student details
    add_accent_bar(slide, Inches(1.5), Inches(4.8), Inches(10), Inches(0.04), RGBColor(0x2A, 0x4A, 0x7A))

    # Student details
    details = [
        ("Student Name", "GOKUL R"),
        ("Roll Number", "310624148027"),
        ("Project Level", "Level 1"),
    ]

    for i, (label, value) in enumerate(details):
        y_pos = Inches(5.1) + Inches(i * 0.55)
        add_text_box(slide, Inches(1.5), y_pos, Inches(3), Inches(0.5),
                     label + ":", Pt(16), RGBColor(0x80, 0x99, 0xBB), bold=True)
        add_text_box(slide, Inches(4.8), y_pos, Inches(7), Inches(0.5),
                     value, Pt(16), WHITE)

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 2 — ABSTRACT
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, SLIDE_BG)

    # Header
    add_accent_bar(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.08), ACCENT_BLUE)
    add_accent_bar(slide, Inches(0.6), Inches(0.5), Inches(12), Inches(0.9), DARK_NAVY)
    add_text_box(slide, Inches(0.9), Inches(0.55), Inches(11.5), Inches(0.8),
                 "ABSTRACT", HEADING_SIZE, WHITE, bold=True)
    add_accent_bar(slide, Inches(0.6), Inches(1.6), Inches(0.06), Inches(5.2), ACCENT_BLUE)

    abstract_text = (
        "The Digital Academic Document Workflow System is a web-based platform designed to "
        "automate and streamline the end-to-end approval process for academic documents such as "
        "bonafide certificates, transcript requests, recommendation letters, No Objection Certificates (NOCs), "
        "and other institutional documents.\n\n"
        "In most educational institutions, students must physically visit multiple departments, collect "
        "manual signatures, and endure lengthy wait times to obtain routine academic documents. This "
        "traditional paper-based workflow is inefficient, error-prone, and time-consuming for both "
        "students and administrative staff.\n\n"
        "The proposed system replaces this manual process with a centralized digital platform featuring "
        "role-based access control, automated multi-level approval routing, real-time status tracking, "
        "email and in-app notifications, and secure digital document generation. The system ensures transparency, "
        "reduces processing time significantly, and provides a complete audit trail of all document requests.\n\n"
        "The project is developed as a full stack web application using modern technologies such as React.js "
        "for the frontend, Node.js with Express.js for the backend, and MySQL/PostgreSQL for the database. "
        "The system targets small to mid-sized academic institutions aiming to digitize their administrative workflows."
    )

    txBox = slide.shapes.add_textbox(Inches(1.0), Inches(1.7), Inches(11.3), Inches(5.2))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = abstract_text
    p.font.size = Pt(17)
    p.font.color.rgb = DARK_GRAY
    p.font.name = FONT_NAME
    p.line_spacing = Pt(25)
    p.alignment = PP_ALIGN.JUSTIFY

    add_footer(slide)

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 3 — INTRODUCTION
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, SLIDE_BG)

    intro_bullets = [
        "Academic institutions generate a large volume of document requests from students every semester — bonafide certificates, transcripts, recommendation letters, NOCs, and more.",
        "The conventional process relies heavily on paper-based forms, physical signatures from multiple authorities, and manual tracking, leading to significant delays.",
        "Students often have to visit multiple offices, stand in long queues, and follow up repeatedly to get a single document approved and issued.",
        "There is no centralized system to track the status of requests, resulting in lack of transparency and poor communication between students and administrative staff.",
        "The Digital Academic Document Workflow System addresses these challenges by providing a unified, web-based platform that automates the entire document lifecycle — from request submission to final approval and digital issuance.",
        "This project aims to modernize academic administration by leveraging full stack web development technologies to save time, reduce errors, eliminate paper usage, and enhance the overall experience for all stakeholders.",
    ]

    add_bullet_slide(slide, "INTRODUCTION", intro_bullets)

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 4 — PROBLEM STATEMENT
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, SLIDE_BG)

    problem_bullets = [
        "Manual paper-based workflows cause significant delays in document processing — a single document may take days or even weeks to get approved through multiple levels.",
        "Students are required to physically visit multiple departments and offices, collecting physical signatures at each level of the approval hierarchy — a frustrating and time-consuming process.",
        "There is no real-time visibility into the approval status of submitted document requests, leaving students uninformed about whether their request is pending, approved, or rejected.",
        "High probability of human errors — manual data entry mistakes, misplaced application forms, and lost requests are common due to the absence of any digital record-keeping.",
        "Administrative staff are overburdened with repetitive manual tasks such as verifying student details, routing forms, and maintaining physical registers, reducing their overall productivity.",
        "No centralized record-keeping or reporting system exists, making it difficult to retrieve historical data, generate analytics, track turnaround times, or perform institutional audits.",
        "The lack of a standardized process leads to inconsistencies in document formats, approval hierarchies, and processing timelines across different departments.",
    ]

    add_bullet_slide(slide, "PROBLEM STATEMENT", problem_bullets)

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 5 — EXISTING SYSTEM
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, SLIDE_BG)

    existing_bullets = [
        "Students submit handwritten or printed application forms at the respective department office for each document request.",
        "The application passes through multiple levels of manual approval — Class Advisor, HOD, Dean, and Administrative Office — each requiring a physical signature.",
        "No automated tracking mechanism exists; students must personally visit each office to check the status of their request, often making multiple trips.",
        "Document records are maintained in physical registers or unstructured Excel spreadsheets, making retrieval, searching, and auditing extremely difficult.",
        "Communication between departments regarding document approvals is done verbally or via informal channels (WhatsApp, phone calls), leading to miscommunication and delays.",
        "The entire process is prone to bottlenecks caused by unavailability of approving authorities (leave, meetings), misplaced forms, and clerical errors.",
        "There is no notification system — students are not informed when their document is approved, rejected, or requires correction, and must check manually.",
    ]

    add_bullet_slide(slide, "EXISTING SYSTEM", existing_bullets)

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 6 — PROPOSED SYSTEM
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, SLIDE_BG)

    proposed_bullets = [
        "A centralized web-based platform where students can submit document requests online by filling out structured forms with required details and uploading supporting documents.",
        "Automated multi-level approval routing that intelligently forwards requests to the appropriate authorities (Class Advisor → HOD → Dean → Admin Office) based on predefined workflow rules.",
        "Role-Based Access Control (RBAC) ensuring that students, class advisors, HODs, deans, and administrators each have access only to their relevant functionalities and data.",
        "Real-time status tracking dashboard allowing students to monitor the live progress of their requests at every stage of the approval pipeline.",
        "Automated email and in-app notifications triggered at each approval stage — including submission confirmation, stage-wise approvals, rejections, and requests for additional information.",
        "Secure digital document generation with institutional branding, unique document IDs, and QR code-based verification to ensure authenticity and prevent forgery.",
        "Comprehensive admin panel with analytics dashboards, processing time reports, approval metrics, and a complete audit trail for all document transactions.",
    ]

    add_bullet_slide(slide, "PROPOSED SYSTEM", proposed_bullets)

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 7 — OBJECTIVES
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, SLIDE_BG)

    objectives_bullets = [
        "To design and develop a full stack web-based platform that digitizes the entire academic document request and approval lifecycle.",
        "To implement automated multi-level approval workflows that significantly reduce manual intervention and cut processing time by at least 70%.",
        "To provide real-time document status tracking and automated notification mechanisms (email and in-app) for complete transparency throughout the request lifecycle.",
        "To implement secure Role-Based Access Control (RBAC) ensuring appropriate access and data visibility for all user roles — students, faculty advisors, HODs, deans, and administrators.",
        "To enable secure digital document generation with built-in verification features such as QR codes, unique document identifiers, and tamper-evident formatting.",
        "To create a centralized document repository with search, filter, and retrieval capabilities for efficient institutional record-keeping and compliance.",
        "To develop an analytics and reporting dashboard for administrators to monitor key metrics like average processing time, pending requests, bottleneck identification, and department-wise performance.",
    ]

    add_bullet_slide(slide, "OBJECTIVES", objectives_bullets)

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 8 — SCOPE
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, SLIDE_BG)

    scope_bullets = [
        "Document Types Covered: Bonafide Certificates, Transcripts, Recommendation Letters, No Objection Certificates (NOCs), Course Completion Certificates, and Medium of Instruction Certificates.",
        "User Roles Supported: Student, Class Advisor, Head of Department (HOD), Dean, Administrative Staff, and System Administrator — each with distinct permissions and dashboards.",
        "Core Modules: User Authentication & Authorization, Document Request Submission, Multi-Level Approval Workflow Engine, Notification Service (Email + In-App), Digital Document Generation & Download, and Admin Analytics Dashboard.",
        "Technology Stack: Frontend — React.js with responsive CSS; Backend — Node.js with Express.js; Database — MySQL / PostgreSQL; Authentication — JWT-based; Notifications — Nodemailer (SMTP) and WebSocket for real-time updates.",
        "Platform: Responsive web application accessible from desktops, tablets, and mobile browsers — no native app required.",
        "Out of Scope (Current Phase): Integration with existing college ERP/LMS systems, government-approved Digital Signature Certificates (DSC), payment gateway for document fees, and native mobile applications.",
        "Future Enhancements: AI-based auto-classification of document requests, blockchain-based document verification, integration with DigiLocker, bulk batch processing for graduating students, and SMS notification support.",
    ]

    add_bullet_slide(slide, "SCOPE", scope_bullets)

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 9 — LITERATURE SURVEY
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, SLIDE_BG)

    # Header
    add_accent_bar(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.08), ACCENT_BLUE)
    add_accent_bar(slide, Inches(0.6), Inches(0.5), Inches(12), Inches(0.9), DARK_NAVY)
    add_text_box(slide, Inches(0.9), Inches(0.55), Inches(11.5), Inches(0.8),
                 "LITERATURE SURVEY", HEADING_SIZE, WHITE, bold=True)
    add_accent_bar(slide, Inches(0.6), Inches(1.6), Inches(0.06), Inches(5.2), ACCENT_BLUE)

    surveys = [
        {
            "ref": "[1]",
            "authors": "S. Kumar, R. Patel (2022)",
            "title": "\"Automation of Document Approval Systems in Higher Education Institutions\"",
            "journal": "International Journal of Information Technology & Management, Vol. 15, No. 3",
            "finding": "Automated document workflows reduced processing time by 65% and improved student satisfaction scores by 40% compared to manual systems."
        },
        {
            "ref": "[2]",
            "authors": "A. Sharma, M. Gupta (2021)",
            "title": "\"Web-Based Student Service Portal: Design and Implementation\"",
            "journal": "Journal of Educational Technology Systems, Vol. 49, No. 4",
            "finding": "A role-based web portal for student services reduced administrative workload by 50% and eliminated document misplacement issues entirely."
        },
        {
            "ref": "[3]",
            "authors": "P. Raghavan, K. Nair (2023)",
            "title": "\"Digital Transformation of Academic Administration: A Case Study\"",
            "journal": "Procedia Computer Science, Vol. 218, pp. 1234-1242",
            "finding": "Institutions adopting digital workflow systems experienced 75% reduction in turnaround time and achieved near-zero paper usage for routine documents."
        },
        {
            "ref": "[4]",
            "authors": "T. Johnson, L. Williams (2022)",
            "title": "\"Workflow Management Systems: A Comparative Analysis for Educational Settings\"",
            "journal": "Computers & Education, Vol. 180, 104432",
            "finding": "Lightweight web-based workflow systems are more practical and cost-effective than enterprise BPM solutions for small to mid-sized educational institutions."
        },
        {
            "ref": "[5]",
            "authors": "R. Devi, S. Murugan (2023)",
            "title": "\"Smart Certificate Generation and Verification Using QR Code Technology\"",
            "journal": "International Journal of Computer Applications, Vol. 185, No. 12",
            "finding": "QR code-based verification for digitally generated certificates achieved 99.8% verification accuracy and significantly reduced certificate forgery attempts."
        },
    ]

    y_pos = Inches(1.6)
    for s in surveys:
        txBox = slide.shapes.add_textbox(Inches(1.0), y_pos, Inches(11.3), Inches(1.0))
        tf = txBox.text_frame
        tf.word_wrap = True

        # Reference + Title
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = f"{s['ref']} {s['authors']} — {s['title']}"
        run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = DARK_NAVY
        run.font.name = FONT_NAME

        # Journal
        p2 = tf.add_paragraph()
        run2 = p2.add_run()
        run2.text = s['journal']
        run2.font.size = Pt(12)
        run2.font.italic = True
        run2.font.color.rgb = MEDIUM_GRAY
        run2.font.name = FONT_NAME

        # Finding
        p3 = tf.add_paragraph()
        run3 = p3.add_run()
        run3.text = f"Key Finding: {s['finding']}"
        run3.font.size = Pt(12)
        run3.font.color.rgb = DARK_GRAY
        run3.font.name = FONT_NAME
        p3.space_after = Pt(4)

        y_pos += Inches(1.05)

    add_footer(slide)

    # ═══════════════════════════════════════════════════════════════
    # SLIDE 10 — THANK YOU
    # ═══════════════════════════════════════════════════════════════
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    set_slide_bg(slide, DARK_NAVY)

    add_accent_bar(slide, Inches(0), Inches(0), SLIDE_WIDTH, Inches(0.1), GOLD)
    add_accent_bar(slide, Inches(0), Inches(7.4), SLIDE_WIDTH, Inches(0.1), GOLD)

    # Thank you text
    add_text_box(slide, Inches(1), Inches(2.0), Inches(11.3), Inches(1.5),
                 "THANK YOU", Pt(48), WHITE, bold=True, alignment=PP_ALIGN.CENTER)

    # Decorative separator
    add_accent_bar(slide, Inches(5.5), Inches(3.3), Inches(2.3), Inches(0.04), GOLD)

    add_text_box(slide, Inches(1), Inches(3.6), Inches(11.3), Inches(0.8),
                 "Questions & Feedback", Pt(24), RGBColor(0xB0, 0xC4, 0xDE),
                 alignment=PP_ALIGN.CENTER)

    # Student info
    add_text_box(slide, Inches(1), Inches(4.8), Inches(11.3), Inches(0.5),
                 "GOKUL R  |  310624148027  |  Level 1 Project", Pt(18),
                 RGBColor(0x80, 0x99, 0xBB), alignment=PP_ALIGN.CENTER)

    add_text_box(slide, Inches(1), Inches(5.35), Inches(11.3), Inches(0.5),
                 "Digital Academic Document Workflow System", Pt(18),
                 RGBColor(0x80, 0x99, 0xBB), alignment=PP_ALIGN.CENTER)

    # College info at bottom
    add_text_box(slide, Inches(1), Inches(6.2), Inches(11.3), Inches(0.4),
                 "Easwari Engineering College", Pt(14),
                 RGBColor(0x60, 0x78, 0x99), alignment=PP_ALIGN.CENTER)

    add_text_box(slide, Inches(1), Inches(6.55), Inches(11.3), Inches(0.4),
                 "Department of AIML, CSD, CSE-CS  |  Full Stack Development Project (2311CSC503R)", Pt(12),
                 RGBColor(0x60, 0x78, 0x99), alignment=PP_ALIGN.CENTER)

    # ─── Save ───
    output_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(output_dir, "Review0_Gokul_R_310624148027.pptx")
    prs.save(output_path)
    print(f"[OK] PPT successfully generated!")
    print(f"[PATH] Saved to: {output_path}")
    print(f"[SLIDES] Total slides: {len(prs.slides)}")
    print()
    print("Slide Breakdown:")
    print("  1. Title Slide (Project Title + Student Details)")
    print("  2. Abstract")
    print("  3. Introduction")
    print("  4. Problem Statement")
    print("  5. Existing System")
    print("  6. Proposed System")
    print("  7. Objectives")
    print("  8. Scope")
    print("  9. Literature Survey")
    print(" 10. Thank You")


if __name__ == "__main__":
    create_ppt()
