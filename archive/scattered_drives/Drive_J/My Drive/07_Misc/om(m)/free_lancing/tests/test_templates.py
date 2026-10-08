#!/usr/bin/env python3
"""
===============================================================================
Comprehensive Unit & E2E Test Suite for Elite Website Templates
===============================================================================
Covers:
  - Tier 1: Feature & Placeholder Coverage across 7 Verticals (>=5 tests per section)
  - Tier 2: Boundary, Extreme Lengths, Unicode, Indic Scripts, XSS & Corner Cases
  - Tier 3: Design Tokens, CSS Architecture, WCAG 2.1 AA Contrast Math, Semantic HTML & Agent-as-Judge Aesthetics
  - Tier 4: Workload Simulation & Pipeline Integration (output/sites/)

Usage:
  python -m unittest discover -s tests
  python -m unittest tests/test_templates.py
  python tests/e2e_test_runner.py
"""

import html
import json
import math
import os
import re
import shutil
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

# Ensure standard output and error use UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── Path Setup ───────────────────────────────────────────────────────────────

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
SITE_GEN_DIR = PROJECT_ROOT / "agents" / "site-generator"
OUTPUT_SITES_DIR = PROJECT_ROOT / "output" / "sites"

# Ensure site-generator is importable
if str(SITE_GEN_DIR) not in sys.path:
    sys.path.insert(0, str(SITE_GEN_DIR))

try:
    import generate
except ImportError:
    generate = None


# ─── Constants & Categories ───────────────────────────────────────────────────

ALL_CATEGORIES = [
    "general",
    "cafe",
    "transport",
    "salon",
    "retail",
    "fitness",
    "clinic"
]

CORE_REQUIRED_PLACEHOLDERS = [
    "{{BUSINESS_NAME}}",
    "{{TAGLINE}}",
    "{{ABOUT_TEXT}}",
    "{{PHONE}}",
    "{{EMAIL}}",
    "{{ADDRESS}}",
    "{{MAP_EMBED_URL}}",
    "{{YEAR}}"
]

ORPHAN_REGEX = re.compile(r"\{\{[A-Z0-9_]+\}\}")


# ─── WCAG 2.1 Color & Contrast Mathematics ───────────────────────────────────

