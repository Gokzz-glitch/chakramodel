import ast
import re

with open(r"m:\chakramodel\COLAB_EVALUATION_AUDIT_REPORT.md", "r", encoding="utf-8") as f:
    text = f.read()

# Find all python code blocks in the document
blocks = re.findall(r"```python(.*?)```", text, re.DOTALL)
print(f"Total python code blocks found: {len(blocks)}")

for i, code in enumerate(blocks, 1):
    # Strip jupyter shell commands (!, %, etc.) before ast.parse
    clean_lines = []
    for line in code.split("\n"):
        stripped = line.strip()
        if stripped.startswith("!") or stripped.startswith("%"):
            clean_lines.append("# " + line)
        else:
            clean_lines.append(line)
    clean_code = "\n".join(clean_lines)
    
    try:
        ast.parse(clean_code)
        print(f"Block {i} (lines {len(clean_lines)}): SYNTAX VALID")
    except SyntaxError as e:
        print(f"Block {i} (lines {len(clean_lines)}): SYNTAX ERROR: {e}")
