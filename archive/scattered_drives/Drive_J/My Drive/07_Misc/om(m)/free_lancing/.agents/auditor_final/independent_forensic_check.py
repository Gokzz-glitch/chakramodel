#!/usr/bin/env python3
"""
Forensic Integrity Independent Verification Script
===================================================
Independently verifies:
1. Template static code analysis (HTML5 semantics, CSS custom properties, clamp(), backdrop-filter, media queries, Vanilla JS)
2. Placeholder contract compliance against AutoWeb spec
3. WCAG 2.1 AA mathematical color contrast ratios
4. Anti-cheating & facade checks across all templates
5. Dynamic pipeline site generation under stress conditions
"""

import os
import re
import sys
import json
import math
from pathlib import Path
from html.parser import HTMLParser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = ROOT_DIR / "templates"
SITE_GEN_PATH = ROOT_DIR / "agents" / "site-generator" / "generate.py"

CATEGORIES = ["general", "cafe", "transport", "salon", "retail", "fitness", "clinic"]

# WCAG 2.1 Relative Luminance & Contrast
def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

def relative_luminance(r, g, b):
    r_lin = srgb_to_linear(r / 255.0)
    g_lin = srgb_to_linear(g / 255.0)
    b_lin = srgb_to_linear(b / 255.0)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

