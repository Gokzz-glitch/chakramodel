import os
import sys
import re
import math
import json
from pathlib import Path

PROJECT_ROOT = Path("M:/free_lancing")
TEMPLATES_DIR = PROJECT_ROOT / "templates"
categories = ["general", "cafe", "transport", "salon", "retail", "fitness", "clinic"]

print("=== INDEPENDENT FORENSIC AUDIT SCRIPT ===")

def parse_css_color(c):
    c = c.strip().rstrip(";").lower()
    if c.startswith("#"):
        h = c.lstrip("#")
        if len(h) == 3:
            h = "".join([ch * 2 for ch in h])
        if len(h) >= 6:
            r = int(h[0:2], 16) / 255.0
            g = int(h[2:4], 16) / 255.0
            b = int(h[4:6], 16) / 255.0
            return (r, g, b)
    elif c.startswith("rgba") or c.startswith("rgb"):
        nums = re.findall(r"[\d.]+", c)
        if len(nums) >= 3:
            return (float(nums[0]) / 255.0, float(nums[1]) / 255.0, float(nums[2]) / 255.0)
    return None

def luminance(r, g, b):
    def channel(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

def contrast(c1, c2):
    l1 = luminance(*c1)
    l2 = luminance(*c2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

results = {}

for cat in categories:
    tdir = TEMPLATES_DIR / cat
    hpath = tdir / "index.html"
    cpath = tdir / "style.css"
    
    assert hpath.exists(), f"Missing {hpath}"
    assert cpath.exists(), f"Missing {cpath}"
    
    htext = hpath.read_text(encoding="utf-8")
    ctext = cpath.read_text(encoding="utf-8")
    
    hsize = len(htext)
    csize = len(ctext)
    
    # 1. Placeholders
    placeholders = set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", htext))
    
    # 2. Design tokens
    has_scroll = ("IntersectionObserver" in htext) or ("fade-in" in ctext) or ("reveal" in ctext)
    has_glass = ("backdrop-filter" in ctext) or ("-webkit-backdrop-filter" in ctext)
    has_hover = (":hover" in ctext) and (("transform" in ctext) or ("transition" in ctext))
    has_clamp = "clamp(" in ctext
    has_fonts = ("fonts.googleapis.com" in htext) and ("font-family" in ctext)
    has_media = "@media" in ctext
    
    # 3. Semantic elements
    has_header = "<header" in htext
    has_nav = "<nav" in htext
    has_main = "<main" in htext or "<section" in htext
    has_footer = "<footer" in htext
    has_viewport = 'name="viewport"' in htext or "name='viewport'" in htext
    
    # 4. Contrast ratio
    var_dict = {}
    for match in re.finditer(r"(--[\w-]+)\s*:\s*([^;]+);", ctext):
        var_dict[match.group(1)] = match.group(2).strip()
    
    bg_val = (
        var_dict.get("--bg-primary")
        or var_dict.get("--color-bg-dark")
        or var_dict.get("--bg-dark")
        or var_dict.get("--bg")
        or "#0b0f19"
    )
    text_val = (
        var_dict.get("--text-primary")
        or var_dict.get("--color-cream")
        or var_dict.get("--text")
        or "#f9fafb"
    )
    
    c_bg = parse_css_color(bg_val) or (0.05, 0.07, 0.1)
    c_text = parse_css_color(text_val) or (0.98, 0.98, 0.98)
    cr = contrast(c_bg, c_text)
    
    results[cat] = {
        "html_size": hsize,
        "css_size": csize,
        "placeholders_count": len(placeholders),
        "placeholders": sorted(list(placeholders)),
        "has_scroll": has_scroll,
        "has_glass": has_glass,
        "has_hover": has_hover,
        "has_clamp": has_clamp,
        "has_fonts": has_fonts,
        "has_media": has_media,
        "has_header": has_header,
        "has_nav": has_nav,
        "has_main": has_main,
        "has_footer": has_footer,
        "has_viewport": has_viewport,
        "contrast_ratio": cr,
        "tokens_count": len(var_dict),
    }

for cat, r in results.items():
    print(f"Category: {cat:<12} | HTML: {r['html_size']:>5} B | CSS: {r['css_size']:>5} B | Placeholders: {r['placeholders_count']:>2} | Contrast: {r['contrast_ratio']:>5.2f}:1 | Tokens: {r['tokens_count']:>3}")
    print(f"  Aesthetics: Scroll={r['has_scroll']}, Glass={r['has_glass']}, Hover={r['has_hover']}, Clamp={r['has_clamp']}, Fonts={r['has_fonts']}, Media={r['has_media']}")
    print(f"  Semantics: Header={r['has_header']}, Nav={r['has_nav']}, Main/Section={r['has_main']}, Footer={r['has_footer']}, Viewport={r['has_viewport']}")
    print(f"  Sample Placeholders: {r['placeholders'][:6]} ... ({len(r['placeholders'])} total)")
    print("-" * 80)
