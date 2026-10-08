import re

files = ['paper/main.tex', 'docs/paper/ChakraModel_Final_Paper.md']

print("=== CHECKING ETIS-LARIB AND CVC-CLINICDB OCCURRENCES ===")
for f in files:
    with open(f, 'r', encoding='utf-8', errors='ignore') as fp:
        lines = fp.readlines()
    print(f"\n--- {f} ---")
    for idx, line in enumerate(lines, 1):
        if re.search(r'etis|larib', line, re.IGNORECASE):
            print(f"ETIS line {idx}: {line.strip()}")
        if re.search(r'cvc-clinic|clinicdb', line, re.IGNORECASE):
            print(f"CVC line {idx}: {line.strip()}")
