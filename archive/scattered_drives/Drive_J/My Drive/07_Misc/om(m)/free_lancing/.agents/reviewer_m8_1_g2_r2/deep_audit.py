import re
from pathlib import Path
from bs4 import BeautifulSoup

def parse_css_color(color_str):
    if not color_str:
        return None
    cleaned = color_str.strip().split()[0].rstrip(";,").lower()
    named = {"white": (1.0, 1.0, 1.0), "black": (0.0, 0.0, 0.0), "transparent": (0.0, 0.0, 0.0)}
    if cleaned in named:
        return named[cleaned]
    if cleaned.startswith("#"):
        h = cleaned.lstrip("#")
        if len(h) == 3:
            h = "".join([c*2 for c in h])
        elif len(h) == 8:
            h = h[:6]
        if len(h) == 6:
            try:
                return (int(h[0:2], 16)/255.0, int(h[2:4], 16)/255.0, int(h[4:6], 16)/255.0)
            except ValueError:
                return None
    rgb_m = re.match(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", cleaned)
    if rgb_m:
        return (int(rgb_m.group(1))/255.0, int(rgb_m.group(2))/255.0, int(rgb_m.group(3))/255.0)
    hsl_m = re.match(r"hsla?\s*\(\s*(\d+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%", cleaned)
    if hsl_m:
        h = float(hsl_m.group(1)) / 360.0
        s = float(hsl_m.group(2)) / 100.0
        l = float(hsl_m.group(3)) / 100.0
        # convert HSL to RGB
        def hue2rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
        if s == 0:
            return (l, l, l)
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        return (hue2rgb(p, q, h + 1/3), hue2rgb(p, q, h), hue2rgb(p, q, h - 1/3))
    return None

def luminance(r, g, b):
    def ch(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)

def contrast(rgb1, rgb2):
    l1 = luminance(*rgb1)
    l2 = luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)

def extract_root_vars(css_text):
    clean_css = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    variables = {}
    for block in re.findall(r":root\s*\{([^}]+)\}", clean_css, re.DOTALL):
        for decl in block.split(";"):
            if ":" in decl:
                k, v = decl.split(":", 1)
                k = k.strip()
                v = v.strip()
                if k.startswith("--"):
                    variables[k] = v
    return variables

templates = ["general", "cafe", "transport", "salon", "retail", "fitness", "clinic"]

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
    print(f"Headings found: {len(h_tags)} -> {h_tags[:10]}...")
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
    text_tokens = [k for k in vars_dict if any(x in k.lower() for x in ["text", "cream", "color-text", "foreground"]) and not any(x in k.lower() for x in ["rgb", "shadow", "muted-rgb"])]
    accent_tokens = [k for k in vars_dict if any(x in k.lower() for x in ["accent", "primary", "gold", "cyan", "secondary"]) and not any(x in k.lower() for x in ["rgb", "gradient", "glow", "glass", "bg"])]
    
    print(f"  Bg tokens found: {bg_tokens}")
    print(f"  Text tokens found: {text_tokens}")
    print(f"  Accent tokens found: {accent_tokens}")
    
    # Test primary text against primary bg
    for bg_k in bg_tokens[:3]:
        bg_val = vars_dict[bg_k]
        bg_rgb = parse_css_color(bg_val)
        if not bg_rgb:
            continue
        for tx_k in text_tokens[:4]:
            tx_val = vars_dict[tx_k]
            tx_rgb = parse_css_color(tx_val)
            if not tx_rgb:
                continue
            c_ratio = contrast(bg_rgb, tx_rgb)
            pass_str = "PASS (AA)" if c_ratio >= 4.5 else ("PASS (Large text only 3:1)" if c_ratio >= 3.0 else "FAIL (<3:1)")
            print(f"    Contrast: {bg_k} ({bg_val}) vs {tx_k} ({tx_val}) = {c_ratio:.2f}:1 -> {pass_str}")
    
    # Check clamp instances
    clamp_matches = re.findall(r"clamp\([^)]+\)", c_text)
    print(f"Sample clamp() rules ({len(clamp_matches)} total):")
    for cm in clamp_matches[:3]:
        print(f"    {cm}")
        
    # Check JS scripts embedded in HTML
    scripts = soup.find_all("script")
    print(f"Embedded scripts count: {len(scripts)}")
    for i, s in enumerate(scripts):
        s_src = s.get("src")
        if s_src:
            print(f"  Script {i+1}: external src='{s_src}'")
        else:
            s_content = s.string or ""
            features = []
            if "IntersectionObserver" in s_content: features.append("IntersectionObserver / Scroll Reveal")
            if "querySelector" in s_content: features.append("DOM selection")
            if "addEventListener" in s_content: features.append("Event listeners")
            if "localStorage" in s_content: features.append("Theme persistence / localStorage")
            print(f"  Script {i+1}: inline ({len(s_content)} chars) -> Features: {', '.join(features)}")
