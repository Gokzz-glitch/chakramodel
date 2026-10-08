import json
import datetime
import os
import re

file_path = r"C:\Users\imgk3\Downloads\chakramodel-testing (3).ipynb"
output_path = file_path + "_extracted.json"

with open(file_path, "r", encoding="utf-8") as f:
    nb = json.load(f)

extracted_content = {
    "cells": []
}

key_metrics_and_values = []

for cell in nb.get("cells", []):
    cell_type = cell.get("cell_type", "")
    source = "".join(cell.get("source", []))
    outputs = cell.get("outputs", [])
    
    cell_data = {
        "cell_type": cell_type,
        "source": source,
    }
    
    if outputs:
        cell_data["outputs"] = []
        for out in outputs:
            text = "".join(out.get("text", [])) if "text" in out else ""
            if "data" in out and "text/plain" in out["data"]:
                text += "".join(out["data"]["text/plain"])
            if "traceback" in out:
                text += "\n".join(out["traceback"])
            
            if text:
                cell_data["outputs"].append(text)
                
                # extract some metrics
                matches = re.findall(r'([A-Za-z\s]+):\s*([\d\.]+)', text)
                for k, v in matches:
                    k_stripped = k.strip()
                    if len(k_stripped) > 2:
                        key_metrics_and_values.append({k_stripped: v})
                        
                matches_pct = re.findall(r'([\d\.]+)%', text)
                for v in matches_pct:
                    key_metrics_and_values.append({"percentage": v + "%"})
                    
                matches_mb = re.findall(r'([\d\.]+MB)', text)
                for v in matches_mb:
                    key_metrics_and_values.append({"size": v})

    extracted_content["cells"].append(cell_data)

final_data = {
    "file_name": os.path.basename(file_path),
    "file_path": file_path,
    "timestamp_processed": datetime.datetime.now().isoformat(),
    "file_type": "ipynb",
    "extracted_content": extracted_content,
    "key_metrics_and_values": key_metrics_and_values
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(final_data, f, indent=4)

print(f"Extraction successful: {output_path}")
