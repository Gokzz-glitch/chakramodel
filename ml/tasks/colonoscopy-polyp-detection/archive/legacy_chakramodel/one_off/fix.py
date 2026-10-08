import re
code = open(r'm:\chakramodel\build_crossval_v5.py', encoding='utf-8').read()
code = code.replace('new_code_cell(f\"\"\"\\', 'new_code_cell(\"\"\"\\')
code = code.replace('new_markdown_cell(f\"\"\"\\', 'new_markdown_cell(\"\"\"\\')
code = code.replace('{{', '{').replace('}}', '}')
open(r'm:\chakramodel\build_crossval_v5.py', 'w', encoding='utf-8').write(code)
print('Fixed f-strings')
