import sys
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

def create_pdf(output_filename):
    doc = SimpleDocTemplate(output_filename, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom style for code/logs
    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontSize=8,
        leading=10,
        fontName='Courier',
        wordWrap='CJK',
    )
    
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    
    Story = []
    
    # Title
    Story.append(Paragraph("ChakraModel Verification Proof", title_style))
    Story.append(Spacer(1, 0.2 * inch))
    Story.append(Paragraph("This document contains the verification script used to validate the CVC-ColonDB results, and the exact terminal output generated during the execution.", styles['Normal']))
    Story.append(Spacer(1, 0.5 * inch))
    
    # Script Section
    Story.append(Paragraph("1. Verification Script (verify_eval.py)", subtitle_style))
    Story.append(Spacer(1, 0.2 * inch))
    
    with open('src/verify_eval.py', 'r', encoding='utf-8') as f:
        script_content = f.read()
    
    Story.append(Preformatted(script_content, code_style))
    Story.append(PageBreak())
    
    # Log Section
    Story.append(Paragraph("2. Execution Log (Proof of Verification)", subtitle_style))
    Story.append(Spacer(1, 0.2 * inch))
    
    log_path = r"C:\Users\imgk3\.gemini\antigravity\brain\d9575053-e74f-4020-80d7-c46c85c16616\.system_generated\tasks\task-165.log"
    with open(log_path, 'r', encoding='utf-8') as f:
        log_content = f.read()
        
    Story.append(Preformatted(log_content, code_style))
    
    doc.build(Story)
    print(f"PDF successfully generated at {output_filename}")

if __name__ == "__main__":
    create_pdf("proof_evidence.pdf")
