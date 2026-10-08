import os
import json
from datetime import datetime
from fpdf import FPDF
import glob

class PDF(FPDF):
    def __init__(self, watermark_text):
        super().__init__()
        self.watermark_text = watermark_text

    def header(self):
        # Watermark
        self.set_font("Helvetica", "B", 40)
        self.set_text_color(220, 220, 220)
        # Position the watermark in the middle of the page, rotated
        with self.rotation(45, 105, 148):
            self.text(30, 150, self.watermark_text)
        
        # Reset font for normal text
        self.set_font("Helvetica", size=10)
        self.set_text_color(0, 0, 0)
        self.set_y(10)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

def main():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    watermark = f"CHAKRAMODEL PROOF - {timestamp}"
    
    pdf = PDF(watermark)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "ChakraModel Empirical Proof of Testing", ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Generated at: {timestamp}", ln=True, align="C")
    pdf.ln(10)
    
    directories_to_scan = [
        "m:/chakramodel/results",
        "m:/chakramodel/outputs/test_results",
        "m:/chakramodel/outputs/eval",
        "m:/chakramodel/outputs/judge_proof",
        "m:/chakramodel/outputs\clinical_reports",
        "m:/chakramodel/outputs/polyp_yolov8x",
        "m:/chakramodel/outputs/polyp_yolov8n",
        "m:/chakramodel/runs/detect",
        "m:/chakramodel/video_testing"
    ]
    
    for directory in directories_to_scan:
        if not os.path.exists(directory):
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, f"Directory: {directory} (NOT FOUND)", ln=True)
            pdf.ln(5)
            continue
            
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, f"Directory: {directory}", ln=True)
        pdf.ln(5)
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                filepath = os.path.join(root, file)
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(0, 8, f"File: {os.path.relpath(filepath, 'm:/chakramodel')}", ln=True)
                
                # Check file extension
                ext = os.path.splitext(file)[1].lower()
                if ext in ['.json', '.txt', '.md', '.csv']:
                    pdf.set_font("Courier", size=8)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Replace characters that might break FPDF latin-1
                            content = content.encode('latin-1', 'replace').decode('latin-1')
                            pdf.multi_cell(0, 4, content)
                    except Exception as e:
                        pdf.multi_cell(0, 4, f"<Error reading file: {e}>")
                else:
                    pdf.set_font("Helvetica", "I", 10)
                    pdf.cell(0, 8, f"  [Binary or non-text file ({ext}) - Included in registry but content not printed]", ln=True)
                pdf.ln(5)

    output_path = "m:/chakramodel/ChakraModel_Proof_of_Testing_Watermarked.pdf"
    pdf.output(output_path)
    print(f"Successfully generated {output_path}")

if __name__ == "__main__":
    main()