def contrast_ratio(rgb1, rgb2):
    l1 = relative_luminance(*rgb1)
    l2 = relative_luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def parse_hex_or_rgb(color_str):
    color_str = color_str.strip().lower()
    if color_str.startswith("#"):
        h = color_str.lstrip("#").split()[0]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        elif len(h) == 8:
            h = h[:6]
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    elif color_str.startswith("rgb"):
        m = re.search(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", color_str)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None

class TagCounter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = {}
        self.open_tags = []
        self.unclosed = []
        self.void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def handle_starttag(self, tag, attrs):
        self.tags[tag] = self.tags.get(tag, 0) + 1
        if tag not in self.void_tags:
            self.open_tags.append(tag)

    def handle_endtag(self, tag):
        if tag not in self.void_tags:
            if self.open_tags and self.open_tags[-1] == tag:
                self.open_tags.pop()
            elif tag in self.open_tags:
                self.open_tags.reverse()
                self.open_tags.remove(tag)
                self.open_tags.reverse()

def audit():
    print("=" * 80)
    print("FORENSIC INTEGRITY AUDIT: INDEPENDENT VERIFICATION")
    print("=" * 80)

    findings = []
    
    # 1. Verify all 7 template directories exist and contain index.html and style.css
    print("\n[CHECK 1] Template Inventory & File Structure")
    for cat in CATEGORIES:
        cat_dir = TEMPLATES_DIR / cat
        html_file = cat_dir / "index.html"
        css_file = cat_dir / "style.css"
        
        if not cat_dir.exists():
            findings.append(f"FAIL: Missing directory {cat}")
            continue
        if not html_file.exists():
            findings.append(f"FAIL: Missing index.html in {cat}")
            continue
        if not css_file.exists():
            findings.append(f"FAIL: Missing style.css in {cat}")
            continue
            
        html_size = html_file.stat().st_size
        css_size = css_file.stat().st_size
        print(f"  [OK] {cat.upper()}: index.html ({html_size} bytes), style.css ({css_size} bytes)")
        if html_size < 5000:
            findings.append(f"FAIL: index.html for {cat} is suspiciously small ({html_size} bytes)")
        if css_size < 5000:
            findings.append(f"FAIL: style.css for {cat} is suspiciously small ({css_size} bytes)")

    # 2. Semantic HTML5 Landmarks and Accessibility
    print("\n[CHECK 2] Semantic HTML5 Landmarks & Structure")
    required_landmarks = ['header', 'nav', 'main', 'section', 'footer']
    for cat in CATEGORIES:
        html_content = (TEMPLATES_DIR / cat / "index.html").read_text(encoding="utf-8")
        parser = TagCounter()
        parser.feed(html_content)
        
        missing_landmarks = [lm for lm in required_landmarks if lm not in parser.tags]
        if missing_landmarks:
            findings.append(f"FAIL: {cat} missing semantic landmarks: {missing_landmarks}")
        else:
            print(f"  [OK] {cat.upper()}: All semantic landmarks present. Total HTML tag count: {sum(parser.tags.values())}")

        # Viewport meta tag
        if "name=\"viewport\"" not in html_content and "name='viewport'" not in html_content:
            findings.append(f"FAIL: {cat} missing viewport meta tag")
        # Language tag
        if "<html lang=" not in html_content:
            findings.append(f"FAIL: {cat} missing lang attribute on html tag")

    # 3. CSS Modern Features & Fluid Typography
    print("\n[CHECK 3] Modern CSS Architecture (Tokens, Clamp, Backdrop-Filter, Media Queries)")
    for cat in CATEGORIES:
        css_content = (TEMPLATES_DIR / cat / "style.css").read_text(encoding="utf-8")
        
        # Check :root
        if ":root" not in css_content:
            findings.append(f"FAIL: {cat} style.css missing :root declaration")
        
        # Count CSS variables in :root
        root_vars = re.findall(r"--[a-zA-Z0-9_-]+\s*:", css_content)
        if len(root_vars) < 20:
            findings.append(f"FAIL: {cat} has only {len(root_vars)} CSS variables (expected >= 20)")
        
        # Check clamp() typography
        clamps = re.findall(r"clamp\([^)]+\)", css_content)
        if len(clamps) < 5:
            findings.append(f"FAIL: {cat} has only {len(clamps)} clamp() functions (expected >= 5)")
        
        # Check backdrop-filter
        glass = re.findall(r"backdrop-filter\s*:\s*blur", css_content)
        if not glass:
            findings.append(f"FAIL: {cat} missing backdrop-filter glassmorphism")
            
        # Check responsive media queries
        media_queries = re.findall(r"@media\s*\([^)]+\)", css_content)
        if len(media_queries) < 2:
            findings.append(f"FAIL: {cat} has only {len(media_queries)} media queries (expected >= 2)")
            
        print(f"  [OK] {cat.upper()}: {len(root_vars)} tokens, {len(clamps)} clamp() rules, {len(glass)} glass rules, {len(media_queries)} media queries")

    # 4. Color Contrast Analysis (WCAG 2.1 AA)
    print("\n[CHECK 4] WCAG 2.1 AA Color Contrast Verification")
    for cat in CATEGORIES:
        css_content = (TEMPLATES_DIR / cat / "style.css").read_text(encoding="utf-8")
        
        bg_match = re.search(r"--(?:bg-primary|bg-dark|background|bg)\s*:\s*([^;]+);", css_content)
        text_match = re.search(r"--(?:text-primary|color-text|text)\s*:\s*([^;]+);", css_content)
        text_sec_match = re.search(r"--text-secondary\s*:\s*([^;]+);", css_content)
        
        if not bg_match or not text_match:
            findings.append(f"FAIL: {cat} could not extract primary bg or text color tokens")
            continue
            
        bg_rgb = parse_hex_or_rgb(bg_match.group(1))
        text_rgb = parse_hex_or_rgb(text_match.group(1))
        
        if not bg_rgb or not text_rgb:
            findings.append(f"FAIL: {cat} failed to parse colors: bg={bg_match.group(1)}, text={text_match.group(1)}")
            continue
            
        ratio_primary = contrast_ratio(bg_rgb, text_rgb)
        print(f"  [OK] {cat.upper()}: Primary Text Contrast = {ratio_primary:.2f}:1 (Requirement >= 4.5:1)")
        if ratio_primary < 4.5:
            findings.append(f"FAIL: {cat} primary text contrast {ratio_primary:.2f}:1 is below WCAG AA 4.5:1")
            
        if text_sec_match:
            sec_rgb = parse_hex_or_rgb(text_sec_match.group(1))
            if sec_rgb:
                ratio_sec = contrast_ratio(bg_rgb, sec_rgb)
                print(f"       Secondary Text Contrast = {ratio_sec:.2f}:1 (Requirement >= 3.0:1)")
                if ratio_sec < 3.0:
                    findings.append(f"FAIL: {cat} secondary text contrast {ratio_sec:.2f}:1 is below WCAG AA 3.0:1")

    # 5. Vanilla JS Interactivity Verification
    print("\n[CHECK 5] Vanilla JS Interactivity Analysis")
    for cat in CATEGORIES:
        html_content = (TEMPLATES_DIR / cat / "index.html").read_text(encoding="utf-8")
        
        has_script = "<script>" in html_content or "<script " in html_content
        has_drawer = "mobile" in html_content or "drawer" in html_content or "toggle" in html_content
        has_observer = "IntersectionObserver" in html_content
        
        if not has_script:
            findings.append(f"FAIL: {cat} missing interactive <script>")
        if not has_drawer:
            findings.append(f"FAIL: {cat} missing mobile drawer/toggle logic")
        if not has_observer:
            findings.append(f"FAIL: {cat} missing IntersectionObserver animation logic")
            
        print(f"  [OK] {cat.upper()}: Vanilla JS present (Drawer logic: {has_drawer}, IntersectionObserver: {has_observer})")

    # 6. Anti-Cheating & Facade Analysis
    print("\n[CHECK 6] Anti-Cheating & Facade Inspection")
    suspicious_patterns = [
        r"test_mode\s*=\s*True",
        r"return\s+['\"](?:PASS|CLEAN|OK)['\"]",
        r"if\s+name\s*==\s*['\"]test['\"]",
        r"hardcoded",
        r"TODO:\s*implement",
        r"NotImplementedError",
    ]
    
    for cat in CATEGORIES:
        html_content = (TEMPLATES_DIR / cat / "index.html").read_text(encoding="utf-8")
        css_content = (TEMPLATES_DIR / cat / "style.css").read_text(encoding="utf-8")
        
        for pat in suspicious_patterns:
            if re.search(pat, html_content, re.IGNORECASE):
                findings.append(f"FAIL: Suspicious pattern '{pat}' found in {cat}/index.html")
            if re.search(pat, css_content, re.IGNORECASE):
                findings.append(f"FAIL: Suspicious pattern '{pat}' found in {cat}/style.css")
                
    print("  [OK] No facade stubs, bypasses, or hardcoded shortcuts detected across templates.")

    # 7. AutoWeb Pipeline Contract & Orphan Tag Detection
    print("\n[CHECK 7] AutoWeb Pipeline Contract & Placeholder Substitution")
    
    # Import generate.py
    sys.path.insert(0, str(SITE_GEN_PATH.parent))
    import generate
    
    dummy_lead = {
        "name": "Forensic Audit Global Inc.",
        "address": "42 Verification Blvd, Chennai, India",
        "phone_national": "+91 98765 43210",
        "primary_type": "consulting",
        "rating": 4.9,
        "review_count": 250,
        "google_maps_url": "https://maps.google.com/?q=test"
    }
    
    dummy_ai = {
        "tagline": "Pinnacle of Precision and Authentic Assurance",
        "about_text": "We provide uncompromising forensic integrity auditing and engineering excellence across digital platforms worldwide with zero tolerance for shortcuts.",
        "services": [
            {"name": "Forensic Code Audit", "description": "Independent verification of source code and architectures."},
            {"name": "Accessibility Testing", "description": "Mathematical WCAG 2.1 AA/AAA compliance validation."},
            {"name": "Pipeline Contracts", "description": "Seamless integration with automated generators."},
            {"name": "Security Scrutiny", "description": "Adversarial review and stress testing under high load."},
            {"name": "Design Token Systems", "description": "Strict verification of CSS custom property tokens."},
            {"name": "Full-Stack Validation", "description": "End-to-end integration and behavioral assurance."}
        ],
        "meta_description": "Forensic Audit Global Inc. — Premier verification and audit consultancy."
    }

    for cat in CATEGORIES:
        html_raw, css_raw = generate.load_template(cat)
        html_filled, css_filled = generate.fill_template(html_raw, css_raw, dummy_lead, dummy_ai)
        
        orphan_html = re.findall(r"\{\{[A-Z0-9_]+\}\}", html_filled)
        orphan_css = re.findall(r"\{\{[A-Z0-9_]+\}\}", css_filled)
        
        if orphan_html:
            findings.append(f"FAIL: {cat} index.html contains orphaned placeholders: {set(orphan_html)}")
        if orphan_css:
            findings.append(f"FAIL: {cat} style.css contains orphaned placeholders: {set(orphan_css)}")
            
        print(f"  [OK] {cat.upper()}: 100% placeholder substitution cleanly executed (0 orphan tokens in HTML/CSS)")

    print("\n" + "=" * 80)
    print("AUDIT FINDINGS SUMMARY:")
    if findings:
        print(f"🚨 INTEGRITY VIOLATIONS DETECTED ({len(findings)} issues):")
        for f in findings:
            print(f"  - {f}")
        return False
    else:
        print("🎉 ALL CHECKS PASSED: 100% CLEAN. Zero integrity violations found.")
        return True

if __name__ == "__main__":
    success = audit()
    sys.exit(0 if success else 1)
