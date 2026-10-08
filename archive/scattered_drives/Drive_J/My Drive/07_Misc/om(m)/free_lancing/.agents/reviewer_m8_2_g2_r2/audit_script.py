import pathlib
import re
import json
from bs4 import BeautifulSoup

root = pathlib.Path('templates')
templates = ['general', 'cafe', 'transport', 'salon', 'retail', 'fitness', 'clinic']

print("=== 1. JS DOM ID INTEGRITY AUDIT ===")
for t in templates:
    html = (root / t / 'index.html').read_text(encoding='utf-8')
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for s in scripts:
        ids = re.findall(r'getElementById\(["\']([^"\']+)["\']\)', s)
        for i in ids:
            if f'id="{i}"' not in html and f"id='{i}'" not in html:
                print(f"[{t.upper()}] JS references missing element ID: '{i}'")

print("\n=== 2. ARIA ROLES AND FOCUS OUTLINES ===")
for t in templates:
    html = (root / t / 'index.html').read_text(encoding='utf-8')
    css = (root / t / 'style.css').read_text(encoding='utf-8')
    
    # Check focus visible in CSS
    has_focus = ':focus' in css or ':focus-visible' in css
    outline_none_without_focus = 'outline: none' in css and ':focus-visible' not in css
    
    # Check landmarks
    soup = BeautifulSoup(html, 'html.parser')
    main_count = len(soup.find_all('main'))
    nav_count = len(soup.find_all('nav'))
    header_count = len(soup.find_all('header'))
    footer_count = len(soup.find_all('footer'))
    
    print(f"[{t.upper()}] :focus styling: {has_focus}, main: {main_count}, nav: {nav_count}, header: {header_count}, footer: {footer_count}")

print("\n=== 3. EXTERNAL RESOURCES AND PERFORMANCE ===")
for t in templates:
    html = (root / t / 'index.html').read_text(encoding='utf-8')
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.find_all('link')
    scripts = soup.find_all('script')
    
    ext_css = [l.get('href') for l in links if l.get('rel') == ['stylesheet'] and l.get('href', '').startswith('http')]
    ext_js = [s.get('src') for s in scripts if s.get('src', '').startswith('http')]
    
    print(f"[{t.upper()}] External CSS: {len(ext_css)} -> {ext_css}")
    print(f"[{t.upper()}] External JS: {len(ext_js)} -> {ext_js}")

print("\n=== 4. COLOR CONTRAST MATH CHECK ===")
# Detailed contrast calculations
def parse_hex(h):
    h = h.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join(c*2 for c in h)
    return int(h[0:2], 16)/255.0, int(h[2:4], 16)/255.0, int(h[4:6], 16)/255.0

def rel_lum(r, g, b):
    def ch(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)

def contrast(rgb1, rgb2):
    l1 = rel_lum(*rgb1)
    l2 = rel_lum(*rgb2)
    return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

for t in templates:
    css = (root / t / 'style.css').read_text(encoding='utf-8')
    # find :root
    root_match = re.search(r':root\s*\{([^}]+)\}', css)
    if root_match:
        vars_dict = {}
        for line in root_match.group(1).split(';'):
            if ':' in line:
                k, v = line.split(':', 1)
                vars_dict[k.strip()] = v.strip()
        bg = vars_dict.get('--bg-primary') or vars_dict.get('--color-bg-dark') or vars_dict.get('--bg-dark') or vars_dict.get('--bg') or '#0B0F19'
        txt = vars_dict.get('--text-primary') or vars_dict.get('--color-cream') or vars_dict.get('--text') or '#F9FAFB'
        accent = vars_dict.get('--accent-primary') or vars_dict.get('--primary') or vars_dict.get('--color-accent') or '#E67E22'
        
        try:
            if bg.startswith('#') and txt.startswith('#'):
                bg_rgb = parse_hex(bg)
                txt_rgb = parse_hex(txt)
                cr = contrast(bg_rgb, txt_rgb)
                print(f"[{t.upper()}] Text vs BG Contrast: {cr:.2f}:1 (bg={bg}, text={txt})")
            if bg.startswith('#') and accent.startswith('#'):
                bg_rgb = parse_hex(bg)
                acc_rgb = parse_hex(accent)
                cr_acc = contrast(bg_rgb, acc_rgb)
                print(f"[{t.upper()}] Accent vs BG Contrast: {cr_acc:.2f}:1 (bg={bg}, accent={accent})")
        except Exception as e:
            print(f"[{t.upper()}] Contrast parsing error: {e}")
