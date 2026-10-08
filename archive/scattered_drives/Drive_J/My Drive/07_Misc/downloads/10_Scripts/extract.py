import zipfile
import xml.etree.ElementTree as ET
import json
import os
import datetime
import re

file_path = r"C:\Users\imgk3\Downloads\ChakraModel_16Slide_Pitch.pptx"
output_path = r"C:\Users\imgk3\Downloads\ChakraModel_16Slide_Pitch.pptx_extracted.json"

extracted_data = {
    "file_name": os.path.basename(file_path),
    "file_path": file_path,
    "timestamp_processed": datetime.datetime.now().isoformat(),
    "file_type": "pptx",
    "extracted_content": {
        "slides": []
    },
    "key_metrics_and_values": []
}

try:
    with zipfile.ZipFile(file_path, 'r') as z:
        # Find slide files
        slide_files = [f for f in z.namelist() if f.startswith('ppt/slides/slide') and f.endswith('.xml')]
        
        # Sort slides numerically
        slide_files.sort(key=lambda x: int(re.search(r'slide(\d+)\.xml', x).group(1)))

        all_text = ""

        for slide_file in slide_files:
            xml_content = z.read(slide_file)
            root = ET.fromstring(xml_content)
            
            texts = []
            for node in root.iter():
                if node.tag.endswith('}t'):
                    if node.text:
                        texts.append(node.text)
            
            slide_text = " ".join(texts)
            extracted_data["extracted_content"]["slides"].append({
                "slide_name": slide_file,
                "content": slide_text
            })
            all_text += slide_text + " "

        # Basic metric extraction (numbers with % or $)
        metrics = re.findall(r'\$?\d+(?:\.\d+)?(?:%|[MBKmbk])?', all_text)
        metrics = list(set([m for m in metrics if any(c.isdigit() for c in m)]))
        extracted_data["key_metrics_and_values"] = metrics

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(extracted_data, f, indent=4)
    print(f"Success: {output_path}")

except Exception as e:
    print(f"Error: {e}")
