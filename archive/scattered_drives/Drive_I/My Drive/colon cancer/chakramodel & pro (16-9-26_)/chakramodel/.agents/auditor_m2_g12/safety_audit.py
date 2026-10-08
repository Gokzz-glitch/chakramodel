import ast
from pathlib import Path

adv_dir = Path("tests/adversarial")
suspicious_imports = {"requests", "urllib", "http", "socket", "urllib3", "aiohttp", "httpx", "ftplib"}
network_calls = {"get", "post", "download", "urlopen", "connect", "send", "recv"}
write_calls = {"write", "write_text", "write_bytes", "unlink", "remove", "rmdir", "rmtree"}

print("AUDITING ALL FILES IN tests/adversarial/ FOR EXECUTION SAFETY:")
violations_found = False

for py_path in sorted(adv_dir.glob("*.py")):
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    imports = []
    writes = []
    net = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
                if alias.name in suspicious_imports:
                    net.append(f"Suspicious import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            imports.append(mod)
            if any(mod.startswith(s) for s in suspicious_imports):
                net.append(f"Suspicious import from: {mod}")
        elif isinstance(node, ast.Call):
            # check open mode
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                for arg in node.args[1:]:
                    if isinstance(arg, ast.Constant) and any(m in str(arg.value) for m in ["w", "a", "+", "x"]):
                        writes.append(f"open() in write/append mode: {arg.value} at line {node.lineno}")
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant) and any(m in str(kw.value.value) for m in ["w", "a", "+", "x"]):
                        writes.append(f"open(mode=...) in write/append mode: {kw.value.value} at line {node.lineno}")
            if isinstance(node.func, ast.Attribute) and node.func.attr in write_calls:
                # Disregard sys.stderr.write or sys.stdout.write if any
                writes.append(f"{node.func.attr}() call at line {node.lineno}")

    print(f"\n[{py_path.name}]")
    print(f"  Imports: {sorted(set(imports))}")
    print(f"  Network calls/imports: {net if net else 'CLEAN (None)'}")
    print(f"  Write/mutation calls:  {writes if writes else 'CLEAN (Read-only)'}")
    if net or writes:
        violations_found = True

print("\n" + "=" * 50)
print(f"SAFETY AUDIT RESULT: {'VIOLATIONS FOUND' if violations_found else 'CLEAN - NO NETWORK OR WRITE HAZARDS'}")
