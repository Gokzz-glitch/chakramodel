#!/usr/bin/env python3
"""
===============================================================================
Elite Website Templates Suite — Standalone E2E Master Test Runner
===============================================================================
Executes 4-Tier validation across all 7 business verticals:
  1. General (Corporate / Multi-service)
  2. Cafe & Dining (Restaurant, Cafe, Bakery)
  3. Transport (Logistics, Fleet, Travel)
  4. Salon & Spa (Beauty, Wellness, Barber)
  5. Retail & Store (Boutique, Supermarket)
  6. Fitness & Gym (Crossfit, Yoga Studio)
  7. Clinic & Medical (Healthcare Clinic, Dental)

Features:
- Pure Python standalone execution (zero external dependencies required)
- Programmatic generation + CLI subprocess invocation tests of generate.py
- Formatted ANSI terminal diagnostic tables and summary matrix per tier & vertical
- Mathematically precise WCAG 2.1 AA relative luminance and contrast calculations
- Full real-world 7-vertical synthetic leads generation workload validation
- Supports CLI flags: --tier, --template, --json-report, -v, --fail-fast, --clean
- Returns strict exit code 0 when all tests pass, and non-zero on test failures

Usage:
  python tests/e2e_test_runner.py
  python tests/e2e_test_runner.py --tier 4
  python tests/e2e_test_runner.py --template cafe
  python tests/e2e_test_runner.py --json-report output/test_report.json
"""

import argparse
import html
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from urllib.parse import quote_plus

# Ensure stdout and stderr use UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── ANSI Colors & Terminal Formatting ───────────────────────────────────────

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_DARK = "\033[40m"

    @classmethod
    def disable(cls):
        cls.RESET = cls.BOLD = cls.DIM = ""
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.MAGENTA = cls.CYAN = cls.WHITE = cls.BG_DARK = ""


# Auto-detect if terminal supports color / Windows VT100
if not sys.stdout.isatty():
    Color.disable()
elif os.name == "nt":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


# ─── Path Configuration ───────────────────────────────────────────────────────

TESTS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TESTS_DIR.parent
TEMPLATES_DIR = PROJECT_DIR / "templates"
SITE_GEN_DIR = PROJECT_DIR / "agents" / "site-generator"
GENERATE_SCRIPT = SITE_GEN_DIR / "generate.py"
OUTPUT_DIR = PROJECT_DIR / "output" / "sites"

