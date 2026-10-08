"""
Adversarial Detection Test for Flaw 06:
Unguarded torch.load() calls across the codebase without weights_only=True.

Security Risk: Arbitrary Code Execution (ACE) via Python pickle deserialization.
Exit code:
  1 if any torch.load() call lacks weights_only=True
  0 if all torch.load() calls are strictly guarded with weights_only=True
"""
import ast
import os
import sys
from pathlib import Path

def check_file(file_path):
    violations = []
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    
    if "torch.load" not in content:
        return violations

    try:
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        return violations

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check if calling torch.load or *.load
            is_torch_load = False
            if isinstance(node.func, ast.Attribute) and node.func.attr == "load":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "torch":
                    is_torch_load = True
            elif isinstance(node.func, ast.Name) and node.func.id == "load":
                # Check imports if needed, but torch.load is standard
                pass

            if is_torch_load:
                has_weights_only = False
                for kw in node.keywords:
                    if kw.arg == "weights_only":
                        if isinstance(kw.value, ast.Constant) and kw.value.value is True:
                            has_weights_only = True
                if not has_weights_only:
                    violations.append((file_path, node.lineno))

    return violations

def main():
    repo_root = Path(r"M:\chakramodel")
    # Targets to inspect: active src and core execution paths
    target_dirs = [repo_root / "src", repo_root / "scripts", repo_root / "kaggle_package", repo_root / "kaggle_bundle"]
    
    all_violations = []
    for tdir in target_dirs:
        if not tdir.exists():
            continue
        for py_path in tdir.rglob("*.py"):
            v = check_file(py_path)
            all_violations.extend(v)

    if all_violations:
        print(f"[FAIL] Flaw 06 detected: {len(all_violations)} unguarded torch.load() calls found without weights_only=True:")
        for path, line in all_violations:
            print(f"  - {path.relative_to(repo_root)}:{line}")
        sys.exit(1)
    else:
        print("[PASS] Flaw 06 resolved: All torch.load() calls explicitly specify weights_only=True.")
        sys.exit(0)

if __name__ == "__main__":
    main()
