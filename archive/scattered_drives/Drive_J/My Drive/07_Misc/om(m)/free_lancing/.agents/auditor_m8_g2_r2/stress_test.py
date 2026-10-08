import sys
import re
from pathlib import Path
from html.parser import HTMLParser

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "agents" / "site-generator"))
import generate

# Test 1: Indic scripts & Emojis
indic_lead = {
    'name': 'नमस्ते ढाबा ☕ ஸ்ரீ பாலாஜி டிரான்ஸ்போர்ட் 🚀 桜サロン',
    'discovery_category': 'cafe',
    'address': '123 மகாத்மா காந்தி சாலை, சென்னை, தமிழ்நாடு 600001',
    'phone_national': '+91 99887 76655',
    'rating': 4.9,
    'review_count': 100
}
indic_ai = {
    'tagline': 'சுவையான உணவு & சிறந்த சேவை 🌸 ₹150',
    'about_text': 'உங்களை அன்புடன் வரவேற்கிறோம். ശുദ്ധമായ ആഹാരം. আমাদের রেস্তোরাঁয় স্বাগতম।',
    'meta_description': 'Authentic multilingual cuisine ☕',
    'services': [{'name': 'ஸ்பெஷல் காபி ☕', 'description': 'மணக்கும் ஃபில்டர் காபி'}]
}

# Test 2: Extreme 500-char string
extreme_lead = {
    'name': 'A' * 300,
    'discovery_category': 'general',
    'address': 'B' * 500,
    'phone_national': '+91 99999 88888',
    'rating': 5.0,
    'review_count': 99999
}
extreme_ai = {
    'tagline': 'C' * 200,
    'about_text': 'D' * 2000,
    'meta_description': 'E' * 160,
    'services': [{'name': 'F' * 100, 'description': 'G' * 300}]
}

# Test 3: XSS & HTML characters
xss_lead = {
    'name': '<script>alert(1)</script> "Double Quotes" & \'Single\' <>&',
    'discovery_category': 'retail',
    'address': '<img src=x onerror=alert(1)>',
    'phone_national': '<b>+91 12345</b>',
    'rating': 0.0,
    'review_count': 0
}
xss_ai = {
    'tagline': '<b>Bold</b> & "Quoted"',
    'about_text': 'Test & verify <svg onload=alert(2)>',
    'meta_description': 'Test meta',
    'services': []
}

templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
print('=== ADVERSARIAL STRESS TESTING ===')
for cat in sorted([p.name for p in templates_dir.iterdir() if p.is_dir()]):
    html_raw, css_raw = generate.load_template(cat)
    
    for label, lead, ai in [('Indic/Unicode', indic_lead, indic_ai), ('Extreme Lengths', extreme_lead, extreme_ai), ('XSS/Entities', xss_lead, xss_ai)]:
        filled_html, filled_css = generate.fill_template(html_raw, css_raw, lead, ai)
        orphans = re.findall(r'\{\{[A-Z0-9_]+\}\}', filled_html)
        
        class V(HTMLParser): pass
        v = V()
        try:
            v.feed(filled_html)
            parse_ok = True
        except Exception as ex:
            parse_ok = False
            
        print(f'{cat:10} | {label:16} | HTML: {len(filled_html):6}B | Orphans: {len(orphans)} | HTML Parsed: {parse_ok}')
