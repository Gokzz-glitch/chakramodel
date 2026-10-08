import json
import sys
import os

with open('notebooks/combos/Combo1_ChakraNet_Focal.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = ''.join(cell['source'])
        if 'class PraNetResNet101' in source or 'class PraNet' in source:
            g = {'DEVICE': 'cpu', '__name__': '__main__'}
            # Avoid printing unicode that fails in cp1252
            source_clean = source.replace('✅', '[OK]').replace('❌', '[FAIL]')
            exec(source_clean, g)
            for k, v in g.items():
                if isinstance(v, type) and issubclass(v, g['nn'].Module) and 'PraNet' in k:
                    model = v()
                    p_count = sum(p.numel() for p in model.parameters())
                    print(f'{k} parameter count: {p_count:,}')
                    for mname, mchild in model.named_children():
                        mparams = sum(p.numel() for p in mchild.parameters())
                        print(f'  {mname}: {mparams:,} params')