def parse_css_color_to_rgb(color_str: str) -> tuple[float, float, float] | None:
    """Parse hex (#rgb, #rrggbb, #rrggbbaa), rgb(), or rgba() into normalized RGB [0.0, 1.0]."""
    if not color_str:
        return None
    cleaned = color_str.strip().rstrip(";,").lower()

    named = {
        "white": (1.0, 1.0, 1.0),
        "black": (0.0, 0.0, 0.0),
        "transparent": (0.0, 0.0, 0.0)
    }
    if cleaned in named:
        return named[cleaned]

    hex_m = re.search(r"#[0-9a-fA-F]{3,8}", cleaned)
    if hex_m:
        hex_clean = hex_m.group(0).lstrip("#")
        if len(hex_clean) == 3:
            hex_clean = "".join([c * 2 for c in hex_clean])
        elif len(hex_clean) == 8:
            hex_clean = hex_clean[:6]
        elif len(hex_clean) == 4:
            hex_clean = "".join([c * 2 for c in hex_clean[:3]])
        if len(hex_clean) == 6:
            r = int(hex_clean[0:2], 16) / 255.0
            g = int(hex_clean[2:4], 16) / 255.0
            b = int(hex_clean[4:6], 16) / 255.0
            return (r, g, b)

    rgb_m = re.search(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", cleaned)
    if rgb_m:
        return (
            int(rgb_m.group(1)) / 255.0,
            int(rgb_m.group(2)) / 255.0,
            int(rgb_m.group(3)) / 255.0
        )

    return None


def calculate_relative_luminance(r: float, g: float, b: float) -> float:
    """Calculate WCAG 2.1 relative luminance for normalized RGB values: L = 0.2126*R + 0.7152*G + 0.0722*B."""
    def channel_linear(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = channel_linear(r)
    g_lin = channel_linear(g)
    b_lin = channel_linear(b)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(rgb1: tuple[float, float, float], rgb2: tuple[float, float, float]) -> float:
    """Calculate WCAG 2.1 contrast ratio between two normalized RGB tuples: (L1 + 0.05) / (L2 + 0.05)."""
    l1 = calculate_relative_luminance(*rgb1)
    l2 = calculate_relative_luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def extract_css_variables(css_content: str) -> dict[str, str]:
    """Extract CSS custom properties defined in :root after stripping comments."""
    clean_css = re.sub(r"/\*.*?\*/", "", css_content, flags=re.DOTALL)
    variables = {}
    root_blocks = re.findall(r":root\s*\{([^}]+)\}", clean_css, re.DOTALL)
    for block in root_blocks:
        declarations = block.split(";")
        for decl in declarations:
            decl = decl.strip()
            if ":" in decl:
                key, val = decl.split(":", 1)
                key = key.strip()
                val = val.strip()
                if key.startswith("--"):
                    variables[key] = val
    return variables


# ─── Mock Fixtures for All 7 Categories ───────────────────────────────────────

SAMPLE_LEADS: dict[str, dict] = {
    "general": {
        "name": "Apex Enterprise Solutions",
        "primary_type": "business consultancy",
        "discovery_category": "general",
        "address": "42 Cyber Hub, DLF Phase 2, Gurugram, Haryana 122002",
        "phone_national": "+91 98100 12345",
        "phone_international": "+919810012345",
        "google_maps_url": "https://maps.google.com/?cid=1001",
        "rating": 4.9,
        "review_count": 88,
    },
    "cafe": {
        "name": "Artisan Roast Cafe & Bakery",
        "primary_type": "cafe",
        "discovery_category": "cafe",
        "address": "15 Indiranagar 100ft Road, Bengaluru, Karnataka 560038",
        "phone_national": "+91 80 4123 4567",
        "phone_international": "+918041234567",
        "google_maps_url": "https://maps.google.com/?cid=1002",
        "rating": 4.8,
        "review_count": 142,
    },
    "transport": {
        "name": "SwiftRoute Logistics & Fleet",
        "primary_type": "transport agency",
        "discovery_category": "transport",
        "address": "88 Grand Southern Trunk Rd, Guindy, Chennai, Tamil Nadu 600032",
        "phone_national": "+91 44 2233 4455",
        "phone_international": "+914422334455",
        "google_maps_url": "https://maps.google.com/?cid=1003",
        "rating": 4.7,
        "review_count": 95,
    },
    "salon": {
        "name": "Luxe Aura Hair Studio & Spa",
        "primary_type": "salon",
        "discovery_category": "salon",
        "address": "24 Linking Road, Bandra West, Mumbai, Maharashtra 400050",
        "phone_national": "+91 22 6677 8899",
        "phone_international": "+912266778899",
        "google_maps_url": "https://maps.google.com/?cid=1004",
        "rating": 4.9,
        "review_count": 210,
    },
    "retail": {
        "name": "Velvet & Vine Boutique Store",
        "primary_type": "retail store",
        "discovery_category": "retail",
        "address": "104 Jubilee Hills, Road No 36, Hyderabad, Telangana 500033",
        "phone_national": "+91 40 2345 6789",
        "phone_international": "+914023456789",
        "google_maps_url": "https://maps.google.com/?cid=1005",
        "rating": 4.6,
        "review_count": 64,
    },
    "fitness": {
        "name": "IronPulse Crossfit & Gym",
        "primary_type": "fitness center",
        "discovery_category": "fitness",
        "address": "55 Park Street, Chowringhee, Kolkata, West Bengal 700016",
        "phone_national": "+91 33 2288 9900",
        "phone_international": "+913322889900",
        "google_maps_url": "https://maps.google.com/?cid=1006",
        "rating": 4.9,
        "review_count": 180,
    },
    "clinic": {
        "name": "Aegis Healthcare & Dental Clinic",
        "primary_type": "clinic",
        "discovery_category": "clinic",
        "address": "12 Mount Road, Anna Salai, Chennai, Tamil Nadu 600002",
        "phone_national": "+91 44 2855 1122",
        "phone_international": "+914428551122",
        "google_maps_url": "https://maps.google.com/?cid=1007",
        "rating": 4.9,
        "review_count": 320,
    },
}

SAMPLE_AI_CONTENT = {
    "tagline": "Excellence and Quality You Can Trust",
    "about_text": "We are a dedicated local service provider committed to delivering world-class customer satisfaction and top-tier services.",
    "meta_description": "Premier service provider offering exceptional quality, verified reviews, and prompt customer care.",
    "services": [
        {"name": "Premium Consulting", "description": "Tailored strategies designed for measurable impact and high growth."},
        {"name": "Comprehensive Solutions", "description": "End-to-end management ensuring maximum efficiency and reliability."},
        {"name": "Client Success Care", "description": "24/7 dedicated support and personalized assistance for all clients."},
        {"name": "Quality Assurance", "description": "Rigorous standards guaranteeing the finest results on every engagement."},
        {"name": "Modern Innovation", "description": "State of the art approaches leveraging modern industry techniques."},
        {"name": "Value Optimization", "description": "Cost-effective solutions without compromising on superior performance."},
    ],
}


def build_full_replacement_dict(lead: dict, ai_content: dict | None = None) -> dict[str, str]:
    """Construct complete placeholder replacement mapping for testing."""
    if ai_content is None:
        ai_content = SAMPLE_AI_CONTENT

    address_encoded = quote_plus(lead.get("address", ""))
    services = ai_content.get("services", [])
    service_icons = ["🚀", "⭐", "💎", "🎯", "✨", "🏆"]

    # Star rating calculation
    rating_val = float(lead.get("rating", 4.5))
    full_stars = int(rating_val)
    half_star = 1 if (rating_val - full_stars) >= 0.5 else 0
    empty_stars = max(0, 5 - full_stars - half_star)
    star_str = ("★" * full_stars) + ("★" if half_star else "") + ("☆" * empty_stars)

    replacements = {
        # Core Identity
        "{{BUSINESS_NAME}}": lead.get("name", "Business Name"),
        "{{TAGLINE}}": ai_content.get("tagline", "Your Trusted Local Business"),
        "{{ABOUT_TEXT}}": ai_content.get("about_text", "Welcome to our business."),
        "{{META_DESCRIPTION}}": ai_content.get("meta_description", "SEO description"),
        "{{BRAND_NAME}}": "AutoWeb",
        "{{YEAR}}": "2026",

        # Contact & Location
        "{{ADDRESS}}": lead.get("address", "123 Main Street"),
        "{{PHONE}}": lead.get("phone_national", "") or lead.get("phone_international", "") or "Contact Us",
        "{{EMAIL}}": f"info@{re.sub(r'[^a-zA-Z0-9]', '', lead.get('name', 'business')).lower()}.com",
        "{{GOOGLE_MAPS_URL}}": lead.get("google_maps_url", "#"),
        "{{MAP_EMBED_URL}}": f"https://maps.google.com/maps?q={address_encoded}&output=embed",
        "{{HOURS_WEEKDAY}}": "9:00 AM - 9:00 PM",
        "{{HOURS_WEEKEND}}": "10:00 AM - 8:00 PM",
        "{{HOURS_TEXT}}": "Mon - Sun: 9:00 AM - 10:00 PM",
        "{{BUSINESS_HOURS}}": "Mon - Fri: 9:00 AM - 9:00 PM | Sat - Sun: 10:00 AM - 8:00 PM",

        # Reputation & Social Proof
        "{{RATING}}": str(lead.get("rating", "4.8")),
        "{{REVIEW_COUNT}}": str(lead.get("review_count", "100")),
        "{{STAR_RATING}}": star_str,
        "{{REVIEW_1_NAME}}": "Arun Kumar",
        "{{REVIEW_1_TEXT}}": "Outstanding service and impeccable attention to detail. Highly recommended!",
        "{{REVIEW_1_RATING}}": "5",
        "{{REVIEW_2_NAME}}": "Priya Sharma",
        "{{REVIEW_2_TEXT}}": "Very professional staff and top quality results every single time.",
        "{{REVIEW_2_RATING}}": "5",
        "{{REVIEW_3_NAME}}": "Deepak Patel",
        "{{REVIEW_3_TEXT}}": "Reliable, transparent, and prompt. Extremely satisfied with the experience.",
        "{{REVIEW_3_RATING}}": "4",

        # Hero & Imagery
        "{{HERO_IMAGE_URL}}": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200",
        "{{HERO_IMAGE}}": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1200",
        "{{ABOUT_IMAGE_URL}}": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=800",
        "{{GALLERY_1}}": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=600",
        "{{GALLERY_2}}": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600",
        "{{GALLERY_3}}": "https://images.unsplash.com/photo-1521017432531-fbd92d768814?w=600",
        "{{GALLERY_4}}": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=600",

        # Services (1 through 6)
        "{{SERVICE_1_NAME}}": services[0]["name"] if len(services) > 0 else "Primary Service",
        "{{SERVICE_1_DESC}}": services[0]["description"] if len(services) > 0 else "Service description",
        "{{SERVICE_1_ICON}}": service_icons[0],
        "{{SERVICE_2_NAME}}": services[1]["name"] if len(services) > 1 else "Secondary Service",
        "{{SERVICE_2_DESC}}": services[1]["description"] if len(services) > 1 else "Service description",
        "{{SERVICE_2_ICON}}": service_icons[1],
        "{{SERVICE_3_NAME}}": services[2]["name"] if len(services) > 2 else "Specialized Care",
        "{{SERVICE_3_DESC}}": services[2]["description"] if len(services) > 2 else "Service description",
        "{{SERVICE_3_ICON}}": service_icons[2],
        "{{SERVICE_4_NAME}}": services[3]["name"] if len(services) > 3 else "Consultation",
        "{{SERVICE_4_DESC}}": services[3]["description"] if len(services) > 3 else "Service description",
        "{{SERVICE_4_ICON}}": service_icons[3],
        "{{SERVICE_5_NAME}}": services[4]["name"] if len(services) > 4 else "Express Delivery",
        "{{SERVICE_5_DESC}}": services[4]["description"] if len(services) > 4 else "Service description",
        "{{SERVICE_5_ICON}}": service_icons[4],
        "{{SERVICE_6_NAME}}": services[5]["name"] if len(services) > 5 else "Custom Strategy",
        "{{SERVICE_6_DESC}}": services[5]["description"] if len(services) > 5 else "Service description",
        "{{SERVICE_6_ICON}}": service_icons[5],

        # Category Specifics (Dining / Dishes)
        "{{DISH_1_NAME}}": "Signature Espresso Roast",
        "{{DISH_1_DESC}}": "Single-origin Arabica with notes of caramel and hazelnut",
        "{{DISH_1_PRICE}}": "₹220",
        "{{DISH_2_NAME}}": "Artisan Sourdough Toast",
        "{{DISH_2_DESC}}": "Handcrafted sourdough with organic avocado and microgreens",
        "{{DISH_2_PRICE}}": "₹280",
        "{{DISH_3_NAME}}": "Velvet Truffle Pasta",
        "{{DISH_3_DESC}}": "Fresh fettuccine tossed in black truffle cream sauce",
        "{{DISH_3_PRICE}}": "₹450",
        "{{DISH_4_NAME}}": "Rustic Margherita Pizza",
        "{{DISH_4_DESC}}": "San Marzano tomatoes, buffalo mozzarella, fresh basil",
        "{{DISH_4_PRICE}}": "₹390",
        "{{DISH_5_NAME}}": "Berry Cheesecake Tart",
        "{{DISH_5_DESC}}": "New York style cheesecake with fresh wild berry compote",
        "{{DISH_5_PRICE}}": "₹240",
        "{{DISH_6_NAME}}": "Cold Brew Infusion",
        "{{DISH_6_DESC}}": "Steeped for 18 hours for smooth, low-acidity flavor",
        "{{DISH_6_PRICE}}": "₹190",

        # Social links
        "{{FACEBOOK_URL}}": "https://facebook.com",
        "{{INSTAGRAM_URL}}": "https://instagram.com",
        "{{TWITTER_URL}}": "https://twitter.com",
    }
    return replacements


def perform_template_substitution(html_content: str, css_content: str, replacements: dict[str, str]) -> tuple[str, str]:
    """Substitute all dictionary keys in HTML and CSS content."""
    res_html = html_content
    res_css = css_content
    for k, v in replacements.items():
        res_html = res_html.replace(k, str(v))
        res_css = res_css.replace(k, str(v))
    return res_html, res_css


# ─── Simple HTML Syntax Validator ─────────────────────────────────────────────

class HTMLStructureValidator(HTMLParser):
    """Parses HTML to verify balanced structure and landmarks."""

    def __init__(self):
        super().__init__()
        self.tags_seen: set[str] = set()
        self.has_nav = False
        self.has_header = False
        self.has_footer = False
        self.has_title = False
        self.has_viewport = False
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        self.tags_seen.add(tag)
        if tag == "nav":
            self.has_nav = True
        elif tag == "header":
            self.has_header = True
        elif tag == "footer":
            self.has_footer = True
        elif tag == "title":
            self.has_title = True
        elif tag == "meta":
            attr_dict = dict(attrs)
            if attr_dict.get("name") == "viewport" and "width=device-width" in (attr_dict.get("content") or ""):
                self.has_viewport = True


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 1: Placeholder Coverage & Clean Substitution Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestTier1PlaceholderCoverage(unittest.TestCase):
    """Tier 1: Verifies template files exist and all placeholders are cleanly replaced."""

    def get_present_template_dirs(self) -> list[Path]:
        """Discover all subdirectories under templates/."""
        self.assertTrue(TEMPLATES_DIR.exists(), f"Templates directory not found: {TEMPLATES_DIR}")
        template_dirs = [p for p in TEMPLATES_DIR.iterdir() if p.is_dir()]
        self.assertGreater(len(template_dirs), 0, "No template directories found under templates/")
        return template_dirs

    def test_01_template_files_exist(self):
        """Verify each present template directory contains index.html and style.css with valid size."""
        for t_dir in self.get_present_template_dirs():
            with self.subTest(template=t_dir.name):
                index_path = t_dir / "index.html"
                css_path = t_dir / "style.css"
                self.assertTrue(index_path.exists(), f"Missing index.html in {t_dir.name}")
                self.assertTrue(css_path.exists(), f"Missing style.css in {t_dir.name}")
                self.assertGreater(index_path.stat().st_size, 200, f"index.html in {t_dir.name} is too small")
                self.assertGreater(css_path.stat().st_size, 200, f"style.css in {t_dir.name} is too small")

    def test_02_placeholder_discovery_and_inventory(self):
        """Verify templates contain essential core placeholders."""
        for t_dir in self.get_present_template_dirs():
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                for placeholder in CORE_REQUIRED_PLACEHOLDERS:
                    self.assertIn(
                        placeholder,
                        html_text,
                        f"Template '{t_dir.name}' is missing essential placeholder {placeholder}",
                    )
                # Verify services / menu items placeholder
                has_service = (
                    ("{{SERVICE_1_NAME}}" in html_text)
                    or ("{{SERVICES}}" in html_text)
                    or ("{{DISH_1_NAME}}" in html_text)
                )
                self.assertTrue(
                    has_service,
                    f"Template '{t_dir.name}' missing service or menu placeholders",
                )
                # Verify review text
                self.assertIn(
                    "{{REVIEW_1_TEXT}}",
                    html_text,
                    f"Template '{t_dir.name}' missing {{{{REVIEW_1_TEXT}}}}",
                )

    def test_03_clean_substitution_zero_orphans(self):
        """Verify that applying standard replacements leaves 0 orphaned {{...}} tags."""
        for t_dir in self.get_present_template_dirs():
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                css_text = (t_dir / "style.css").read_text(encoding="utf-8")

                category = t_dir.name if t_dir.name in SAMPLE_LEADS else "general"
                lead = SAMPLE_LEADS.get(category, SAMPLE_LEADS["general"])
                replacements = build_full_replacement_dict(lead)

                rendered_html, rendered_css = perform_template_substitution(html_text, css_text, replacements)

                html_orphans = ORPHAN_REGEX.findall(rendered_html)
                css_orphans = ORPHAN_REGEX.findall(rendered_css)

                self.assertEqual(
                    html_orphans, [],
                    f"Template '{t_dir.name}' has orphaned placeholders in index.html: {html_orphans}",
                )
                self.assertEqual(
                    css_orphans, [],
                    f"Template '{t_dir.name}' has orphaned placeholders in style.css: {css_orphans}",
                )

    def test_04_cafe_specific_placeholders(self):
        """Verify cafe template implements menu and dish placeholders cleanly."""
        cafe_dir = TEMPLATES_DIR / "cafe"
        if cafe_dir.exists():
            html_text = (cafe_dir / "index.html").read_text(encoding="utf-8")
            for i in range(1, 7):
                self.assertIn(f"{{{{DISH_{i}_NAME}}}}", html_text)
                self.assertIn(f"{{{{DISH_{i}_PRICE}}}}", html_text)

    def test_05_image_alt_tags_presence(self):
        """Verify all <img> tags across templates have non-empty alt attributes."""
        for t_dir in self.get_present_template_dirs():
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                soup = BeautifulSoup(html_text, "html.parser")
                images = soup.find_all("img")
                for img in images:
                    alt = img.get("alt")
                    self.assertIsNotNone(alt, f"{t_dir.name} contains <img> without alt attribute: {img}")
                    self.assertTrue(len(alt.strip()) > 0, f"{t_dir.name} contains <img> with empty alt attribute")


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 2: Boundary & Corner Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestTier2BoundaryAndCornerCases(unittest.TestCase):
    """Tier 2: Validates resilience against extreme lengths, unicode, XSS, and zero/empty values."""

    def setUp(self):
        self.template_dirs = [p for p in TEMPLATES_DIR.iterdir() if p.is_dir()]

    def test_01_extra_long_business_name_and_copy(self):
        """Test template substitution with a 250+ char business name and 1500+ char description."""
        extreme_lead = {
            "name": "Apex Global Multi-Disciplinary Advanced Enterprise Logistics, Infrastructure, Freight, Transportation & Supply Chain Solutions Private Limited & Co.",
            "primary_type": "enterprise",
            "address": "Tower 4, 15th Floor, Grand Horizon Business Park, Sector 62, Golf Course Extension Road, Phase 5, Gurugram, National Capital Region, Haryana 122001, India",
            "phone_national": "+91 124 4567890",
            "phone_international": "+911244567890",
            "google_maps_url": "https://maps.google.com/?q=long+address",
            "rating": 4.9,
            "review_count": 9999,
        }
        extreme_ai = {
            "tagline": "Empowering cross-border enterprises with resilient infrastructure, digital supply chains, AI-driven routing, and sustainable multi-modal transport networks across the globe.",
            "about_text": (
                "Established over three decades ago with a vision for transformative logistics, our organization "
                "has grown to become a recognized benchmark in supply chain excellence. Operating across continents, "
                "we deliver tailored enterprise solutions, comprehensive freight handling, and mission-critical "
                "procurement support. Our commitment to sustainable practices, technological innovation, and dedicated "
                "customer satisfaction has earned the trust of multinational conglomerates and regional leaders alike. "
            ) * 3,
            "meta_description": "Premier enterprise logistics and transportation solutions worldwide.",
            "services": [
                {"name": "Multi-Modal Freight Logistics & Global Air Cargo Routing", "description": "End-to-end containerized transport, customs clearance, and global real-time tracking."},
                {"name": "Temperature-Controlled Pharmaceutical Warehousing", "description": "Certified cold-chain storage maintaining stringent compliance standards."},
            ],
        }

        replacements = build_full_replacement_dict(extreme_lead, extreme_ai)

        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                css_text = (t_dir / "style.css").read_text(encoding="utf-8")
                rendered_html, _ = perform_template_substitution(html_text, css_text, replacements)

                self.assertIn(extreme_lead["name"], rendered_html)
                self.assertEqual(ORPHAN_REGEX.findall(rendered_html), [])

    def test_02_special_characters_and_html_entities(self):
        """Test resilience against quotes, ampersands, and script-like injection sequences."""
        special_lead = {
            "name": "Tom & Jerry's \"Fresh\" Delights <Bakery & Sweets>",
            "primary_type": "bakery",
            "address": "Shop #4 & 5, King's Cross <St. Avenue>, Mumbai",
            "phone_national": "+91 (022) 2345-6789",
            "phone_international": "+912223456789",
            "google_maps_url": "https://maps.google.com/?q=Tom+%26+Jerry",
            "rating": 5.0,
            "review_count": 50,
        }
        special_ai = {
            "tagline": "Freshly Baked Bread, Pastries & Desserts — 100% Organic & Pure!",
            "about_text": "We bake with love & passion! Our recipes use authentic ingredients: wheat, butter & natural spices. <script>console.log('safe');</script>",
            "meta_description": "Tom & Jerry's Bakery - Fresh breads & sweets.",
            "services": [
                {"name": "Cakes & Pastries <Special>", "description": "Custom birthday cakes & assorted dessert boxes for all events."},
            ],
        }
        replacements = build_full_replacement_dict(special_lead, special_ai)

        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                css_text = (t_dir / "style.css").read_text(encoding="utf-8")
                rendered_html, _ = perform_template_substitution(html_text, css_text, replacements)

                self.assertIn(special_lead["name"], rendered_html)
                self.assertEqual(ORPHAN_REGEX.findall(rendered_html), [])

    def test_03_unicode_multilingual_and_emojis(self):
        """Test non-Latin scripts (Devanagari, Tamil, Japanese), currency symbols (₹), and emojis."""
        unicode_lead = {
            "name": "नमस्ते कैफे ☕ சென்னை உணவகம் 🚀 桜サロン ✨ ₹250",
            "primary_type": "cafe",
            "address": "123 महात्मा गांधी मार्ग, சென்னை, 東京都渋谷区",
            "phone_national": "+91 99887 76655",
            "phone_international": "+919988776655",
            "google_maps_url": "https://maps.google.com/?q=नमस्ते",
            "rating": 4.9,
            "review_count": 777,
        }
        unicode_ai = {
            "tagline": "स्वादिष्ट भोजन மற்றும் சிறந்த சேவை 🌸 ₹100 Deals",
            "about_text": "हाम्रो कैफेमा तपाईंलाई स्वागत छ! உங்கள் வருகை நல்வரவாகுக. ようこそ！",
            "meta_description": "Multilingual cafe experience ☕✨",
            "services": [
                {"name": "विशेष कॉफी ☕ ₹150", "description": "ತಾಜಾ ಕಾಫಿ ಮತ್ತು ಚಹಾ"},
            ],
        }
        replacements = build_full_replacement_dict(unicode_lead, unicode_ai)

        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                css_text = (t_dir / "style.css").read_text(encoding="utf-8")
                rendered_html, _ = perform_template_substitution(html_text, css_text, replacements)

                self.assertIn("नमस्ते कैफे ☕", rendered_html)
                self.assertIn("சென்னை உணவகம் 🚀", rendered_html)
                self.assertIn("桜サロン ✨", rendered_html)
                self.assertIn("₹250", rendered_html)
                self.assertEqual(ORPHAN_REGEX.findall(rendered_html), [])

    def test_04_zero_ratings_and_empty_fields(self):
        """Test boundary conditions for 0.0 rating, 0 reviews, and empty optional contact fields."""
        zero_lead = {
            "name": "Brand New Startup Enterprise",
            "primary_type": "startup",
            "address": "",
            "phone_national": "",
            "phone_international": "",
            "google_maps_url": "",
            "rating": 0.0,
            "review_count": 0,
        }
        zero_ai = {
            "tagline": "",
            "about_text": "Welcome to our newly opened enterprise.",
            "meta_description": "",
            "services": [],
        }
        replacements = build_full_replacement_dict(zero_lead, zero_ai)

        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                css_text = (t_dir / "style.css").read_text(encoding="utf-8")
                rendered_html, _ = perform_template_substitution(html_text, css_text, replacements)

                self.assertIn(zero_lead["name"], rendered_html)
                self.assertEqual(ORPHAN_REGEX.findall(rendered_html), [])

    def test_05_valid_html_structure_after_substitution(self):
        """Verify HTML document structure remains valid after boundary substitution."""
        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                css_text = (t_dir / "style.css").read_text(encoding="utf-8")
                lead = SAMPLE_LEADS.get(t_dir.name, SAMPLE_LEADS["general"])
                replacements = build_full_replacement_dict(lead)
                rendered_html, _ = perform_template_substitution(html_text, css_text, replacements)

                parser = HTMLStructureValidator()
                parser.feed(rendered_html)

                self.assertIn("html", parser.tags_seen)
                self.assertIn("head", parser.tags_seen)
                self.assertIn("body", parser.tags_seen)
                self.assertTrue(parser.has_title, "HTML missing <title>")


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 3: Design Tokens & Accessibility (WCAG 2.1 AA)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTier3DesignTokensAndA11y(unittest.TestCase):
    """Tier 3: Validates semantic HTML, CSS tokens, responsive @media, glassmorphism, clamp/typography, and contrast."""

    def setUp(self):
        self.template_dirs = [p for p in TEMPLATES_DIR.iterdir() if p.is_dir()]

    def test_01_semantic_html_structure(self):
        """Verify semantic HTML5 landmark tags in index.html."""
        required_elements = ["<nav", "<header", "<section", "<footer", "<title>"]
        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                html_content = (t_dir / "index.html").read_text(encoding="utf-8").lower()
                for element in required_elements:
                    self.assertIn(
                        element,
                        html_content,
                        f"Template '{t_dir.name}' is missing semantic tag: {element}",
                    )

    def test_02_viewport_meta_tag(self):
        """Verify viewport meta tag for responsive mobile scaling."""
        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                html_content = (t_dir / "index.html").read_text(encoding="utf-8")
                self.assertRegex(
                    html_content,
                    r'<meta\s+name=["\']viewport["\']\s+content=["\'][^"\']*width=device-width[^"\']*["\']',
                    f"Template '{t_dir.name}' is missing valid viewport meta tag",
                )

    def test_03_css_custom_properties_in_root(self):
        """Verify :root block contains CSS custom property tokens (--bg, --text, --primary/accent, --glass)."""
        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                css_content = (t_dir / "style.css").read_text(encoding="utf-8")
                tokens = extract_css_variables(css_content)
                self.assertGreater(
                    len(tokens), 3,
                    f"Template '{t_dir.name}' must define CSS custom properties in :root",
                )
                token_keys = list(tokens.keys())
                has_bg = any("bg" in k or "background" in k for k in token_keys)
                has_text_or_color = any(
                    "text" in k or "color" in k or "accent" in k or "cream" in k or "gold" in k or "primary" in k
                    for k in token_keys
                )
                self.assertTrue(has_bg, f"Template '{t_dir.name}' missing background token in :root")
                self.assertTrue(has_text_or_color, f"Template '{t_dir.name}' missing text/color token in :root")

    def test_04_responsive_media_queries(self):
        """Verify style.css contains responsive @media rules."""
        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                css_content = (t_dir / "style.css").read_text(encoding="utf-8")
                self.assertIn(
                    "@media",
                    css_content,
                    f"Template '{t_dir.name}' missing responsive @media queries in style.css",
                )

    def test_05_modern_css_features_glassmorphism(self):
        """Verify style.css contains glassmorphism backdrop-filter rules."""
        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                css_content = (t_dir / "style.css").read_text(encoding="utf-8")
                has_backdrop = ("backdrop-filter" in css_content) or ("-webkit-backdrop-filter" in css_content)
                self.assertTrue(
                    has_backdrop,
                    f"Template '{t_dir.name}' missing backdrop-filter glassmorphism in style.css",
                )

    def test_06_typography_and_responsive_scaling(self):
        """Verify typography declarations and responsive font sizing in style.css."""
        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                css_content = (t_dir / "style.css").read_text(encoding="utf-8")
                self.assertIn("font-family", css_content, f"Template '{t_dir.name}' missing font-family in style.css")
                has_responsive_units = any(unit in css_content for unit in ["rem", "em", "clamp(", "vw"])
                self.assertTrue(
                    has_responsive_units,
                    f"Template '{t_dir.name}' missing modern responsive font sizing units (rem/clamp/vw)",
                )

    def test_07_wcag_color_contrast_ratios(self):
        """Verify color contrast ratios meet WCAG 2.1 AA (>= 4.5:1 for body text, >= 3.0:1 for accents/UI)."""
        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                css_content = (t_dir / "style.css").read_text(encoding="utf-8")
                tokens = extract_css_variables(css_content)

                # Locate background color
                bg_val = (
                    tokens.get("--bg-primary")
                    or tokens.get("--color-bg-dark")
                    or tokens.get("--bg-dark")
                    or tokens.get("--bg")
                    or "#0b0f19"
                )

                # Locate text color
                text_val = (
                    tokens.get("--text-primary")
                    or tokens.get("--color-cream")
                    or tokens.get("--text")
                    or "#f9fafb"
                )

                bg_rgb = parse_css_color_to_rgb(bg_val) or (0.05, 0.07, 0.1)
                text_rgb = parse_css_color_to_rgb(text_val) or (1.0, 1.0, 1.0)

                text_contrast = calculate_contrast_ratio(bg_rgb, text_rgb)

                self.assertGreaterEqual(
                    text_contrast, 4.5,
                    f"Template '{t_dir.name}' text contrast {text_contrast:.2f}:1 fails WCAG AA (>=4.5:1)",
                )

    def test_08_agent_as_judge_aesthetic_score(self):
        """Agent-as-Judge Heuristic: Verifies >=3 of 5 elite features (scroll reveals, glassmorphism, bento grid, hover transforms, typography hierarchy)."""
        for t_dir in self.template_dirs:
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                css_text = (t_dir / "style.css").read_text(encoding="utf-8")

                score = 0
                # 1. Scroll reveals / IntersectionObserver
                if "IntersectionObserver" in html_text or "reveal" in css_text or "fade-in" in css_text:
                    score += 1
                # 2. Glassmorphism
                if "backdrop-filter" in css_text or "glass" in css_text or "rgba(" in css_text:
                    score += 1
                # 3. Bento Grid / Multi-column Grid
                if "grid-template-columns" in css_text or "bento" in css_text or "repeat(" in css_text:
                    score += 1
                # 4. Hover Micro-interactions
                if ":hover" in css_text and ("transform" in css_text or "transition" in css_text):
                    score += 1
                # 5. Typography Hierarchy / Google Fonts
                if "fonts.googleapis.com" in html_text or "font-family" in css_text:
                    score += 1

                self.assertGreaterEqual(
                    score, 3,
                    f"Template '{t_dir.name}' failed Agent-as-Judge aesthetic criteria: scored {score}/5 (required >= 3)",
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 4: Workload Simulation & Pipeline Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestTier4WorkloadSimulation(unittest.TestCase):
    """Tier 4: Simulates full site generation across all 7 categories and validates output files in output/sites/."""

    def setUp(self):
        self.output_dir = OUTPUT_SITES_DIR
        os.makedirs(self.output_dir, exist_ok=True)
        self.created_dirs = []

    def tearDown(self):
        # Clean up any test-specific generated sites
        for d in self.created_dirs:
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)

    def test_01_workload_simulation_all_categories(self):
        """Simulate generation for all 7 categories and assert output files and markup integrity."""
        for category in ALL_CATEGORIES:
            with self.subTest(category=category):
                lead = SAMPLE_LEADS.get(category, SAMPLE_LEADS["general"])
                template_name = category if (TEMPLATES_DIR / category).exists() else "general"
                template_dir = TEMPLATES_DIR / template_name

                html_source = (template_dir / "index.html").read_text(encoding="utf-8")
                css_source = (template_dir / "style.css").read_text(encoding="utf-8")

                replacements = build_full_replacement_dict(lead)
                rendered_html, rendered_css = perform_template_substitution(html_source, css_source, replacements)

                safe_name = re.sub(r"[^\w\s-]", "", lead["name"]).strip()
                safe_name = re.sub(r"[-\s]+", "-", safe_name).lower()
                site_dir = self.output_dir / f"test-{safe_name}"
                os.makedirs(site_dir, exist_ok=True)
                self.created_dirs.append(str(site_dir))

                out_html_path = site_dir / "index.html"
                out_css_path = site_dir / "style.css"

                out_html_path.write_text(rendered_html, encoding="utf-8")
                out_css_path.write_text(rendered_css, encoding="utf-8")

                self.assertTrue(out_html_path.exists(), f"Output HTML not created for {category}")
                self.assertTrue(out_css_path.exists(), f"Output CSS not created for {category}")

                generated_html = out_html_path.read_text(encoding="utf-8")
                generated_css = out_css_path.read_text(encoding="utf-8")

                self.assertIn(lead["name"], generated_html)
                self.assertIn("<!DOCTYPE html>", generated_html)
                self.assertIn("</html>", generated_html)
                self.assertGreater(len(generated_html), 1000)
                self.assertGreater(len(generated_css), 500)

                orphans_html = ORPHAN_REGEX.findall(generated_html)
                orphans_css = ORPHAN_REGEX.findall(generated_css)

                self.assertEqual(orphans_html, [], f"Category '{category}' generated HTML has orphans: {orphans_html}")
                self.assertEqual(orphans_css, [], f"Category '{category}' generated CSS has orphans: {orphans_css}")

    def test_02_generate_py_integration(self):
        """Test direct integration with generate.py's fill_template function."""
        if generate is None or not hasattr(generate, "fill_template"):
            self.skipTest("generate.py not importable or missing fill_template")

        for t_dir in [p for p in TEMPLATES_DIR.iterdir() if p.is_dir()]:
            with self.subTest(template=t_dir.name):
                html_text = (t_dir / "index.html").read_text(encoding="utf-8")
                css_text = (t_dir / "style.css").read_text(encoding="utf-8")

                category = t_dir.name if t_dir.name in SAMPLE_LEADS else "general"
                lead = SAMPLE_LEADS.get(category, SAMPLE_LEADS["general"])

                filled_html, filled_css = generate.fill_template(html_text, css_text, lead, SAMPLE_AI_CONTENT)

                html_orphans = ORPHAN_REGEX.findall(filled_html)
                css_orphans = ORPHAN_REGEX.findall(filled_css)

                self.assertEqual(
                    html_orphans, [],
                    f"generate.py fill_template left orphans in '{t_dir.name}' index.html: {html_orphans}",
                )
                self.assertEqual(
                    css_orphans, [],
                    f"generate.py fill_template left orphans in '{t_dir.name}' style.css: {css_orphans}",
                )

    def test_03_generate_site_function_execution(self):
        """Test generate_site execution with mocked AI content to prevent network calls."""
        if generate is None or not hasattr(generate, "generate_site"):
            self.skipTest("generate.py not importable or missing generate_site")

        with patch("generate.generate_ai_content", return_value=SAMPLE_AI_CONTENT):
            for t_dir in [p for p in TEMPLATES_DIR.iterdir() if p.is_dir()]:
                with self.subTest(template=t_dir.name):
                    lead = SAMPLE_LEADS.get(t_dir.name, SAMPLE_LEADS["general"])
                    site_path = generate.generate_site(lead, template_name=t_dir.name)
                    self.assertIsNotNone(site_path)
                    self.created_dirs.append(str(site_path))
                    self.assertTrue(os.path.exists(site_path))
                    self.assertTrue((Path(site_path) / "index.html").exists())
                    self.assertTrue((Path(site_path) / "style.css").exists())


# ─── Main Execution Entrypoint ────────────────────────────────────────────────

if __name__ == "__main__":
    unittest.main(verbosity=2)
