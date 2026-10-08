#!/usr/bin/env python3
"""
AutoWeb Site Generator
========================
Generates static website previews by filling templates with business data + AI content.

Usage:
    python generate.py --lead "Business Name" --template general
    python generate.py --input ../output/scored_leads.json --top 5
    python generate.py --input ../output/scored_leads.json --all

Requires:
    - GEMINI_API_KEY in .env (for AI content generation)
    - Templates in ../templates/
"""

import argparse
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv

# Ensure standard output and error use UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# ─── Constants ───────────────────────────────────────────────────────────────

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent  # agents/site-generator -> agents -> free_lancing
TEMPLATES_DIR = PROJECT_DIR / "templates"
OUTPUT_DIR = PROJECT_DIR / "output" / "sites"
CONFIG_PATH = PROJECT_DIR / "agents" / "config.json"


# ─── AI Content Generation ──────────────────────────────────────────────────

def generate_ai_content(business_name: str, business_type: str, address: str,
                        rating: float, review_count: int, api_key: str) -> dict:
    """
    Use Gemini to generate website content for a business.
    Returns dict with: tagline, about_text, services (list), meta_description
    """
    prompt = f"""You are a professional copywriter creating website content for a local business in India.

Business Details:
- Name: {business_name}
- Type: {business_type}
- Location: {address}
- Google Rating: {rating}/5 ({review_count} reviews)

Generate the following in JSON format (no markdown, just raw JSON):
{{
    "tagline": "A short, catchy tagline (max 10 words)",
    "about_text": "A professional 'About Us' paragraph (60-80 words). Make it warm, trustworthy, and mention years of serving the community. Don't make up specific years or claims that can't be verified.",
    "services": [
        {{"name": "Service 1 Name", "description": "Brief description (15-20 words)"}},
        {{"name": "Service 2 Name", "description": "Brief description (15-20 words)"}},
        {{"name": "Service 3 Name", "description": "Brief description (15-20 words)"}},
        {{"name": "Service 4 Name", "description": "Brief description (15-20 words)"}}
    ],
    "meta_description": "SEO meta description for this business (150-160 characters)"
}}

Important:
- Use professional but friendly tone
- Mention the location naturally
- Keep it authentic — don't exaggerate
- Services should be realistic for a {business_type}
- Return ONLY valid JSON, no markdown formatting"""

    headers = {"Content-Type": "application/json"}
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.9,
            "maxOutputTokens": 1024,
        }
    }

    url = f"{GEMINI_API_URL}?key={api_key}"

    try:
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        # Clean up markdown code blocks if present
        text = re.sub(r'^```json\s*', '', text.strip())
        text = re.sub(r'\s*```$', '', text.strip())

        return json.loads(text)
    except Exception as e:
        print(f"  ⚠️  AI content generation failed: {e}")
        # Return fallback content
        return {
            "tagline": f"Your Trusted {business_type.title()} in {address.split(',')[0]}",
            "about_text": f"Welcome to {business_name}! We are a trusted {business_type} located in {address.split(',')[0]}. With a commitment to quality and customer satisfaction, we have been serving our community with dedication. Visit us today and experience the difference.",
            "services": [
                {"name": "Quality Service", "description": f"Professional {business_type} services tailored to your needs"},
                {"name": "Customer Care", "description": "Dedicated support and personalized attention for every customer"},
                {"name": "Expert Team", "description": "Skilled professionals committed to delivering excellence"},
                {"name": "Best Value", "description": "Competitive pricing without compromising on quality"},
            ],
            "meta_description": f"{business_name} - Your trusted {business_type} in {address.split(',')[0]}. Quality service, great reviews. Contact us today!"
        }


# ─── Template Processing ────────────────────────────────────────────────────

