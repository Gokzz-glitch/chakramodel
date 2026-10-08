import re
from pathlib import Path
from bs4 import BeautifulSoup

templates_dir = Path("templates")

for d in sorted(templates_dir.iterdir()):
    if not d.is_dir():
        continue
    h_file = d / "index.html"
    c_file = d / "style.css"
    h_text = h_file.read_text(encoding="utf-8")
    c_text = c_file.read_text(encoding="utf-8")
    soup = BeautifulSoup(h_text, "html.parser")
    
    print(f"\n==========================================")
    print(f"TEMPLATE: {d.name.upper()}")
    print(f"==========================================")
    
    # Title & Meta
    title = soup.title.string if soup.title else "NO TITLE"
    viewport = soup.find("meta", {"name": "viewport"})
    print(f"Title: {title.strip()}")
    print(f"Viewport: {viewport.get('content') if viewport else 'NO VIEWPORT'}")
    
    # Fonts linked
    font_links = [l.get("href") for l in soup.find_all("link", rel="stylesheet") if "fonts" in (l.get("href") or "")]
    print(f"Font links: {font_links}")
    
    # Sections & IDs
    sections = soup.find_all("section")
    print(f"Sections ({len(sections)}):")
    for s in sections:
        s_id = s.get("id", "no-id")
        s_class = s.get("class", [])
        h = s.find(re.compile(r"^h[1-6]$"))
        h_text_preview = h.get_text(strip=True)[:40] if h else "no-heading"
        print(f"  - #{s_id:<15} class={str(s_class):<25} header='{h_text_preview}'")
        
    # Buttons and CTA links
    cta_buttons = soup.find_all(["button", "a"], class_=re.compile(r"btn|cta|button", re.I))
    print(f"CTAs ({len(cta_buttons)}): {[b.get_text(strip=True)[:25] for b in cta_buttons[:6]]}")
    
    # Forms and inputs
    forms = soup.find_all("form")
    print(f"Forms ({len(forms)}): {[f.get('id') or f.get('class') for f in forms]}")
    for f in forms:
        inputs = [inp.get("name") or inp.get("type") or inp.get("id") for inp in f.find_all(["input", "textarea", "select"])]
        print(f"    Form fields: {inputs}")
        
    # Interactive Features in Script
    script = soup.find("script")
    if script and script.string:
        code = script.string
        print(f"JS features found:")
        if "mobile-nav" in code or "hamburger" in code or "nav-toggle" in code or "menu-toggle" in code:
            print("  - Mobile navigation drawer / toggle")
        if "IntersectionObserver" in code:
            print("  - Scroll reveal / IntersectionObserver animations")
        if "modal" in code or "dialog" in code or "popup" in code:
            print("  - Modal dialog / popup logic")
        if "addEventListener('submit'" in code or "preventDefault" in code:
            print("  - Form submission handler / Toast notification")
        if "theme" in code or "dark-mode" in code or "light-mode" in code:
            print("  - Theme toggle")
