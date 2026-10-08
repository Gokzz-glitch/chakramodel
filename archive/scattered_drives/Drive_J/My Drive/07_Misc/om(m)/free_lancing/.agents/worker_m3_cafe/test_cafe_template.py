import os
import sys
import re
import json
from pathlib import Path

# Set UTF-8
sys.stdout.reconfigure(encoding="utf-8")

def test_cafe_template():
    print("==================================================")
    print("  Elite Cafe Template Verification & Test Suite   ")
    print("==================================================")
    
    html_path = Path(r"M:\free_lancing\templates\cafe\index.html")
    css_path = Path(r"M:\free_lancing\templates\cafe\style.css")
    
    assert html_path.exists(), f"Missing {html_path}"
    assert css_path.exists(), f"Missing {css_path}"
    
    html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")
    
    print(f"✓ index.html size: {len(html)} bytes, lines: {len(html.splitlines())}")
    print(f"✓ style.css size: {len(css)} bytes, lines: {len(css.splitlines())}")
    
    # 1. Mandatory Placeholders Check
    mandatory_placeholders = [
        "{{BUSINESS_NAME}}",
        "{{TAGLINE}}",
        "{{HERO_IMAGE_URL}}",
        "{{ABOUT_TEXT}}",
        "{{ABOUT_IMAGE_URL}}",
        "{{DISH_1_NAME}}", "{{DISH_1_DESC}}", "{{DISH_1_PRICE}}",
        "{{DISH_2_NAME}}", "{{DISH_2_DESC}}", "{{DISH_2_PRICE}}",
        "{{DISH_3_NAME}}", "{{DISH_3_DESC}}", "{{DISH_3_PRICE}}",
        "{{DISH_4_NAME}}", "{{DISH_4_DESC}}", "{{DISH_4_PRICE}}",
        "{{DISH_5_NAME}}", "{{DISH_5_DESC}}", "{{DISH_5_PRICE}}",
        "{{DISH_6_NAME}}", "{{DISH_6_DESC}}", "{{DISH_6_PRICE}}",
        "{{GALLERY_1}}", "{{GALLERY_2}}", "{{GALLERY_3}}", "{{GALLERY_4}}",
        "{{STAR_RATING}}",
        "{{REVIEW_1_NAME}}", "{{REVIEW_1_TEXT}}",
        "{{REVIEW_2_NAME}}", "{{REVIEW_2_TEXT}}",
        "{{REVIEW_3_NAME}}", "{{REVIEW_3_TEXT}}",
        "{{PHONE}}", "{{EMAIL}}", "{{ADDRESS}}",
        "{{HOURS_WEEKDAY}}", "{{HOURS_WEEKEND}}", "{{MAP_EMBED_URL}}",
        "{{BRAND_NAME}}", "{{YEAR}}"
    ]
    
    found_placeholders = set(re.findall(r"(\{\{[A-Z0-9_]+\}\})", html))
    missing = [p for p in mandatory_placeholders if p not in found_placeholders]
    
    if missing:
        print(f"❌ FAILED: Missing mandatory placeholders: {missing}")
        sys.exit(1)
    else:
        print(f"✓ All {len(mandatory_placeholders)} mandatory placeholders verified in index.html!")
    
    # 2. Design Tokens and Typography Verification
    assert ("Playfair Display" in html or "Playfair+Display" in html) and "Outfit" in html, "Typography fonts must be loaded in index.html"
    assert "--font-heading: 'Playfair Display'" in css, "CSS must define Playfair Display heading font"
    assert "--font-body: 'Outfit'" in css, "CSS must define Outfit body font"
    assert "clamp(" in css, "CSS must implement fluid clamp typography"
    assert "prefers-reduced-motion" in css and "prefers-reduced-motion" in html, "Must support prefers-reduced-motion"
    print("✓ Design tokens, fluid clamp typography, and accessibility checks passed!")
    
    # 3. Interactive Component Verification
    assert 'data-filter="all"' in html, "Menu filtering 'all' tab present"
    assert 'data-filter="coffee"' in html, "Menu filtering 'coffee' tab present"
    assert 'data-filter="bakery"' in html, "Menu filtering 'bakery' tab present"
    assert 'data-filter="kitchen"' in html, "Menu filtering 'kitchen' tab present"
    assert 'id="reservation-form"' in html, "Reservation form present"
    assert 'id="mobile-toggle"' in html, "Mobile toggle button present"
    print("✓ Interactive components (filters, forms, mobile nav) verified!")
    
    # 4. Generate Integration Test
    sys.path.insert(0, r"M:\free_lancing\agents\site-generator")
    import generate
    
    sample_lead = {
        "name": "Madras Coffee House & Bistro",
        "discovery_category": "cafe",
        "primary_type": "cafe",
        "address": "45 Cathedral Road, Gopalapuram, Chennai, Tamil Nadu",
        "phone_national": "044 2811 5432",
        "phone_international": "+91 44 2811 5432",
        "rating": 4.8,
        "review_count": 520,
        "google_maps_url": "https://maps.google.com/?cid=12345"
    }
    
    sample_ai = {
        "tagline": "Traditional Degree Filter Coffee & Authentic South Indian Confectionery",
        "about_text": "Serving timeless South Indian filter coffee and freshly churned artisanal savories since generations. We honor heritage brewing with modern bistro elegance.",
        "services": [
            {"name": "Degree Filter Coffee", "description": "Authentic brass dabarah-tumbler brew with fresh farm milk."},
            {"name": "Artisan Ghee Podi Roast", "description": "Crisp golden crepe infused with freshly ground heirloom spices."},
            {"name": "Traditional Mysore Pak", "description": "Melt-in-the-mouth pure desi ghee artisanal sweet delicacy."},
            {"name": "Evening Tiffin Feasts", "description": "Handcrafted steamed delicacies served with stone-ground chutneys."}
        ],
        "meta_description": "Experience authentic degree filter coffee and artisanal tiffin delicacies at Madras Coffee House & Bistro in Chennai."
    }
    
    filled_html, filled_css = generate.fill_template(html, css, sample_lead, sample_ai)
    
    unfilled = re.findall(r"(\{\{[A-Z0-9_]+\}\})", filled_html)
    assert len(unfilled) == 0, f"Unfilled placeholders found: {set(unfilled)}"
    
    output_dir = Path(r"M:\free_lancing\output\sites\test-madras-coffee-house")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(filled_html, encoding="utf-8")
    (output_dir / "style.css").write_text(filled_css, encoding="utf-8")
    
    print(f"✓ Integration test passed! Sample site generated cleanly at:")
    print(f"  {output_dir / 'index.html'}")
    print("==================================================")
    print("  ALL AUDIT CHECKS PASSED (100% SUCCESS)          ")
    print("==================================================")

if __name__ == "__main__":
    test_cafe_template()
