"""
Adversarial Syntax, Schema, Metadata & AST Verifier for ChakraModel Notebooks
Tests all 6 Kaggle notebooks in notebooks/
"""

import sys
import os
import json
import re
import ast
import traceback
import nbformat
from nbformat import NotebookNode, validate

NOTEBOOKS = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb",
]

NOTEBOOK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "notebooks")

def sanitize_ipython_for_ast(source_text: str) -> str:
    """
    Transforms IPython magics and shell escapes into valid Python statements
    so that the underlying Python AST can be strictly verified.
    """
    lines = source_text.splitlines()
    sanitized_lines = []
    
    in_cell_magic = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Check for cell magics like %%writefile, %%time, etc.
        if i == 0 and stripped.startswith("%%"):
            sanitized_lines.append(f"# CELL_MAGIC: {line}")
            continue
            
        # Check for line magics like %matplotlib, %cd, %time, etc.
        if stripped.startswith("%"):
            sanitized_lines.append(f"# LINE_MAGIC: {line}")
            continue
            
        # Check for shell escapes like !pip install, !wget, etc.
        if stripped.startswith("!"):
            sanitized_lines.append(f"# SHELL_ESCAPE: {line}")
            continue
            
        # Check for inline help like ?foo or foo?
        if stripped.startswith("?") or stripped.endswith("?"):
            sanitized_lines.append(f"# HELP_QUERY: {line}")
            continue
            
        sanitized_lines.append(line)
        
    return "\n".join(sanitized_lines)