# Ensure project root, tests, and site-generator are in sys.path
for p in [str(PROJECT_DIR), str(TESTS_DIR), str(SITE_GEN_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import generate
except ImportError:
    generate = None


# ─── 7-Vertical Synthetic Leads Catalog ───────────────────────────────────────

SYNTHETIC_LEADS: dict[str, dict] = {
    "general": {
        "name": "Nexus Advisory Group",
        "primary_type": "management consulting",
        "discovery_category": "general",
        "address": "100 Innovation Boulevard, Tech Park, Chennai, Tamil Nadu 600089",
        "phone_national": "+91 44 2345 6789",
        "phone_international": "+914423456789",
        "google_maps_url": "https://maps.google.com/?cid=1001",
        "rating": 4.9,
        "review_count": 320,
        "ai_content": {
            "tagline": "Pioneering Strategic Advisory & Digital Transformation",
            "about_text": "With over a decade of dedicated enterprise consulting in the region, Nexus Advisory Group delivers precision execution, strategic growth roadmaps, and client-centric solutions designed to scale operations and accelerate market leadership.",
            "meta_description": "Nexus Advisory Group in Chennai offers premier consulting solutions trusted by Fortune 500 leaders. Contact us today for strategic excellence!",
            "services": [
                {"name": "Strategic Growth Advisory", "description": "Tailored expert guidance to streamline operations and scale cross-border business growth."},
                {"name": "Digital Transformation", "description": "Cutting-edge modernization protocols for resilient enterprise architecture."},
                {"name": "Risk & Compliance Care", "description": "24/7 governance frameworks ensuring continuous regulatory safety and risk mitigation."},
                {"name": "Operations Optimization", "description": "Precision performance analytics reducing turnaround times and operational friction."},
                {"name": "Mergers & Integration", "description": "Bespoke integration workflows crafted for seamless post-merger synergy."},
                {"name": "Enterprise Security", "description": "Comprehensive cybersecurity and resilience frameworks for modern infrastructure."}
            ]
        }
    },
    "cafe": {
        "name": "The Royal Roastery Cafe",
        "primary_type": "artisan cafe",
        "discovery_category": "cafe",
        "address": "15 Indiranagar 100ft Road, Bengaluru, Karnataka 560038",
        "phone_national": "+91 80 4123 4567",
        "phone_international": "+918041234567",
        "google_maps_url": "https://maps.google.com/?cid=1002",
        "rating": 4.8,
        "review_count": 540,
        "ai_content": {
            "tagline": "Artisanal Single-Origin Roasts & Handcrafted Viennoiserie",
            "about_text": "Every cup poured and plate presented at The Royal Roastery is an homage to slow-food traditions, small-lot harvests, and thoughtful hospitality. We curate pure seasonal ingredients and roast our coffees in micro-batches daily.",
            "meta_description": "The Royal Roastery Cafe in Indiranagar Bengaluru offers single-origin micro-roasts, artisan pastries, and cozy dining.",
            "services": [
                {"name": "Single-Origin Pour Over", "description": "Directly traded specialty Arabica micro-lots steeped to perfection."},
                {"name": "Wild-Yeast Sourdough Bakery", "description": "Freshly baked laminated croissants and 48-hour fermented breads."},
                {"name": "Artisan Bistro Kitchen", "description": "Farm-fresh organic brunch bowls, gourmet salads, and savory entrees."},
                {"name": "Cold Drip Tasting Flights", "description": "Slow-extracted botanical cold brew infusions served chilled."},
                {"name": "Private Roasting Workshops", "description": "Hands-on coffee cupping and barista masterclasses with our head roaster."},
                {"name": "Gourmet Gift Hampers", "description": "Curated selection of roasted beans, preserves, and handcrafted treats."}
            ]
        }
    },
    "transport": {
        "name": "Metro Express Logistics",
        "primary_type": "freight logistics",
        "discovery_category": "transport",
        "address": "88 Grand Southern Trunk Rd, Guindy, Chennai, Tamil Nadu 600032",
        "phone_national": "+91 44 2233 4455",
        "phone_international": "+914422334455",
        "google_maps_url": "https://maps.google.com/?cid=1003",
        "rating": 4.7,
        "review_count": 410,
        "ai_content": {
            "tagline": "Next-Day Nationwide Cargo & Temperature-Controlled Fleets",
            "about_text": "Metro Express Logistics delivers end-to-end multimodal transportation networks across India. Powered by GPS telemetry, automated dispatch, and cold-chain compliance, we guarantee safe, on-time delivery for mission-critical cargo.",
            "meta_description": "Metro Express Logistics offers freight transportation, interstate cargo, and dedicated cold-chain fleet solutions in Chennai.",
            "services": [
                {"name": "Interstate Container Freight", "description": "Heavy-payload long-haul freight connecting major economic corridors."},
                {"name": "Cold-Chain Pharma Logistics", "description": "Temperature-monitored refrigerated transport maintaining strict vaccine protocols."},
                {"name": "Express Urban Parcel Delivery", "description": "Same-day metropolitan dispatch with live customer tracking portals."},
                {"name": "Warehouse Storage & 3PL", "description": "Secure warehousing, pick-and-pack fulfillment, and inventory analytics."},
                {"name": "Customs Port Clearance", "description": "Fast-track documentation and multi-modal transit for maritime shipments."},
                {"name": "Dedicated Fleet Leasing", "description": "Contractual commercial vehicles customized for enterprise supply chains."}
            ]
        }
    },
    "salon": {
        "name": "Luxe Glow Salon & Spa",
        "primary_type": "luxury salon",
        "discovery_category": "salon",
        "address": "24 Linking Road, Bandra West, Mumbai, Maharashtra 400050",
        "phone_national": "+91 22 6677 8899",
        "phone_international": "+912266778899",
        "google_maps_url": "https://maps.google.com/?cid=1004",
        "rating": 4.9,
        "review_count": 680,
        "ai_content": {
            "tagline": "Couture Hair Styling, Botanical Facials & Wellness Rituals",
            "about_text": "Luxe Glow Salon & Spa offers an oasis of rejuvenation in Bandra. Our internationally trained master stylists and therapists combine organic botanicals with advanced beauty technologies to deliver bespoke transformations.",
            "meta_description": "Luxe Glow Salon & Spa in Bandra Mumbai offers luxury hair transformations, keratin therapies, bridal makeup, and spa wellness.",
            "services": [
                {"name": "Keratin & Botanical Hair Spa", "description": "Deep-conditioning restorative rituals restoring radiant shine and strength."},
                {"name": "Hydra-Glow Signature Facial", "description": "Non-invasive multi-step skin rejuvenation for luminous vitality."},
                {"name": "Couture Balayage & Coloring", "description": "Handcrafted color blending customized to individual skin tones."},
                {"name": "Bridal Artistry & Makeovers", "description": "HD bridal makeup, draping, and styling packages for memorable occasions."},
                {"name": "Deep Tissue Aromatherapy", "description": "Full-body holistic stress relief using pure essential botanical oils."},
                {"name": "Nail Couture & Spa Pedicure", "description": "Gel extensions, nail art, and organic exfoliating foot treatments."}
            ]
        }
    },
    "retail": {
        "name": "Apex Gear Boutique",
        "primary_type": "retail boutique",
        "discovery_category": "retail",
        "address": "104 Jubilee Hills, Road No 36, Hyderabad, Telangana 500033",
        "phone_national": "+91 40 2345 6789",
        "phone_international": "+914023456789",
        "google_maps_url": "https://maps.google.com/?cid=1005",
        "rating": 4.8,
        "review_count": 290,
        "ai_content": {
            "tagline": "Curated Designer Apparel, Timepieces & Handcrafted Goods",
            "about_text": "Apex Gear Boutique is Jubilee Hills' premier destination for artisanal apparel, luxury leather accessories, and bespoke horology. Every piece is ethically sourced and meticulously crafted to celebrate individuality and craftsmanship.",
            "meta_description": "Apex Gear Boutique in Jubilee Hills Hyderabad offers luxury designer wear, accessories, and curated lifestyle collections.",
            "services": [
                {"name": "Bespoke Bespoke Tailoring", "description": "Custom made-to-measure suiting using the finest Italian wools and silks."},
                {"name": "Handmade Leather Goods", "description": "Full-grain artisanal wallets, messenger bags, and handcrafted footwear."},
                {"name": "Horology & Chronographs", "description": "Certified collectible timepieces with precision automatic movements."},
                {"name": "Private VIP Styling", "description": "Personalized wardrobe consultations with dedicated fashion advisors."},
                {"name": "Eco-Conscious Linen Line", "description": "Sustainable organic linens woven with breathable natural fibers."},
                {"name": "Worldwide Concierge Shipping", "description": "Complimentary insured express delivery on all premium orders."}
            ]
        }
    },
    "fitness": {
        "name": "Titan Fitness Club",
        "primary_type": "fitness center",
        "discovery_category": "fitness",
        "address": "55 Park Street, Chowringhee, Kolkata, West Bengal 700016",
        "phone_national": "+91 33 2288 9900",
        "phone_international": "+913322889900",
        "google_maps_url": "https://maps.google.com/?cid=1006",
        "rating": 4.9,
        "review_count": 520,
        "ai_content": {
            "tagline": "Olympic Free-Weights, Functional Arena & Cryo Recovery",
            "about_text": "Engineered for relentless athletic progress, Titan Fitness Club combines Olympic-standard free weights, functional turf zones, biometric progress tracking, and certified strength coaches in a high-octane community environment.",
            "meta_description": "Titan Fitness Club on Park Street Kolkata offers high-performance strength training, CrossFit turf, and cryotherapy recovery.",
            "services": [
                {"name": "Olympic Heavy Iron Deck", "description": "Competition-grade barbells, bumper plates, and power cages for heavy lifting."},
                {"name": "CrossFit Conditioning Turf", "description": "Functional obstacle arenas, sled tracks, and high-intensity interval gear."},
                {"name": "1-on-1 Biometric Coaching", "description": "Body-composition analytics and personalized nutritional guidance."},
                {"name": "Cryo & Hydrotherapy Lab", "description": "Sub-zero cold recovery and infrared saunas for rapid muscle repair."},
                {"name": "Mobility & Power Yoga", "description": "Dynamic movement sessions designed to enhance joint longevity and flexibility."},
                {"name": "24/7 RFID Arena Access", "description": "Unrestricted keycard access for seamless round-the-clock training."}
            ]
        }
    },
    "clinic": {
        "name": "Aura Dental Care",
        "primary_type": "dental clinic",
        "discovery_category": "clinic",
        "address": "12 Mount Road, Anna Salai, Chennai, Tamil Nadu 600002",
        "phone_national": "+91 44 2855 1122",
        "phone_international": "+914428551122",
        "google_maps_url": "https://maps.google.com/?cid=1007",
        "rating": 4.9,
        "review_count": 890,
        "ai_content": {
            "tagline": "Advanced Micro-Dentistry, Pain-Free Implants & Smile Design",
            "about_text": "Aura Dental Care combines cutting-edge dental laser technology, 3D CBCT scanning, and gentle pain-free clinical techniques. Our team of specialist prosthodontists and orthodontists is dedicated to crafting healthy, radiant smiles.",
            "meta_description": "Aura Dental Care in Anna Salai Chennai offers painless root canals, dental implants, teeth whitening, and smile design.",
            "services": [
                {"name": "Digital Smile Designing", "description": "3D photorealistic aesthetic simulations for veneers and smile alignment."},
                {"name": "Laser Micro-Dentistry", "description": "Pain-free root canals and gum sculpting with rapid healing times."},
                {"name": "Titanium Dental Implants", "description": "Permanent bio-compatible tooth restorations with lifetime warranties."},
                {"name": "Invisible Clear Aligners", "description": "Discreet orthodontic correction for adults and teens with digital progress monitoring."},
                {"name": "Pediatric Dental Care", "description": "Child-friendly preventive dentistry in a gentle, welcoming environment."},
                {"name": "24/7 Emergency Consultation", "description": "Rapid triage for acute dental pain, trauma, and urgent restorations."}
            ]
        }
    }
}


# ─── HTML & CSS Parsers for Standalone Runner ────────────────────────────────

class StandaloneHTMLValidator(HTMLParser):
    """HTML parser to validate structure, landmarks, and detect unreplaced placeholders."""
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__()
        self.tags = []
        self.has_doctype = False
        self.has_html = False
        self.has_head = False
        self.has_body = False
        self.has_nav = False
        self.has_header = False
        self.has_footer = False
        self.has_title = False
        self.has_viewport = False
        self.img_missing_alt = 0
        self.img_total = 0

    def handle_decl(self, decl):
        if "html" in decl.lower():
            self.has_doctype = True

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        self.tags.append(tag)
        if tag == "html":
            self.has_html = True
        elif tag == "head":
            self.has_head = True
        elif tag == "body":
            self.has_body = True
        elif tag == "nav":
            self.has_nav = True
        elif tag == "header":
            self.has_header = True
        elif tag == "footer":
            self.has_footer = True
        elif tag == "title":
            self.has_title = True
        elif tag == "meta":
            if attr_dict.get("name") == "viewport" and "width=device-width" in (attr_dict.get("content") or ""):
                self.has_viewport = True
        elif tag == "img":
            self.img_total += 1
            if not attr_dict.get("alt"):
                self.img_missing_alt += 1


# ─── Master E2E Runner Implementation ────────────────────────────────────────

class E2EMasterRunner:
    """Orchestrates test execution, synthetic lead site generation, and diagnostics."""

    def __init__(self, options):
        self.options = options
        self.results = {
            "tier1": {"passed": 0, "failed": 0, "total": 0, "details": []},
            "tier2": {"passed": 0, "failed": 0, "total": 0, "details": []},
            "tier3": {"passed": 0, "failed": 0, "total": 0, "details": []},
            "tier4": {"passed": 0, "failed": 0, "total": 0, "details": []},
            "categories": {},
            "start_time": 0.0,
            "duration": 0.0,
            "overall_status": "PENDING"
        }
        self.temp_dirs = []

    def clean_output_dir(self):
        """Clean output directory if requested."""
        if self.options.clean and OUTPUT_DIR.exists():
            for item in OUTPUT_DIR.iterdir():
                if item.is_dir() and item.name.startswith("test-"):
                    shutil.rmtree(item, ignore_errors=True)

    def run_unit_tests(self) -> bool:
        """Run unittests from test_templates.py and test_adversarial_stress.py with tier filtering and failfast."""
        tier_label = f"Tier {self.options.tier}" if self.options.tier != "all" else "All Tiers"
        print(f"\n{Color.BOLD}{Color.CYAN}▶ Executing Unit Test Suite ({tier_label})...{Color.RESET}")

        full_suite = unittest.defaultTestLoader.discover(str(TESTS_DIR), pattern="test_*.py")

        def collect_test_cases(s, tier_filter: str):
            cases = []
            target_cls = f"tier{tier_filter}".lower() if tier_filter != "all" else None
            for item in s:
                if isinstance(item, unittest.TestSuite):
                    cases.extend(collect_test_cases(item, tier_filter))
                elif isinstance(item, unittest.TestCase):
                    cls_name = item.__class__.__name__.lower()
                    test_name = str(item).lower()
                    if target_cls is None:
                        cases.append(item)
                    elif target_cls in cls_name or target_cls in test_name:
                        cases.append(item)
                    elif tier_filter == "2" and "adversarial" in cls_name:
                        cases.append(item)
            return cases

        selected_cases = collect_test_cases(full_suite, self.options.tier)
        suite = unittest.TestSuite()
        for case in selected_cases:
            suite.addTest(case)

        runner = unittest.TextTestRunner(
            verbosity=2 if self.options.verbose else 1,
            failfast=self.options.fail_fast
        )
        test_result = runner.run(suite)

        # Map failures/errors
        failed_tests = set()
        for test, err in test_result.failures + test_result.errors:
            name = str(test)
            failed_tests.add(name)
            cls_name = getattr(test, "test_case", test).__class__.__name__
            full_ident = f"{cls_name} {name}".lower()
            tier_key = "tier1" if "tier1" in full_ident else ("tier2" if ("tier2" in full_ident or "adversarial" in full_ident) else ("tier3" if "tier3" in full_ident else "tier4"))
            self.results[tier_key]["failed"] += 1
            self.results[tier_key]["details"].append({"test": name, "status": "FAIL", "error": err})

        # Count total and passed per tier
        for case in selected_cases:
            name = str(case)
            cls_name = case.__class__.__name__
            full_ident = f"{cls_name} {name}".lower()
            tier_key = "tier1" if "tier1" in full_ident else ("tier2" if ("tier2" in full_ident or "adversarial" in full_ident) else ("tier3" if "tier3" in full_ident else "tier4"))
            self.results[tier_key]["total"] += 1
            if name not in failed_tests:
                self.results[tier_key]["passed"] += 1

        return test_result.wasSuccessful()

    def run_tier4_workload(self) -> bool:
        """Execute Tier 4 Real-World Site Generation Workload across all 7 synthetic leads."""
        print(f"\n{Color.BOLD}{Color.MAGENTA}▶ Executing Tier 4 Workload Testing Across 7 Verticals...{Color.RESET}")

        all_passed = True
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        for category, lead_data in SYNTHETIC_LEADS.items():
            if self.options.template != "all" and self.options.template != category:
                continue

            t0 = time.time()
            lead_name = lead_data["name"]
            template_name = category if (TEMPLATES_DIR / category).exists() else "general"

            # Safe directory slug
            safe_slug = re.sub(r"[^\w\s-]", "", lead_name).strip()
            safe_slug = re.sub(r"[-\s]+", "-", safe_slug).lower()
            site_dir = OUTPUT_DIR / safe_slug

            status_entry = {
                "category": category,
                "lead_name": lead_name,
                "template": template_name,
                "path": str(site_dir),
                "html_exists": False,
                "css_exists": False,
                "html_size": 0,
                "css_size": 0,
                "unreplaced_tokens": [],
                "html_valid": False,
                "cli_subprocess_ok": False,
                "duration_ms": 0,
                "passed": False
            }

            try:
                # 1. Programmatic Site Generation Test
                html_raw, css_raw = generate.load_template(template_name)
                filled_html, filled_css = generate.fill_template(
                    html_raw, css_raw, lead_data, lead_data["ai_content"]
                )

                os.makedirs(site_dir, exist_ok=True)
                html_file = site_dir / "index.html"
                css_file = site_dir / "style.css"

                html_file.write_text(filled_html, encoding="utf-8")
                css_file.write_text(filled_css, encoding="utf-8")

                status_entry["html_exists"] = html_file.exists()
                status_entry["css_exists"] = css_file.exists()
                status_entry["html_size"] = html_file.stat().st_size
                status_entry["css_size"] = css_file.stat().st_size

                # 2. Token Orphan Scanner (0 unreplaced {{...}})
                orphans = re.findall(r"\{\{[A-Z0-9_]+\}\}", filled_html) + re.findall(r"\{\{[A-Z0-9_]+\}\}", filled_css)
                status_entry["unreplaced_tokens"] = list(set(orphans))

                # 3. HTML Structure & Landmark Audit
                parser = StandaloneHTMLValidator()
                parser.feed(filled_html)
                status_entry["html_valid"] = parser.has_doctype and parser.has_title and parser.has_nav and parser.has_footer

                # 4. External CLI Subprocess Execution Test of generate.py
                temp_leads_file = Path(tempfile.gettempdir()) / f"lead_{category}.json"
                temp_leads_file.write_text(json.dumps([lead_data]), encoding="utf-8")

                proc = subprocess.run(
                    [sys.executable, str(GENERATE_SCRIPT), "--input", str(temp_leads_file), "--all"],
                    cwd=str(PROJECT_DIR),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
                status_entry["cli_subprocess_ok"] = (proc.returncode == 0)

                # Clean temporary file
                if temp_leads_file.exists():
                    temp_leads_file.unlink(missing_ok=True)

                # Evaluate overall pass for this vertical
                is_ok = (
                    status_entry["html_exists"]
                    and status_entry["css_exists"]
                    and status_entry["html_size"] > 1000
                    and status_entry["css_size"] > 200
                    and len(status_entry["unreplaced_tokens"]) == 0
                    and status_entry["html_valid"]
                    and status_entry["cli_subprocess_ok"]
                )

                status_entry["passed"] = is_ok
                if not is_ok:
                    all_passed = False
                    if self.options.fail_fast:
                        break

            except Exception as ex:
                status_entry["error"] = str(ex)
                status_entry["traceback"] = traceback.format_exc()
                status_entry["passed"] = False
                all_passed = False
                if self.options.fail_fast:
                    break

            status_entry["duration_ms"] = int((time.time() - t0) * 1000)
            self.results["categories"][category] = status_entry

            # Terminal log
            mark = f"{Color.GREEN}✔ PASS{Color.RESET}" if status_entry["passed"] else f"{Color.RED}✖ FAIL{Color.RESET}"
            print(f"  [{mark}] {category.upper():<10} | Lead: {lead_name:<30} | Size: {status_entry['html_size']}B HTML, {status_entry['css_size']}B CSS | {status_entry['duration_ms']}ms")

            if not status_entry["passed"] and self.options.verbose:
                print(f"      {Color.RED}Orphans: {status_entry['unreplaced_tokens']} | HTML Valid: {status_entry['html_valid']} | CLI OK: {status_entry['cli_subprocess_ok']}{Color.RESET}")

        if self.results["categories"]:
            cat_passed = sum(1 for c in self.results["categories"].values() if c.get("passed"))
            cat_failed = len(self.results["categories"]) - cat_passed
            self.results["tier4"]["total"] += len(self.results["categories"])
            self.results["tier4"]["passed"] += cat_passed
            self.results["tier4"]["failed"] += cat_failed

        return all_passed

    def print_summary_matrix(self):
        """Render ANSI colored summary dashboard."""
        print(f"\n{Color.BOLD}{Color.WHITE}========================================================================================{Color.RESET}")
        print(f"{Color.BOLD}{Color.CYAN}                      AUTOWEB ELITE TEMPLATES E2E TEST SUMMARY MATRIX                    {Color.RESET}")
        print(f"{Color.BOLD}{Color.WHITE}========================================================================================{Color.RESET}")

        # Tiers Table
        print(f"{Color.BOLD}{'Test Tier':<42} | {'Passed':<8} | {'Failed':<8} | {'Status':<10}{Color.RESET}")
        print("-" * 88)

        tiers = [
            ("Tier 1: Feature & Placeholder Coverage", "tier1"),
            ("Tier 2: Boundary & Corner Cases", "tier2"),
            ("Tier 3: Design Tokens, A11y & Aesthetics", "tier3"),
            ("Tier 4: Real-World Workload Simulation", "tier4")
        ]

        total_p = 0
        total_f = 0

        for title, key in tiers:
            p = self.results[key]["passed"]
            f = self.results[key]["failed"]
            tot = self.results[key]["total"]
            total_p += p
            total_f += f
            if tot == 0:
                st = f"{Color.YELLOW}SKIP{Color.RESET}"
            elif f == 0 and p > 0:
                st = f"{Color.GREEN}PASS{Color.RESET}"
            else:
                st = f"{Color.RED}FAIL{Color.RESET}"
            print(f"{title:<42} | {p:<8} | {f:<8} | {st:<10}")

        print("-" * 88)
        status_label = f"{Color.GREEN}100% PASS{Color.RESET}" if (total_f == 0 and total_p > 0) else (f"{Color.YELLOW}NO TESTS{Color.RESET}" if total_p == 0 else f"{Color.RED}FAILURES{Color.RESET}")
        print(f"{'Total Automated Assertions':<42} | {total_p:<8} | {total_f:<8} | {status_label}")

        # Category Matrix Table
        if self.results["categories"]:
            print(f"\n{Color.BOLD}{'Vertical Category':<15} | {'Synthetic Business Lead':<30} | {'Template':<10} | {'Tokens':<8} | {'CLI':<6} | {'Status'}{Color.RESET}")
            print("-" * 88)

            for cat, data in self.results["categories"].items():
                st = f"{Color.GREEN}PASS{Color.RESET}" if data.get("passed") else f"{Color.RED}FAIL{Color.RESET}"
                tok_status = "0 Leaks" if len(data.get("unreplaced_tokens", [])) == 0 else f"{len(data.get('unreplaced_tokens'))} Leaks"
                cli_st = "OK" if data.get("cli_subprocess_ok") else "ERR"
                print(f"{cat.capitalize():<15} | {data.get('lead_name', '')[:28]:<30} | {data.get('template', ''):<10} | {tok_status:<8} | {cli_st:<6} | {st}")

            print("-" * 88)

        duration_s = self.results["duration"]
        overall_pass = (total_f == 0 and total_p > 0 and (not self.results["categories"] or all(d.get("passed") for d in self.results["categories"].values())))
        overall = f"{Color.BOLD}{Color.GREEN}ALL TESTS PASSED — READY FOR PRODUCTION{Color.RESET}" if overall_pass else f"{Color.BOLD}{Color.RED}TEST SUITE DETECTED FAILURES{Color.RESET}"
        print(f"\n⏱ Execution Time: {duration_s:.2f}s | Overall Result: {overall}\n")

    def export_json_report(self, path_str: str):
        """Export machine-readable JSON summary report."""
        report_path = Path(path_str)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "duration_seconds": self.results["duration"],
            "overall_status": "PASS" if self.results["overall_status"] == "PASS" else "FAIL",
            "tier_results": {
                "tier1": self.results["tier1"],
                "tier2": self.results["tier2"],
                "tier3": self.results["tier3"],
                "tier4": self.results["tier4"]
            },
            "vertical_categories": self.results["categories"]
        }
        report_path.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        print(f"📄 Exported machine-readable JSON report to: {report_path.resolve()}")

    def run(self) -> int:
        """Main execution flow."""
        self.results["start_time"] = time.time()
        self.clean_output_dir()

        run_all = (self.options.tier == "all")

        unit_ok = True
        if run_all or self.options.tier in ["1", "2", "3", "4"]:
            unit_ok = self.run_unit_tests()

        workload_ok = True
        if (run_all or self.options.tier == "4") and (not self.options.fail_fast or unit_ok):
            workload_ok = self.run_tier4_workload()

        self.results["duration"] = time.time() - self.results["start_time"]
        success = unit_ok and workload_ok
        self.results["overall_status"] = "PASS" if success else "FAIL"

        self.print_summary_matrix()

        if self.options.json_report:
            self.export_json_report(self.options.json_report)

        return 0 if success else 1


# ─── CLI Entrypoint ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🎨 Elite Website Templates — Master 4-Tier E2E Test Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--tier", "-t",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Filter execution to a specific test tier"
    )
    parser.add_argument(
        "--template",
        choices=["general", "cafe", "transport", "salon", "retail", "fitness", "clinic", "all"],
        default="all",
        help="Filter execution to a specific template vertical"
    )
    parser.add_argument(
        "--json-report", "-j",
        type=str,
        default=None,
        help="Path to export machine-readable JSON test report"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable detailed verbose output"
    )
    parser.add_argument(
        "--fail-fast", "-f",
        action="store_true",
        help="Stop test execution immediately upon first failure"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean previously generated test site artifacts before running"
    )

    args = parser.parse_args()
    runner = E2EMasterRunner(args)
    exit_code = runner.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
