import sys
import importlib
import subprocess
import shutil

print(f"Python Executable: {sys.executable}")
print(f"Python Version: {sys.version}")

candidates = [
    ("fitz (pymupdf)", "fitz"),
    ("pymupdf", "pymupdf"),
    ("pymupdf4llm", "pymupdf4llm"),
    ("pdfplumber", "pdfplumber"),
    ("pypdf", "pypdf"),
    ("PyPDF2", "PyPDF2"),
    ("pdfminer.six", "pdfminer"),
    ("marker", "marker"),
    ("docling", "docling"),
    ("unstructured", "unstructured"),
    ("fpdf2 (import fpdf)", "fpdf"),
    ("reportlab", "reportlab"),
    ("tabulate", "tabulate"),
    ("markdown", "markdown"),
    ("markdown_it", "markdown_it"),
    ("rich", "rich"),
    ("bs4 (BeautifulSoup4)", "bs4"),
    ("google.genai", "google.genai"),
    ("google.generativeai", "google.generativeai"),
    ("openai", "openai"),
    ("anthropic", "anthropic")
]

print("\n--- Package Probing ---")
for label, mod_name in candidates:
    try:
        mod = importlib.import_module(mod_name)
        ver = getattr(mod, "__version__", getattr(mod, "VERSION", "installed"))
        file_path = getattr(mod, "__file__", "builtin/namespace")
        print(f"[OK] {label}: {ver} ({file_path})")
    except ImportError as e:
        print(f"[MISSING] {label}: {e}")

print("\n--- CLI Tools Probing ---")
cli_tools = ["pandoc", "pdftotext", "pdftoppm", "pdfimages", "tesseract", "gs", "gswin64c", "uv", "pip", "git"]
for cli in cli_tools:
    path = shutil.which(cli)
    if path:
        print(f"[FOUND] {cli} at {path}")
    else:
        print(f"[NOT FOUND] {cli}")