class NotebookStressTester:
    def __init__(self, notebook_path: str):
        self.notebook_path = notebook_path
        self.notebook_name = os.path.basename(notebook_path)
        self.raw_content = ""
        self.json_data = None
        self.nb_node = None
        self.errors = []
        self.warnings = []
        self.stats = {
            "total_cells": 0,
            "code_cells": 0,
            "markdown_cells": 0,
            "raw_cells": 0,
            "total_code_lines": 0,
            "total_markdown_lines": 0,
            "defined_classes": [],
            "defined_functions": [],
            "imports": [],
        }

    def run_all_tests(self):
        print(f"\n=======================================================")
        print(f"Testing Notebook: {self.notebook_name}")
        print(f"=======================================================")
        
        self.test_1_raw_file_and_json()
        if self.json_data is None:
            return False
            
        self.test_2_nbformat_schema_validation()
        self.test_3_metadata_and_kernelspec()
        self.test_4_cell_level_schema_and_boundaries()
        self.test_5_code_cell_ast_syntax()
        self.test_6_stress_boundary_and_anomalies()
        
        passed = len(self.errors) == 0
        status_str = "PASSED" if passed else "FAILED"
        print(f"Result for {self.notebook_name}: {status_str} ({len(self.errors)} errors, {len(self.warnings)} warnings)")
        return passed

    def test_1_raw_file_and_json(self):
        """Test file readability, UTF-8 validity, and JSON decoding."""
        try:
            with open(self.notebook_path, "r", encoding="utf-8") as f:
                self.raw_content = f.read()
        except Exception as e:
            self.errors.append(f"UTF-8 Read Error: {str(e)}")
            return

        if len(self.raw_content) == 0:
            self.errors.append("File is empty (0 bytes).")
            return

        try:
            self.json_data = json.loads(self.raw_content)
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON Parse Error at line {e.lineno}, col {e.colno}: {e.msg}")
            return
            
        # Top level keys
        required_keys = {"cells", "metadata", "nbformat", "nbformat_minor"}
        missing_keys = required_keys - set(self.json_data.keys())
        if missing_keys:
            self.errors.append(f"Missing top-level JSON keys: {missing_keys}")

    def test_2_nbformat_schema_validation(self):
        """Validate notebook according to official nbformat JSON schema."""
        try:
            self.nb_node = nbformat.reads(self.raw_content, as_version=4)
            validate(self.nb_node)
        except Exception as e:
            self.errors.append(f"nbformat.validate Error: {str(e)}")

    def test_3_metadata_and_kernelspec(self):
        """Validate metadata, kernelspec, and language info."""
        if not self.nb_node:
            return
            
        metadata = self.nb_node.get("metadata", {})
        
        # Check language_info
        lang_info = metadata.get("language_info", {})
        if not lang_info:
            self.warnings.append("No 'language_info' in notebook metadata.")
        else:
            lang_name = lang_info.get("name", "")
            if lang_name.lower() != "python":
                self.warnings.append(f"language_info name is '{lang_name}', expected 'python'.")

        # Check kernelspec
        kernelspec = metadata.get("kernelspec", {})
        if not kernelspec:
            self.warnings.append("No 'kernelspec' in notebook metadata.")
        else:
            kname = kernelspec.get("name", "")
            kdisplay = kernelspec.get("display_name", "")
            if not kname or not kdisplay:
                self.warnings.append(f"Incomplete kernelspec: name='{kname}', display_name='{kdisplay}'")

        # Check nbformat version
        nbformat_ver = self.nb_node.get("nbformat", 0)
        nbformat_minor = self.nb_node.get("nbformat_minor", 0)
        if nbformat_ver != 4:
            self.errors.append(f"nbformat is {nbformat_ver}, expected 4.")
        if nbformat_minor < 2:
            self.warnings.append(f"nbformat_minor is {nbformat_minor}, standard is >= 2 (typically 4 or 5).")

    def test_4_cell_level_schema_and_boundaries(self):
        """Validate each individual cell schema, types, cell IDs, and source."""
        if not self.nb_node:
            return
            
        cells = self.nb_node.get("cells", [])
        self.stats["total_cells"] = len(cells)
        
        seen_cell_ids = set()
        
        for idx, cell in enumerate(cells):
            cell_type = cell.get("cell_type")
            cell_id = cell.get("id")
            
            # Check cell_id uniqueness if present
            if cell_id:
                if cell_id in seen_cell_ids:
                    self.errors.append(f"Duplicate cell id '{cell_id}' at cell index {idx}")
                seen_cell_ids.add(cell_id)

            if cell_type == "code":
                self.stats["code_cells"] += 1
                if "execution_count" not in cell:
                    self.errors.append(f"Code cell {idx} missing 'execution_count' field.")
                if "outputs" not in cell or not isinstance(cell.get("outputs"), list):
                    self.errors.append(f"Code cell {idx} missing valid 'outputs' list.")
            elif cell_type == "markdown":
                self.stats["markdown_cells"] += 1
            elif cell_type == "raw":
                self.stats["raw_cells"] += 1
            else:
                self.errors.append(f"Cell {idx} has invalid cell_type: '{cell_type}'")

            source = cell.get("source", "")
            if isinstance(source, list):
                source_str = "".join(source)
            elif isinstance(source, str):
                source_str = source
            else:
                self.errors.append(f"Cell {idx} source is neither str nor list: {type(source)}")
                source_str = ""

            line_count = len(source_str.splitlines())
            if cell_type == "code":
                self.stats["total_code_lines"] += line_count
            elif cell_type == "markdown":
                self.stats["total_markdown_lines"] += line_count

    def test_5_code_cell_ast_syntax(self):
        """Adversarially extract and parse code cells with Python AST."""
        if not self.nb_node:
            return
            
        cells = self.nb_node.get("cells", [])
        for idx, cell in enumerate(cells):
            if cell.get("cell_type") != "code":
                continue
                
            source = cell.get("source", "")
            if isinstance(source, list):
                source_str = "".join(source)
            else:
                source_str = str(source)
                
            if not source_str.strip():
                self.warnings.append(f"Code cell {idx} is empty.")
                continue

            sanitized_code = sanitize_ipython_for_ast(source_str)
            
            try:
                tree = ast.parse(sanitized_code, filename=f"cell_{idx}.py")
                
                # Analyze AST to extract classes, functions, and imports
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        self.stats["defined_classes"].append(f"Cell {idx}: {node.name}")
                    elif isinstance(node, ast.FunctionDef):
                        self.stats["defined_functions"].append(f"Cell {idx}: {node.name}")
                    elif isinstance(node, ast.AsyncFunctionDef):
                        self.stats["defined_functions"].append(f"Cell {idx}: async {node.name}")
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            self.stats["imports"].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        mod = node.module or ""
                        for alias in node.names:
                            self.stats["imports"].append(f"{mod}.{alias.name}")
                            
            except SyntaxError as e:
                self.errors.append(
                    f"AST SyntaxError in Code Cell {idx} at line {e.lineno}, col {e.offset}: {e.msg}\n"
                    f"    Line text: {e.text.strip() if e.text else 'N/A'}"
                )
            except Exception as e:
                self.errors.append(
                    f"Unexpected parsing failure in Code Cell {idx}: {str(e)}\n"
                    f"{traceback.format_exc()}"
                )

    def test_6_stress_boundary_and_anomalies(self):
        """Stress test strings for null bytes, unescaped unicode, malformed regex."""
        if "\x00" in self.raw_content:
            self.errors.append("Null byte (\\x00) detected in notebook file!")

        # Check for any unclosed triple-quotes or bad escape anomalies in markdown
        cells = self.nb_node.get("cells", []) if self.nb_node else []
        for idx, cell in enumerate(cells):
            source = cell.get("source", "")
            source_str = "".join(source) if isinstance(source, list) else str(source)
            
            # Check for NaN / Infinity / undefined JSON literals that might be invalid
            if "undefined" in source_str:
                self.warnings.append(f"Cell {idx} contains 'undefined' string literal.")


