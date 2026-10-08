import json

nb_path = 'm:/chakramodelpro/all-in-one-comapriosn-18-9-7am(error found).ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))[:100].replace('\n', ' ')
    print(f"=== Cell {i} ({cell.get('cell_type')}) ===")
    print(f"Source: {src}")
    for o in cell.get('outputs', []):
        ot = o.get('output_type')
        if ot == 'error':
            print(f"  [ERROR] {o.get('ename')}: {o.get('evalue')}")
            for tb in o.get('traceback', [])[-3:]:
                print(f"    {tb}")
        elif ot == 'stream':
            txt = ''.join(o.get('text', []))
            for l in txt.strip().split('\n')[:5]:
                print(f"  [STREAM] {l}")
        elif ot in ('execute_result', 'display_data'):
            data = o.get('data', {})
            if 'text/plain' in data:
                print(f"  [DATA] {data['text/plain'][:100]}")
