import json
import re
import datetime
import os

input_file = r"C:\Users\imgk3\Downloads\combo-6-om (3).ipynb"
output_file = r"C:\Users\imgk3\Downloads\combo-6-om (3).ipynb_extracted.json"

with open(input_file, 'r', encoding='utf-8') as f:
    nb_data = json.load(f)

extracted_content = {
    "cells": []
}

key_metrics = set()

def extract_metrics(text):
    # simple regex to find numbers and percentages
    matches = re.findall(r'\b\d+(?:\.\d+)?%?\b', text)
    for m in matches:
        key_metrics.add(m)

for cell in nb_data.get("cells", []):
    cell_info = {
        "cell_type": cell.get("cell_type"),
        "source": "".join(cell.get("source", [])),
    }
    extract_metrics(cell_info["source"])
    
    if cell.get("cell_type") == "code":
        outputs = []
        for out in cell.get("outputs", []):
            out_text = ""
            if "text" in out:
                out_text = "".join(out["text"])
            elif "data" in out and "text/plain" in out["data"]:
                out_text = "".join(out["data"]["text/plain"])
            
            if out_text:
                outputs.append(out_text)
                extract_metrics(out_text)
        cell_info["outputs"] = outputs
        
    extracted_content["cells"].append(cell_info)

out_data = {
    "file_name": os.path.basename(input_file),
    "file_path": input_file,
    "timestamp_processed": datetime.datetime.now().isoformat(),
    "file_type": "ipynb",
    "extracted_content": extracted_content,
    "key_metrics_and_values": list(key_metrics)
}

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(out_data, f, indent=4)
    
print("Extraction complete.")