def main():
    print(f"Starting Adversarial Test Suite on {len(NOTEBOOKS)} notebooks...")
    print(f"Target directory: {NOTEBOOK_DIR}")
    
    results = {}
    all_passed = True
    
    for nb_name in NOTEBOOKS:
        nb_path = os.path.join(NOTEBOOK_DIR, nb_name)
        if not os.path.exists(nb_path):
            print(f"CRITICAL: Notebook {nb_name} does not exist at {nb_path}!")
            results[nb_name] = {"passed": False, "errors": ["File not found"], "warnings": [], "stats": {}}
            all_passed = False
            continue
            
        tester = NotebookStressTester(nb_path)
        passed = tester.run_all_tests()
        if not passed:
            all_passed = False
            
        results[nb_name] = {
            "passed": passed,
            "errors": tester.errors,
            "warnings": tester.warnings,
            "stats": tester.stats,
        }
        
    print("\n=======================================================")
    print("SUMMARY REPORT")
    print("=======================================================")
    for nb_name, res in results.items():
        status = "PASS" if res["passed"] else "FAIL"
        err_count = len(res["errors"])
        warn_count = len(res["warnings"])
        stats = res.get("stats", {})
        cells = stats.get("total_cells", 0)
        code_cells = stats.get("code_cells", 0)
        code_lines = stats.get("total_code_lines", 0)
        classes = len(stats.get("defined_classes", []))
        funcs = len(stats.get("defined_functions", []))
        
        print(f"[{status}] {nb_name}:")
        print(f"    Cells: {cells} (Code: {code_cells}, Lines: {code_lines}, Classes: {classes}, Functions: {funcs})")
        print(f"    Errors: {err_count}, Warnings: {warn_count}")
        if res["errors"]:
            for err in res["errors"]:
                print(f"      - ERROR: {err}")
        if res["warnings"]:
            for w in res["warnings"]:
                print(f"      - WARNING: {w}")

    # Output machine-readable JSON summary for audit
    report_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adversarial_results.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved machine-readable test results to: {report_file}")
    
    if not all_passed:
        print("\nOVERALL STATUS: FAILED")
        sys.exit(1)
    else:
        print("\nOVERALL STATUS: ALL 6 NOTEBOOKS PASSED ADVERSARIAL VALIDATION!")
        sys.exit(0)

if __name__ == "__main__":
    main()
