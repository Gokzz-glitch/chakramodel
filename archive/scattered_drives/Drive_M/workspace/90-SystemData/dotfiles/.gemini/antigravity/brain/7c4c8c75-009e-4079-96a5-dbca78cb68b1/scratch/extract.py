import json
import os
import datetime
import re

file_path = r"C:\Users\imgk3\Downloads\chakratransformer_COMBO 6 ISSUES.pdf"
output_path = r"C:\Users\imgk3\Downloads\chakratransformer_COMBO 6 ISSUES.pdf_extracted.json"

text = ""
try:
    import pypdf
    reader = pypdf.PdfReader(file_path)
    for page in reader.pages:
        text += page.extract_text() + "\n"
except Exception as e:
    try:
        import fitz
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text() + "\n"
    except Exception as e2:
        text = "Failed to extract text. Errors: " + str(e) + " | " + str(e2)

numbers = re.findall(r'\b\d+(?:\.\d+)?%?\b', text)
metrics = list(set(numbers))

data = {
    "file_name": os.path.basename(file_path),
    "file_path": file_path,
    "timestamp_processed": datetime.datetime.now().isoformat(),
    "file_type": "pdf",
    "extracted_content": {
        "text": text
    },
    "key_metrics_and_values": metrics[:100]
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4)
print("SUCCESS: " + output_path)
