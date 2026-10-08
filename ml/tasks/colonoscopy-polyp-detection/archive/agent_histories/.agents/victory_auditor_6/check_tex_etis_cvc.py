import re

with open('paper/main.tex', 'r', encoding='utf-8', errors='ignore') as fp:
    lines = fp.readlines()

print("=== paper/main.tex ETIS / CVC LINES ===")
for idx, line in enumerate(lines, 1):
    if re.search(r'etis|larib', line, re.IGNORECASE):
        print(f"ETIS line {idx}: {line.strip()}")
    if re.search(r'cvc-clinic|clinicdb', line, re.IGNORECASE):
        print(f"CVC line {idx}: {line.strip()}")
