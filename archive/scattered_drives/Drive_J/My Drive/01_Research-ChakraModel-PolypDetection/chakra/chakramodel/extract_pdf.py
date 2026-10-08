import fitz
import json
import re
from datetime import datetime

pdf_path = r"C:\Users\imgk3\Downloads\chakranet_merged.pdf"
out_path = r"C:\Users\imgk3\Downloads\chakranet_merged.pdf_extracted.json"

doc = fitz.open(pdf_path)

extracted_content = {
    "pages": []
}

full_text = ""
for i, page in enumerate(doc):
    text = page.get_text()
    extracted_content["pages"].append({
        "page_number": i + 1,
        "text": text
    })
    full_text += text + "\n"

# extract key metrics
percs = re.findall(r'\d+(?:\.\d+)?%', full_text)
metrics = re.findall(r'(?:DSC|mIoU|Accuracy|Sensitivity|Specificity|Precision|Recall|Parameters|FPS)[:\s=]*[\d\.]+', full_text, re.IGNORECASE)
parameters = re.findall(r'\b\d+(?:\.\d+)?[MB]\b', full_text)

key_metrics = list(set(percs + metrics + parameters))

data = {
    "file_name": "chakranet_merged.pdf",
    "file_path": pdf_path,
    "timestamp_processed": "2026-09-04T14:58:48+05:30",
    "file_type": "pdf",
    "extracted_content": extracted_content,
    "key_metrics_and_values": key_metrics
}

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

print("Successfully extracted to", out_path)
