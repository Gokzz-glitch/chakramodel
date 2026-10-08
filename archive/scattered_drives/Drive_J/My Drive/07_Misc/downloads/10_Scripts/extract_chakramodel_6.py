import json
import re
import datetime

file_path = r'C:\Users\imgk3\Downloads\chakramodel-testing (6).ipynb'
output_path = r'C:\Users\imgk3\Downloads\chakramodel-testing (6).ipynb_extracted.json'

with open(file_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

extracted_content = {
    'cells': []
}

key_metrics = []

for cell in nb.get('cells', []):
    cell_data = {
        'type': cell.get('cell_type'),
        'source': cell.get('source'),
        'outputs': cell.get('outputs', [])
    }
    extracted_content['cells'].append(cell_data)

    # find key metrics in outputs
    for out in cell.get('outputs', []):
        text_list = out.get('text', [])
        if isinstance(text_list, str):
            text = text_list
        else:
            text = ''.join(text_list)
        
        # Look for numbers like Dice, mIoU, Sensitivity, FPS
        metrics_found = re.findall(r'(Dice.*?:\s*[\d\.]+)|(mIoU.*?:\s*[\d\.]+)|(Sensitivity.*?:\s*[\d\.]+)|(FPS.*?:\s*[\d\.]+)', text)
        for m in metrics_found:
            for item in m:
                if item:
                    key_metrics.append(item.strip())
        
        json_matches = re.findall(r'\{\n\s*\"Dice.*?\}', text, re.DOTALL)
        for jm in json_matches:
            key_metrics.append(jm)

out_data = {
    'file_name': 'chakramodel-testing (6).ipynb',
    'file_path': file_path,
    'timestamp_processed': datetime.datetime.now().isoformat(),
    'file_type': 'ipynb',
    'extracted_content': extracted_content,
    'key_metrics_and_values': list(set(key_metrics))
}

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(out_data, f, indent=2)

print('Done Extraction')
