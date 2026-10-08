import os
import re
from pathlib import Path
from bs4 import BeautifulSoup

templates_dir = Path("templates")

print("=== TEMPLATE METRICS ===")
for d in sorted(templates_dir.iterdir()):
    if not d.is_dir():
        continue
    h_file = d / "index.html"
    c_file = d / "style.css"
    h_lines = len(h_file.read_text(encoding="utf-8").splitlines()) if h_file.exists() else 0
    c_lines = len(c_file.read_text(encoding="utf-8").splitlines()) if c_file.exists() else 0
    h_size = h_file.stat().st_size if h_file.exists() else 0
    c_size = c_file.stat().st_size if c_file.exists() else 0
    print(f"{d.name:10} | HTML: {h_size:6} B ({h_lines:4} lines) | CSS: {c_size:6} B ({c_lines:4} lines)")

print("\n=== PLACEHOLDERS AUDIT ===")
placeholder_regex = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
for d in sorted(templates_dir.iterdir()):
    if not d.is_dir():
        continue
    h_text = (d / "index.html").read_text(encoding="utf-8")
    c_text = (d / "style.css").read_text(encoding="utf-8")
    h_placeholders = set(placeholder_regex.findall(h_text))
    c_placeholders = set(placeholder_regex.findall(c_text))
    print(f"\n[{d.name}] Total unique placeholders in HTML: {len(h_placeholders)}, in CSS: {len(c_placeholders)}")
    print(f"  HTML sample tokens: {sorted(list(h_placeholders))[:8]}")
    if c_placeholders:
        print(f"  CSS tokens: {sorted(list(c_placeholders))}")

print("\n=== CSS FEATURES AUDIT (clamp, backdrop-filter, grid, transitions, @media, :root) ===")
for d in sorted(templates_dir.iterdir()):
    if not d.is_dir():
        continue
    c_text = (d / "style.css").read_text(encoding="utf-8")
    h_text = (d / "index.html").read_text(encoding="utf-8")
    
    clamp_count = len(re.findall(r"clamp\(", c_text))
    backdrop_count = len(re.findall(r"backdrop-filter", c_text))
    media_count = len(re.findall(r"@media", c_text))
    grid_count = len(re.findall(r"grid-template", c_text)) + len(re.findall(r"display:\s*grid", c_text))
    custom_props = len(re.findall(r"--[a-zA-Z0-9_-]+:", c_text))
    
    print(f"[{d.name:10}] clamp(): {clamp_count:2} | backdrop-filter: {backdrop_count:2} | @media: {media_count:2} | grid: {grid_count:2} | CSS vars: {custom_props:2}")
