import pathlib
import re

root = pathlib.Path('templates')
templates = ['general', 'cafe', 'transport', 'salon', 'retail', 'fitness', 'clinic']

print("=== CSS BRACE AND SYNTAX AUDIT ===")
for t in templates:
    css = (root / t / 'style.css').read_text(encoding='utf-8')
    # strip comments and strings
    clean = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    clean = re.sub(r'"(?:\\.|[^"\\])*"', '', clean)
    clean = re.sub(r"'(?:\\.|[^'\\])*'", '', clean)
    
    open_b = clean.count('{')
    close_b = clean.count('}')
    
    print(f"[{t.upper()}] Open braces: {open_b}, Close braces: {close_b}, Balanced: {open_b == close_b}")
