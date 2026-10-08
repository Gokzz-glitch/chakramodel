import json
import re
from datetime import datetime
import os

def extract_notebook_data(file_path):
    file_name = os.path.basename(file_path)
    output_path = f"{file_path}_extracted.json"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
        
    extracted_content = {
        "cells": []
    }
    
    key_metrics = []
    
    # Regex to find numbers/percentages
    metric_regex = re.compile(r'(\b\d+(?:\.\d+)?%?\b)')

    for cell in nb.get('cells', []):
        cell_type = cell.get('cell_type')
        source = "".join(cell.get('source', []))
        
        cell_data = {
            "type": cell_type,
            "source": source
        }
        
        # Find metrics in source
        found_metrics = metric_regex.findall(source)
        if found_metrics:
            key_metrics.extend(found_metrics)
            
        if cell_type == 'code':
            cell_data['execution_count'] = cell.get('execution_count')
            outputs = cell.get('outputs', [])
            extracted_outputs = []
            for out in outputs:
                if out.get('output_type') == 'stream':
                    text = "".join(out.get('text', []))
                    extracted_outputs.append({"type": "stream", "text": text})
                    key_metrics.extend(metric_regex.findall(text))
                elif out.get('output_type') in ('display_data', 'execute_result'):
                    data = out.get('data', {})
                    text_plain = "".join(data.get('text/plain', []))
                    extracted_outputs.append({"type": "data", "text": text_plain})
                    key_metrics.extend(metric_regex.findall(text_plain))
                elif out.get('output_type') == 'error':
                    extracted_outputs.append({
                        "type": "error",
                        "ename": out.get('ename'),
                        "evalue": out.get('evalue')
                    })
            cell_data['outputs'] = extracted_outputs
            
        extracted_content["cells"].append(cell_data)
        
    # Deduplicate metrics
    key_metrics = list(set(key_metrics))
    
    result = {
        "file_name": file_name,
        "file_path": file_path,
        "timestamp_processed": datetime.now().isoformat(),
        "file_type": "ipynb",
        "extracted_content": extracted_content,
        "key_metrics_and_values": key_metrics
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4)
        
    print(f"Extraction complete. Saved to {output_path}")

extract_notebook_data(r'C:\Users\imgk3\Downloads\combo-6-om (2).ipynb')
