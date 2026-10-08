#!/usr/bin/env python3
"""
===============================================================================
Adversarial Stress Test Harness for AutoWeb Template Suite & generate.py
===============================================================================
Empirical Challenger Test Suite:
  1. Vector 1: Extreme Length Strings (1,000 to 10,000+ chars)
  2. Vector 2: Severe XSS Payloads, HTML Injections & Entity Escaping
  3. Vector 3: Missing, None, Empty & Corrupted Dictionaries/Keys
  4. Vector 4: Negative, Zero, Float Overflows, NaN, Inf & Type Mismatches
  5. Vector 5: Non-Latin Scripts (Indic, RTL Arabic/Hebrew, CJK, Emojis, Control Chars)
  6. Vector 6: Path Traversal, Windows Reserved Names & Empty Slugs
  7. Vector 7: High-Throughput Burst Stress Workload (100+ generated sites)
"""

import html
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
import traceback
import unittest
from unittest.mock import patch
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

# Paths
TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
SITE_GEN_DIR = PROJECT_ROOT / "agents" / "site-generator"

if str(SITE_GEN_DIR) not in sys.path:
    sys.path.insert(0, str(SITE_GEN_DIR))

import generate

ALL_TEMPLATES = ["general", "cafe", "transport", "salon", "retail", "fitness", "clinic"]


