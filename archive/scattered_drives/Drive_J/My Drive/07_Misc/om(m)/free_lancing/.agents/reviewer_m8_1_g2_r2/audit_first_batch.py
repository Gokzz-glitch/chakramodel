import re
from pathlib import Path
from bs4 import BeautifulSoup
from deep_audit import parse_css_color, contrast, extract_root_vars

templates = ["general", "cafe", "transport", "salon"]

for t in templates:
    t_dir = Path("templates") / t
    h_text = (t_dir / "index.html").read_text(encoding="utf-8")
    c_text = (t_dir / "style.css").read_text(encoding="utf-8")
    soup = BeautifulSoup(h_text, "html.parser")
    vars_dict = extract_root_vars(c_text)
    
    print(f"\n=======================================================")
    print(f"VERTICAL: {t.upper()}")
    print(f"=======================================================")
    
    # Check landmarks
    landmarks = {
        "header": bool(soup.find("header")),
        "nav": bool(soup.find("nav")),
        "main": bool(soup.find("main")),
        "footer": bool(soup.find("footer")),
        "section count": len(soup.find_all("section")),
        "article count": len(soup.find_all("article")),
    }
    print(f"Landmarks: {landmarks}")
    
    # Headings hierarchy
    h_tags = [tag.name for tag in soup.find_all(re.compile(r"^h[1-6]$"))]
    print(f"Headings found: {len(h_tags)} -> {h_tags[:8]}...")
    has_h1 = "h1" in h_tags
    h1_count = h_tags.count("h1")
    print(f"H1 presence: {has_h1} (count: {h1_count})")
    
    # Images audit
    imgs = soup.find_all("img")
    missing_alt = [img for img in imgs if not img.get("alt") or len(img.get("alt").strip()) == 0]
    print(f"Images: total {len(imgs)}, missing alt: {len(missing_alt)}")
    
    # Color contrast in tokens
    print("Color Tokens & Contrast:")
    bg_tokens = [k for k in vars_dict if any(x in k.lower() for x in ["bg", "background"]) and not any(x in k.lower() for x in ["glass", "gradient", "rgb", "blur", "radius"])]
    text_tokens = [k for k in vars_dict if any(x in k.lower() for x in ["text", "cream", "color-text", "foreground"]) and not any(x in k.lower() for x in ["rgb", "shadow", "muted-rgb", "xs", "sm", "base", "md", "lg", "xl", "2xl", "3xl", "4xl", "hero"])]
    
    print(f"  Bg tokens: {bg_tokens[:3]}")
    print(f"  Text tokens: {text_tokens[:4]}")
    
    for bg_k in bg_tokens[:3]:
        bg_val = vars_dict[bg_k]
        bg_rgb = parse_css_color(bg_val)
        if not bg_rgb: continue
        for tx_k in text_tokens[:4]:
            tx_val = vars_dict[tx_k]
            tx_rgb = parse_css_color(tx_val)
            if not tx_rgb: continue
            c_ratio = contrast(bg_rgb, tx_rgb)
            pass_str = "PASS (AA)" if c_ratio >= 4.5 else ("PASS (Large text only 3:1)" if c_ratio >= 3.0 else "FAIL (<3:1)")
            print(f"    Contrast: {bg_k} ({bg_val}) vs {tx_k} ({tx_val}) = {c_ratio:.2f}:1 -> {pass_str}")
            
    scripts = soup.find_all("script")
    print(f"Embedded scripts count: {len(scripts)}")
    for i, s in enumerate(scripts):
        s_src = s.get("src")
        if s_src:
            print(f"  Script {i+1}: external src='{s_src}'")
        else:
            s_content = s.string or ""
            print(f"  Script {i+1}: inline ({len(s_content)} chars)")
