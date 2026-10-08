import ast
import re
from pathlib import Path

report_path = Path(r"m:\chakramodel\COLAB_EVALUATION_AUDIT_REPORT.md")
content = report_path.read_text(encoding='utf-8')

# Let's extract code blocks in Section 8
code_blocks = re.findall(r'```python\n(.*?)```', content, re.DOTALL)
print(f"Total Python code blocks found in report: {len(code_blocks)}")

for i, block in enumerate(code_blocks):
    print(f"\n--- Checking Code Block {i+1} ---")
    first_few_lines = "\n".join(block.strip().split("\n")[:3])
    print(first_few_lines)
    # Check syntax (ignoring ipython magic lines like !pip or !python)
    clean_lines = []
    for line in block.split("\n"):
        stripped = line.strip()
        if stripped.startswith("!") or stripped.startswith("%"):
            clean_lines.append(f"# {line}")
        else:
            clean_lines.append(line)
    py_code = "\n".join(clean_lines)
    try:
        ast.parse(py_code)
        print(f"Block {i+1}: AST parse SUCCESSFUL")
    except SyntaxError as e:
        print(f"Block {i+1}: SYNTAX ERROR: {e}")
