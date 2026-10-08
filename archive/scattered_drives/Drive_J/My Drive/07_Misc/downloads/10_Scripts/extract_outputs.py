import json, re

path = r'J:\My Drive\downloads\recentrrun 02-39pm 9-9-26'
nb = json.load(open(path, 'r', encoding='utf-8'))
cells = nb['cells']
print(f'Total cells: {len(cells)}')

out = []
for i, c in enumerate(cells):
    ct = c.get('cell_type', '')
    src = ''.join(c.get('source', []))
    outputs = c.get('outputs', [])

    if ct == 'code' and outputs:
        out.append(f'=== CELL {i} OUTPUT ===')
        for o in outputs:
            otype = o.get('output_type', '')
            if otype == 'stream':
                out.append(''.join(o.get('text', [])))
            elif otype in ('execute_result', 'display_data'):
                data = o.get('data', {})
                if 'text/plain' in data:
                    out.append(''.join(data['text/plain']))
            elif otype == 'error':
                ename = o.get('ename', '')
                evalue = o.get('evalue', '')
                out.append(f'ERROR: {ename}: {evalue}')
                # strip ANSI from traceback
                tb = ''.join(o.get('traceback', []))
                tb_clean = re.sub(r'\x1b\[[0-9;]*m', '', tb)
                out.append(tb_clean)
    elif ct == 'code' and src.strip():
        out.append(f'=== CELL {i} (no output) ===')

open(r'J:\My Drive\downloads\run_outputs.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('done - saved to run_outputs.txt')