class TestAdversarialStress(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="autoweb_stress_")
        self.old_output_dir = generate.OUTPUT_DIR
        generate.OUTPUT_DIR = Path(self.temp_dir)

    def tearDown(self):
        generate.OUTPUT_DIR = self.old_output_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # VECTOR 1: Extreme Length Strings
    # -------------------------------------------------------------------------
    def test_v1_extreme_length_strings(self):
        """Test extreme length inputs (1k-10k chars) across all 7 templates."""
        huge_name = "MegaCorp " + ("International Enterprise Solutions " * 100) # ~3500 chars
        huge_tagline = "We provide " + ("hyper-optimized scalable multi-cloud infrastructure " * 50) # ~2500 chars
        huge_about = "Our history spans decades. " + ("We deliver excellence every single day across all continents. " * 80) # ~5000 chars
        huge_address = "Suite 9000, Tower A, " + ("Technology Park, Sector 62, Innovation Hub, " * 40) + "Bangalore, India" # ~2000 chars
        huge_review = "Outstanding quality! " + ("I have never seen such a remarkable service in my entire life. " * 30) # ~2000 chars

        lead = {
            "name": huge_name,
            "primary_type": "consulting",
            "address": huge_address,
            "rating": 4.9,
            "review_count": 99999,
            "phone_national": "+91 98765 43210",
            "phone_international": "+91 98765 43210",
            "google_maps_url": "https://maps.google.com/?q=" + quote_plus(huge_address[:200])
        }

        ai_content = {
            "tagline": huge_tagline,
            "about_text": huge_about,
            "services": [
                {"name": f"Service {i} " + ("Super Elite " * 20), "description": f"Description {i} " + ("Details and specifications " * 40)}
                for i in range(1, 7)
            ],
            "meta_description": "Meta " + ("SEO summary " * 50)
        }

        for template in ALL_TEMPLATES:
            with self.subTest(template=template):
                html_raw, css_raw = generate.load_template(template)
                html_filled, css_filled = generate.fill_template(html_raw, css_raw, lead, ai_content)

                # Check that template substitutions succeeded without unreplaced core tokens
                self.assertNotIn("{{BUSINESS_NAME}}", html_filled)
                self.assertNotIn("{{TAGLINE}}", html_filled)
                self.assertNotIn("{{ABOUT_TEXT}}", html_filled)
                self.assertNotIn("{{ADDRESS}}", html_filled)

                # Verify document length is appropriately large and not empty
                self.assertGreater(len(html_filled), 10000)

                # Verify HTML parses
                soup = BeautifulSoup(html_filled, "html.parser")
                self.assertIsNotNone(soup.find("title"))
                self.assertIsNotNone(soup.find("body"))

    # -------------------------------------------------------------------------
    # VECTOR 2: Severe XSS & HTML Payloads
    # -------------------------------------------------------------------------
    def test_v2_xss_and_html_payloads(self):
        """Test behavior when malicious XSS and malformed HTML payloads are provided."""
        xss_payloads = [
            "<script id=\"xss\">alert('XSS_NAME')</script>",
            "<img src=x onerror=alert('XSS_IMG')>",
            "\"><svg/onload=alert('XSS_SVG')>",
            "<iframe src='javascript:alert(1)'></iframe>",
            "<b>Bold</b><i>Italic</i><h1>Unclosed Header",
            "</div></div><!-- Injected Comment -->",
            "'; DROP TABLE users; --",
            "{{TEMPLATE_INJECTION_ATTEMPT}}",
            "<a href=\"javascript:alert('XSS_LINK')\">Click Here</a>",
            "& < > \" ' ` = /"
        ]

        for i, payload in enumerate(xss_payloads):
            lead = {
                "name": f"Business_{i} " + payload,
                "primary_type": "restaurant",
                "address": "123 Main St " + payload,
                "rating": 5.0,
                "review_count": 100,
                "phone_national": "+91 98765 43210 " + payload,
                "google_maps_url": "https://maps.google.com/?q=" + quote_plus(payload)
            }
            ai_content = {
                "tagline": "Tagline " + payload,
                "about_text": "About us " + payload,
                "services": [
                    {"name": f"Service {j} " + payload, "description": f"Desc {j} " + payload}
                    for j in range(1, 7)
                ],
                "meta_description": "Meta " + payload
            }

            for template in ALL_TEMPLATES:
                with self.subTest(template=template, payload_idx=i):
                    html_raw, css_raw = generate.load_template(template)
                    html_filled, css_filled = generate.fill_template(html_raw, css_raw, lead, ai_content)

                    # Verify template doesn't crash on string substitution
                    self.assertIsInstance(html_filled, str)
                    self.assertIsInstance(css_filled, str)
                    self.assertGreater(len(html_filled), 100)

                    # Note: raw tags are substituted directly into template
                    # BeautifulSoup parses the resulting tree
                    soup = BeautifulSoup(html_filled, "html.parser")
                    self.assertIsNotNone(soup.body)

    # -------------------------------------------------------------------------
    # VECTOR 3: Missing, None, Empty & Corrupted Dictionaries
    # -------------------------------------------------------------------------
    def test_v3_missing_and_none_fields_resilience(self):
        """Audit resilience against missing keys and identify exact unhandled type crashes."""
        # 1. Missing keys with default fallback dicts (well-formed defaults)
        safe_lead = {"name": "Safe Business"}
        safe_ai = {"services": []}

        for template in ALL_TEMPLATES:
            with self.subTest(template=template):
                html_raw, css_raw = generate.load_template(template)
                html_filled, css_filled = generate.fill_template(html_raw, css_raw, safe_lead, safe_ai)
                self.assertIsInstance(html_filled, str)
                self.assertNotIn("{{BUSINESS_NAME}}", html_filled)

        # 2. Corrupted data structures that trigger runtime exceptions
        vulnerabilities = []

        test_leads = [
            ("lead_address_is_None", {"address": None}, {"services": []}),
            ("lead_name_is_None", {"name": None}, {"services": []}),
            ("lead_rating_is_None", {"rating": None}, {"services": []}),
            ("lead_primary_type_is_None", {"primary_type": None}, {"services": []}),
            ("ai_content_services_is_None", {}, {"services": None}),
            ("services_element_is_None", {}, {"services": [None]}),
            ("services_element_missing_name_key", {}, {"services": [{"description": "Desc"}]}),
        ]

        html_raw, css_raw = generate.load_template("general")
        for test_id, lead, ai_content in test_leads:
            try:
                generate.fill_template(html_raw, css_raw, lead, ai_content)
            except Exception as e:
                vulnerabilities.append({
                    "test_id": test_id,
                    "exception_type": type(e).__name__,
                    "error_message": str(e)
                })

        # Assert that all edge cases are handled gracefully with 0 vulnerabilities
        self.assertEqual(len(vulnerabilities), 0, f"Expected 0 vulnerabilities after remediation, found: {vulnerabilities}")

    # -------------------------------------------------------------------------
    # VECTOR 4: Negative, Zero, Overflow Numbers & Extreme Floats
    # -------------------------------------------------------------------------
    def test_v4_number_extremes(self):
        """Test negative numbers, zero, extreme floats, nan, inf, and large numbers."""
        test_ratings = [-10.0, -1.0, 0.0, 0.0001, 2.5, 4.9999, 5.0, 10.0, 100.0, 1e6]
        
        for rating in test_ratings:
            lead = {
                "name": f"Test Rating {rating}",
                "rating": rating,
                "review_count": -50 if rating < 0 else 1000000000,
                "address": "123 Star Way, Galaxy City"
            }
            ai_content = {"services": []}

            for template in ALL_TEMPLATES:
                with self.subTest(template=template, rating=rating):
                    html_raw, css_raw = generate.load_template(template)
                    html_filled, css_filled = generate.fill_template(html_raw, css_raw, lead, ai_content)
                    self.assertIsInstance(html_filled, str)
                    star_html = generate.generate_star_rating_html(rating)
                    self.assertIsInstance(star_html, str)

        # Extreme non-number types: NaN and Inf
        with self.assertRaises(ValueError):
            generate.generate_star_rating_html(float("nan"))
        with self.assertRaises(OverflowError):
            generate.generate_star_rating_html(float("inf"))

    # -------------------------------------------------------------------------
    # VECTOR 5: Non-Latin Scripts, RTL, Complex Unicode & Control Characters
    # -------------------------------------------------------------------------
    def test_v5_multilingual_unicode_rtl(self):
        """Test Devanagari, Tamil, Arabic (RTL), Hebrew, CJK, Cyrillic, Emojis, and Control Chars."""
        multilingual_cases = [
            {
                "lang": "Hindi_Devanagari",
                "name": "शाही चाय कैफ़े और बेकरी — नमस्ते दुनिया",
                "tagline": "स्वादिष्ट भोजन और उत्तम कॉफ़ी",
                "about": "हम 2005 से अपने समुदाय की सेवा कर रहे हैं। हमारे यहाँ ताज़ा केक और कॉफ़ी मिलती है।",
                "address": "दुकान संख्या ४५, एम जी रोड, नई दिल्ली, भारत"
            },
            {
                "lang": "Tamil",
                "name": "சென்னை ஸ்பெஷல் காபி மற்றும் சிற்றுண்டி",
                "tagline": "பாரம்பரிய சுவை மற்றும் தரம்",
                "about": "நாங்கள் மிகச்சிறந்த சுவையான காபி மற்றும் உணவுகளை வழங்குகிறோம்.",
                "address": "123 அண்ணா சாலை, சென்னை, தமிழ்நாடு"
            },
            {
                "lang": "Arabic_RTL",
                "name": "مقهى ومخبز النخبة الذهبية",
                "tagline": "أفضل قهوة وأشهى المأكولات في المدينة",
                "about": "نحن نقدم أجود أنواع البن والمخبوزات الطازجة يومياً لخدمتكم بأعلى معايير الجودة.",
                "address": "شارع الملك فهد، الرياض، المملكة العربية السعودية"
            },
            {
                "lang": "Hebrew_RTL",
                "name": "קפה ומאפיית הבוטיק",
                "tagline": "הקפה הטוב ביותר בעיר",
                "about": "אנו מגישים קפה איכותי ומאפים טריים מדי יום באווירה חמה ומזמינה.",
                "address": "רחוב דיזנגוף 100, תל אביב, ישראל"
            },
            {
                "lang": "Japanese_CJK",
                "name": "東京ロースタリー＆ベーカリーカフェ",
                "tagline": "最高峰の焙煎珈琲と職人仕込みの焼きたてパン",
                "about": "厳選された豆と伝統の技術でおもてなしいたします。心地よい時間をお過ごしください。",
                "address": "東京都渋谷区神宮前1-2-3"
            },
            {
                "lang": "Emojis_SpecialChars",
                "name": "⚡🔥 The Ultimate ☕ Cafe & 🥐 Bakery 🌟✨💎",
                "tagline": "🚀 Fast & Delicious 🍕🍔🍟 | 💯% Organic 🌿",
                "about": "🎉 Best spot in town! ⭐⭐⭐⭐⭐ Loved by millions 💖 Check our reviews 📈",
                "address": "📍 404 Nebula Lane 🛸 Cyberspace 🌐"
            },
            {
                "lang": "ControlChars_NullBytes",
                "name": "Business\tWith\nNewlines\rAnd\x1b[31mANSI\x1b[0m",
                "tagline": "Clean\x00Null\x07Bell\x08Backspace",
                "about": "Text with \t\n\r and unicode \u200b\u200c\u200d\ufeff zero-width chars.",
                "address": "Road #1, \x1fUnit 2"
            }
        ]

        for case in multilingual_cases:
            lead = {
                "name": case["name"],
                "primary_type": "cafe",
                "address": case["address"],
                "rating": 4.8,
                "review_count": 250,
                "phone_national": "+91 99887 76655",
                "google_maps_url": "https://maps.google.com/?q=" + quote_plus(case["address"])
            }
            ai_content = {
                "tagline": case["tagline"],
                "about_text": case["about"],
                "services": [
                    {"name": f"Service {i} — " + case["name"][:15], "description": case["tagline"]}
                    for i in range(1, 7)
                ],
                "meta_description": case["about"][:150]
            }

            for template in ALL_TEMPLATES:
                with self.subTest(template=template, lang=case["lang"]):
                    html_raw, css_raw = generate.load_template(template)
                    html_filled, css_filled = generate.fill_template(html_raw, css_raw, lead, ai_content)

                    self.assertIsInstance(html_filled, str)
                    self.assertIsInstance(css_filled, str)

                    # Ensure UTF-8 output writes and reads back cleanly without encoding errors
                    out_html_path = Path(self.temp_dir) / f"test_{template}_{case['lang']}.html"
                    out_html_path.write_text(html_filled, encoding="utf-8")
                    read_back = out_html_path.read_text(encoding="utf-8")
                    self.assertEqual(len(read_back), len(html_filled))

    # -------------------------------------------------------------------------
    # VECTOR 6: Path Traversal, Slug Security & Windows Reserved Names
    # -------------------------------------------------------------------------
    def test_v6_slug_generation_and_path_security(self):
        """Test path traversal names, Windows reserved names, and all-symbol names in generate_site."""
        mock_ai = {
            "tagline": "Test Tagline",
            "about_text": "Test About",
            "services": [{"name": "S", "description": "D"}] * 6,
            "meta_description": "Test Meta"
        }

        adversarial_names = [
            ("../../../etc/passwd", "Path traversal sanitized to safe slug"),
            ("..\\..\\..\\Windows\\System32", "Windows path traversal sanitized"),
            ("CON", "Windows reserved device CON"),
            ("PRN", "Windows reserved device PRN"),
            ("AUX", "Windows reserved device AUX"),
            ("COM1", "Windows reserved device COM1"),
            ("LPT1", "Windows reserved device LPT1"),
            ("!!!@@@###$$$%%%^^^&&&***()", "All symbols produce empty slug"),
            ("   ", "Pure whitespace produces empty slug"),
            ("---___---", "Hyphens and underscores slug"),
            ("Lead/With/Slashes\\And\\Backslashes:Colon*Star?Question\"Quote<Less>Greater|Pipe", "Illegal file chars"),
        ]

        with patch("generate.generate_ai_content", return_value=mock_ai):
            for name, desc in adversarial_names:
                lead = {
                    "name": name,
                    "primary_type": "retail",
                    "address": "123 Security Blvd",
                    "rating": 4.5,
                    "review_count": 10
                }
                with self.subTest(name=name, desc=desc):
                    site_path = generate.generate_site(lead, "retail")
                    self.assertIsNotNone(site_path)
                    p = Path(site_path)
                    self.assertTrue(p.exists())
                    self.assertTrue((p / "index.html").exists())

            # Specific Windows device crash on NUL
            nul_lead = {"name": "NUL", "primary_type": "retail", "address": "123 Test St", "rating": 4.5, "review_count": 10}
            if os.name == "nt":
                with self.assertRaises(FileNotFoundError):
                    generate.generate_site(nul_lead, "retail")

    # -------------------------------------------------------------------------
    # VECTOR 7: High-Throughput Burst Stress Workload
    # -------------------------------------------------------------------------
    def test_v7_burst_workload(self):
        """Generate 105 sites (15 of each vertical) in rapid succession to test resource leaks & stability."""
        mock_ai = {
            "tagline": "Burst Performance Tagline",
            "about_text": "Burst performance about text running high speed site generation.",
            "services": [{"name": f"Speed Service {i}", "description": "Rapid response and high performance"} for i in range(1, 7)],
            "meta_description": "Burst generation meta description."
        }

        start_time = time.time()
        count = 0

        with patch("generate.generate_ai_content", return_value=mock_ai):
            for i in range(15):
                for cat in ALL_TEMPLATES:
                    lead = {
                        "name": f"Stress Corp {cat.title()} Batch{i+1}",
                        "discovery_category": cat,
                        "primary_type": cat,
                        "address": f"{100+i} Enterprise Way, Sector {i+1}, Tech City",
                        "rating": 4.0 + (i % 10) * 0.1,
                        "review_count": (i + 1) * 25,
                        "phone_national": f"+91 98000 {i:05d}",
                        "google_maps_url": f"https://maps.google.com/?q={cat}+{i}"
                    }
                    site_path = generate.generate_site(lead, cat)
                    self.assertIsNotNone(site_path)
                    self.assertTrue(Path(site_path).exists())
                    self.assertTrue((Path(site_path) / "index.html").exists())
                    self.assertTrue((Path(site_path) / "style.css").exists())
                    count += 1

        elapsed = time.time() - start_time
        rate = count / elapsed if elapsed > 0 else 999.0
        print(f"\n⚡ Burst Workload Completed: {count} sites generated across 7 verticals in {elapsed:.2f}s ({rate:.1f} sites/sec)")
        self.assertEqual(count, 105)


if __name__ == "__main__":
    unittest.main(verbosity=2)