def get_template_for_category(category: str) -> str:
    """Determine which template to use based on business category."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
        mapping = config.get("template_mapping", {})
        return mapping.get(category, mapping.get("default", "general"))
    return "general"


def load_template(template_name: str) -> tuple[str, str]:
    """Load HTML and CSS template files. Returns (html_content, css_content)."""
    template_dir = TEMPLATES_DIR / template_name
    html_path = template_dir / "index.html"
    css_path = template_dir / "style.css"

    if not html_path.exists():
        print(f"  ❌ Template not found: {html_path}")
        sys.exit(1)

    html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    return html, css


def generate_star_rating_html(rating: float | int | str | None) -> str:
    """Generate HTML for star rating display with robust bounds and type checking."""
    if rating is None:
        rating = 4.5
    try:
        r = float(rating)
    except (ValueError, TypeError):
        r = 4.5

    # Handle float('nan') and float('inf') to match test expectations
    if math.isnan(r):
        raise ValueError("Cannot convert float NaN to rating")
    if math.isinf(r):
        raise OverflowError("Cannot convert float infinity to rating")

    r = max(0.0, min(5.0, r))
    full_stars = int(r)
    half_star = 1 if (r - full_stars) >= 0.5 else 0
    empty_stars = 5 - full_stars - half_star

    html = "★" * full_stars
    if half_star:
        html += "★"
    html += "☆" * max(0, empty_stars)

    return html


def fill_template(html: str, css: str, lead: dict | None, ai_content: dict | None) -> tuple[str, str]:
    """Fill template placeholders with business data and AI-generated content."""
    if lead is None:
        lead = {}
    if ai_content is None:
        ai_content = {}

    # Extract lead fields safely
    business_name = str(lead.get("name") or "Business Name")
    category = str(lead.get("discovery_category") or lead.get("primary_type") or "business")
    address = str(lead.get("address") or "")
    phone = str(lead.get("phone_national") or lead.get("phone_international") or "Contact us")
    maps_url = str(lead.get("google_maps_url") or "#")
    rating_raw = lead.get("rating")
    rating_val = str(rating_raw) if rating_raw is not None else "4.5"
    review_count_raw = lead.get("review_count")
    review_count_val = str(review_count_raw) if review_count_raw is not None else "0"

    # Clean email slug
    email_name = re.sub(r"[^a-zA-Z0-9]", "", business_name).lower() or "business"
    email = str(lead.get("email") or f"info@{email_name}.com")

    # Build Google Maps embed URL
    address_encoded = quote_plus(address)
    map_embed_fallback = f"https://maps.google.com/maps?q={address_encoded}&output=embed"

    # Extract AI content fields safely
    tagline = str(ai_content.get("tagline") or f"Your Trusted {category.title()} in {address.split(',')[0] if address else 'Your City'}")
    about_text = str(ai_content.get("about_text") or f"Welcome to {business_name}! We are a trusted {category} dedicated to providing the highest quality products and services to our community.")
    meta_description = str(ai_content.get("meta_description") or f"{business_name} - Your trusted {category} in {address.split(',')[0] if address else 'Your City'}. Quality service, verified reviews. Contact us today!")

    # Prepare services safely
    services_raw = ai_content.get("services")
    services = services_raw if isinstance(services_raw, list) else []
    service_icons = ["🚀", "⭐", "💎", "🎯", "✨", "🏆"]

    def get_service_item(idx: int, fallback_name: str, fallback_desc: str) -> tuple[str, str]:
        if idx < len(services):
            item = services[idx]
            if isinstance(item, dict):
                s_name = item.get("name") or fallback_name
                s_desc = item.get("description") or fallback_desc
                return str(s_name), str(s_desc)
            elif item is not None:
                return str(item), fallback_desc
        return fallback_name, fallback_desc

    s1_name, s1_desc = get_service_item(0, "Our Services", "Professional services tailored to your needs")
    s2_name, s2_desc = get_service_item(1, "Customer Care", "Dedicated support and personalized attention")
    s3_name, s3_desc = get_service_item(2, "Quality Assured", "Top quality standards guaranteed")
    s4_name, s4_desc = get_service_item(3, "Best Value", "Competitive pricing without compromising on quality")
    s5_name, s5_desc = get_service_item(4, "Specialized Care", "Tailored solutions for your specific needs")
    s6_name, s6_desc = get_service_item(5, "Expert Consultation", "Professional guidance and support")

    # Star rating HTML
    star_rating_html = generate_star_rating_html(rating_raw)

    primary_type_encoded = quote_plus(str(lead.get("primary_type") or category))

    # Build replacements dictionary
    replacements = {
        # Business info
        "{{BUSINESS_NAME}}": business_name,
        "{{TAGLINE}}": tagline,
        "{{ABOUT_TEXT}}": about_text,
        "{{ADDRESS}}": address,
        "{{PHONE}}": phone,
        "{{EMAIL}}": email,
        "{{GOOGLE_MAPS_URL}}": maps_url,
        "{{MAP_EMBED_URL}}": map_embed_fallback,
        "{{META_DESCRIPTION}}": meta_description,
        "{{RATING}}": rating_val,
        "{{REVIEW_COUNT}}": review_count_val,
        "{{STAR_RATING}}": star_rating_html,

        # Hero image
        "{{HERO_IMAGE_URL}}": f"https://source.unsplash.com/1200x600/?{primary_type_encoded}",
        "{{HERO_IMAGE}}": f"https://source.unsplash.com/1200x600/?{primary_type_encoded}",

        # Services
        "{{SERVICE_1_NAME}}": s1_name,
        "{{SERVICE_1_DESC}}": s1_desc,
        "{{SERVICE_1_ICON}}": service_icons[0],
        "{{SERVICE_2_NAME}}": s2_name,
        "{{SERVICE_2_DESC}}": s2_desc,
        "{{SERVICE_2_ICON}}": service_icons[1],
        "{{SERVICE_3_NAME}}": s3_name,
        "{{SERVICE_3_DESC}}": s3_desc,
        "{{SERVICE_3_ICON}}": service_icons[2],
        "{{SERVICE_4_NAME}}": s4_name,
        "{{SERVICE_4_DESC}}": s4_desc,
        "{{SERVICE_4_ICON}}": service_icons[3],
        "{{SERVICE_5_NAME}}": s5_name,
        "{{SERVICE_5_DESC}}": s5_desc,
        "{{SERVICE_5_ICON}}": service_icons[4],
        "{{SERVICE_6_NAME}}": s6_name,
        "{{SERVICE_6_DESC}}": s6_desc,
        "{{SERVICE_6_ICON}}": service_icons[5],

        # Reviews
        "{{REVIEW_1_NAME}}": "Happy Customer",
        "{{REVIEW_1_TEXT}}": "Excellent service! Highly recommended for everyone.",
        "{{REVIEW_1_RATING}}": "5",
        "{{REVIEW_2_NAME}}": "Satisfied Client",
        "{{REVIEW_2_TEXT}}": "Great experience, very professional and friendly staff.",
        "{{REVIEW_2_RATING}}": "5",
        "{{REVIEW_3_NAME}}": "Regular Visitor",
        "{{REVIEW_3_TEXT}}": "Been coming here for years. Consistent quality every time.",
        "{{REVIEW_3_RATING}}": "4",

        # Gallery
        "{{GALLERY_1}}": f"https://source.unsplash.com/400x300/?{primary_type_encoded},1",
        "{{GALLERY_2}}": f"https://source.unsplash.com/400x300/?{primary_type_encoded},2",
        "{{GALLERY_3}}": f"https://source.unsplash.com/400x300/?{primary_type_encoded},3",
        "{{GALLERY_4}}": f"https://source.unsplash.com/400x300/?{primary_type_encoded},4",

        # Cafe-specific
        "{{DISH_1_NAME}}": "Signature Special",
        "{{DISH_1_DESC}}": "Our most popular item, made with love",
        "{{DISH_1_PRICE}}": "₹150",
        "{{DISH_2_NAME}}": "Classic Favorite",
        "{{DISH_2_DESC}}": "A timeless classic loved by everyone",
        "{{DISH_2_PRICE}}": "₹120",
        "{{DISH_3_NAME}}": "Chef's Choice",
        "{{DISH_3_DESC}}": "Today's special creation",
        "{{DISH_3_PRICE}}": "₹200",
        "{{DISH_4_NAME}}": "Premium Selection",
        "{{DISH_4_DESC}}": "Our finest offering",
        "{{DISH_4_PRICE}}": "₹250",
        "{{DISH_5_NAME}}": "Light Bite",
        "{{DISH_5_DESC}}": "Perfect for a quick snack",
        "{{DISH_5_PRICE}}": "₹80",
        "{{DISH_6_NAME}}": "Refreshing Drink",
        "{{DISH_6_DESC}}": "Cool and refreshing beverages",
        "{{DISH_6_PRICE}}": "₹60",

        # Business hours
        "{{HOURS_WEEKDAY}}": "9:00 AM - 9:00 PM",
        "{{HOURS_WEEKEND}}": "10:00 AM - 8:00 PM",
        "{{HOURS_TEXT}}": "Mon - Sun: 9:00 AM - 10:00 PM",
        "{{BUSINESS_HOURS}}": "Mon - Fri: 9:00 AM - 9:00 PM | Sat - Sun: 10:00 AM - 8:00 PM",

        # Additional Imagery & Social
        "{{ABOUT_IMAGE_URL}}": f"https://source.unsplash.com/600x400/?{primary_type_encoded},about",
        "{{FACEBOOK_URL}}": "#",
        "{{INSTAGRAM_URL}}": "#",
        "{{TWITTER_URL}}": "#",

        # Brand
        "{{BRAND_NAME}}": os.getenv("BRAND_NAME", "AutoWeb"),
        "{{YEAR}}": "2026",
    }

    # Apply all replacements
    for placeholder, value in replacements.items():
        val_str = str(value if value is not None else "")
        html = html.replace(placeholder, val_str)
        css = css.replace(placeholder, val_str)

    return html, css


def generate_site(lead: dict | None, template_name: str | None = None) -> str | None:
    """Generate a complete static site for a single lead. Returns output path."""
    if lead is None:
        lead = {}

    business_name = lead.get("name") or "Unknown"
    category = lead.get("discovery_category") or lead.get("primary_type") or "business"
    address = lead.get("address") or ""
    rating = lead.get("rating") if lead.get("rating") is not None else 0
    review_count = lead.get("review_count") if lead.get("review_count") is not None else 0

    print(f"\n🎨 Generating site for: {business_name}")
    print(f"   Category: {category} | Rating: {rating}⭐ ({review_count} reviews)")

    # Determine template
    if not template_name:
        template_name = get_template_for_category(category)
    print(f"   Template: {template_name}")

    # Load template
    html, css = load_template(template_name)

    # Generate AI content
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key and gemini_key != "your_gemini_api_key_here":
        print("   🤖 Generating AI content...")
        ai_content = generate_ai_content(business_name, category, address, rating, review_count, gemini_key)
    else:
        print("   ⚠️  No GEMINI_API_KEY — using fallback content")
        ai_content = generate_ai_content(business_name, category, address, rating, review_count, "")

    # Fill template
    html_filled, css_filled = fill_template(html, css, lead, ai_content)

    # Create output directory
    safe_name = re.sub(r'[^\w\s-]', '', str(business_name)).strip()
    safe_name = re.sub(r'[-\s]+', '-', safe_name).lower()
    if not safe_name:
        safe_name = "unnamed-business"

    site_dir = OUTPUT_DIR / safe_name

    os.makedirs(site_dir, exist_ok=True)

    # Write files
    (site_dir / "index.html").write_text(html_filled, encoding="utf-8")
    (site_dir / "style.css").write_text(css_filled, encoding="utf-8")

    print(f"   ✅ Site generated: {site_dir}")
    print(f"   📂 Open: file:///{site_dir / 'index.html'}")

    return str(site_dir)


# ─── CLI Interface ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🎨 AutoWeb Site Generator — Create stunning website previews",
    )
    parser.add_argument("--input", type=str, help="Path to scored_leads.json or leads.json")
    parser.add_argument("--lead", type=str, help="Generate for a specific lead by name")
    parser.add_argument("--template", type=str, help="Force a specific template (general, cafe, etc.)")
    parser.add_argument("--top", type=int, help="Generate for top N leads only")
    parser.add_argument("--all", action="store_true", help="Generate for all leads")
    parser.add_argument("--hot-only", action="store_true", help="Generate only for HOT leads")

    args = parser.parse_args()

    # Default paths
    default_input = PROJECT_DIR / "output" / "scored_leads.json"
    if not default_input.exists():
        default_input = PROJECT_DIR / "output" / "leads.json"

    input_path = args.input or str(default_input)

    if not os.path.exists(input_path):
        print(f"❌ No leads file found at {input_path}")
        print("   Run discover.py and score.py first.")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        leads = json.load(f)

    if not leads:
        print("⚠️  No leads to process.")
        sys.exit(0)

    # Filter leads
    if args.lead:
        leads = [l for l in leads if args.lead.lower() in l.get("name", "").lower()]
        if not leads:
            print(f"❌ No lead found matching '{args.lead}'")
            sys.exit(1)
    elif args.hot_only:
        leads = [l for l in leads if "HOT" in l.get("score_label", "")]
        print(f"🔥 Processing {len(leads)} HOT leads only")
    elif args.top:
        leads = leads[:args.top]
        print(f"📋 Processing top {len(leads)} leads")
    elif not args.all:
        # Default: process top 5
        leads = leads[:5]
        print(f"📋 Processing top {len(leads)} leads (use --all for all, --top N for specific count)")

    # Generate sites
    generated = []
    for lead in leads:
        site_path = generate_site(lead, args.template)
        if site_path:
            generated.append({"name": lead["name"], "path": site_path})
        time.sleep(1)  # Rate limit for AI API

    # Summary
    print(f"\n{'='*60}")
    print(f"✅ Generated {len(generated)} website previews")
    print(f"{'='*60}")
    for site in generated:
        print(f"  📁 {site['name']}: {site['path']}")


if __name__ == "__main__":
    main()
