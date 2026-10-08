import json
import datetime
import os
import re

file_path = r"C:\Users\imgk3\Downloads\combo-6-om.ipynb"
output_path = r"C:\Users\imgk3\Downloads\combo-6-om.ipynb_extracted.json"

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)
        
    extracted = {
        "file_name": "combo-6-om.ipynb",
        "file_path": file_path,
        "timestamp_processed": datetime.datetime.now().isoformat(),
        "file_type": "ipynb",
        "extracted_content": {
            "cells": []
        },
        "key_metrics_and_values": []
    }
    
    number_pattern = re.compile(r'\b\d+(?:\.\d+)?%?\b')
    
    for cell in notebook.get("cells", []):
        cell_data = {
            "cell_type": cell.get("cell_type"),
            "source": "".join(cell.get("source", [])),
            "outputs": []
        }
        
        # Extract numbers from source
        metrics = number_pattern.findall(cell_data["source"])
        if metrics:
            extracted["key_metrics_and_values"].extend(metrics)
            
        if cell.get("cell_type") == "code":
            for output in cell.get("outputs", []):
                out_data = {"output_type": output.get("output_type")}
                if "text" in output:
                    out_text = "".join(output["text"])
                    out_data["text"] = out_text
                    metrics = number_pattern.findall(out_text)
                    if metrics:
                        extracted["key_metrics_and_values"].extend(metrics)
                if "data" in output and "text/plain" in output["data"]:
                    out_text = "".join(output["data"]["text/plain"])
                    out_data["data"] = out_text
                    metrics = number_pattern.findall(out_text)
                    if metrics:
                        extracted["key_metrics_and_values"].extend(metrics)
                cell_data["outputs"].append(out_data)
                
        extracted["extracted_content"]["cells"].append(cell_data)
        
    # Deduplicate metrics
    extracted["key_metrics_and_values"] = list(set(extracted["key_metrics_and_values"]))
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(extracted, f, indent=2)
        
    print(f"SUCCESS: {output_path}")

except Exception as e:
    print(f"FAILED: {e}")
