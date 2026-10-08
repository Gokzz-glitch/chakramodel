#!/usr/bin/env python3
"""
AutoWeb Pipeline Runner
=========================
Runs the complete end-to-end pipeline:
  Discover → Score → Generate → Outreach

Usage:
    python pipeline.py --area "Ramapuram, Chennai" --category "restaurant"
    python pipeline.py --config config.json --target 0
    python pipeline.py --config config.json --all
    python pipeline.py --demo  # Run with sample data (no API key needed)
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR.parent / ".env")


def run_step(name: str, cmd: list[str], cwd: str = None):
    """Run a pipeline step and handle output."""
    print(f"\n{'='*60}")
    print(f"🔄 Step: {name}")
    print(f"{'='*60}")

    result = subprocess.run(
        cmd,
        cwd=cwd or str(SCRIPT_DIR),
        capture_output=False,
    )

    if result.returncode != 0:
        print(f"\n❌ Step '{name}' failed with exit code {result.returncode}")
        return False

    print(f"\n✅ Step '{name}' completed")
    return True


def create_demo_data():
    """Create sample lead data for testing without an API key."""
    output_dir = SCRIPT_DIR.parent / "output"
    os.makedirs(output_dir, exist_ok=True)

    demo_leads = [
        {
            "id": "demo_001",
            "name": "Sri Balaji Transport",
            "address": "45, Arcot Road, Ramapuram, Chennai, Tamil Nadu 600089",
            "phone_national": "044 2345 6789",
            "phone_international": "+91 44 2345 6789",
            "website": "",
            "google_maps_url": "https://maps.google.com/?cid=1234567890",
            "rating": 4.3,
            "review_count": 87,
            "business_status": "OPERATIONAL",
            "primary_type": "transport_agency",
            "types": ["moving_company", "point_of_interest", "establishment"],
            "photo_refs": ["photo_ref_1", "photo_ref_2", "photo_ref_3"],
            "business_hours": ["Monday: 8:00 AM – 9:00 PM", "Tuesday: 8:00 AM – 9:00 PM"],
            "discovery_area": "Ramapuram, Chennai",
            "discovery_category": "transport agency",
            "discovered_at": "2025-01-01T00:00:00Z"
        },
        {
            "id": "demo_002",
            "name": "Madras Coffee House",
            "address": "12, Mount Poonamallee Road, Ramapuram, Chennai, Tamil Nadu 600089",
            "phone_national": "044 8765 4321",
            "phone_international": "+91 44 8765 4321",
            "website": "",
            "google_maps_url": "https://maps.google.com/?cid=9876543210",
            "rating": 4.5,
            "review_count": 156,
            "business_status": "OPERATIONAL",
            "primary_type": "cafe",
            "types": ["cafe", "restaurant", "food", "point_of_interest"],
            "photo_refs": ["photo_ref_1", "photo_ref_2", "photo_ref_3", "photo_ref_4"],
            "business_hours": ["Monday: 7:00 AM – 10:00 PM", "Tuesday: 7:00 AM – 10:00 PM"],
            "discovery_area": "Ramapuram, Chennai",
            "discovery_category": "cafe",
            "discovered_at": "2025-01-01T00:00:00Z"
        },
        {
            "id": "demo_003",
            "name": "Royal Studio Photography",
            "address": "23, Jawaharlal Nehru Road, Ramapuram, Chennai, Tamil Nadu 600089",
            "phone_national": "098765 43210",
            "phone_international": "+91 98765 43210",
            "website": "",
            "google_maps_url": "https://maps.google.com/?cid=1122334455",
            "rating": 4.1,
            "review_count": 42,
            "business_status": "OPERATIONAL",
            "primary_type": "photo_studio",
            "types": ["photographer", "point_of_interest", "establishment"],
            "photo_refs": ["photo_ref_1", "photo_ref_2"],
            "business_hours": ["Monday: 9:00 AM – 8:00 PM"],
            "discovery_area": "Ramapuram, Chennai",
            "discovery_category": "photo studio",
            "discovered_at": "2025-01-01T00:00:00Z"
        },
        {
            "id": "demo_004",
            "name": "Green Leaf Restaurant",
            "address": "67, Poonamallee High Road, Porur, Chennai, Tamil Nadu 600116",
            "phone_national": "044 5544 3322",
            "phone_international": "+91 44 5544 3322",
            "website": "",
            "google_maps_url": "https://maps.google.com/?cid=5566778899",
            "rating": 3.8,
            "review_count": 23,
            "business_status": "OPERATIONAL",
            "primary_type": "restaurant",
            "types": ["restaurant", "food", "point_of_interest"],
            "photo_refs": ["photo_ref_1"],
            "business_hours": ["Monday: 11:00 AM – 11:00 PM"],
            "discovery_area": "Porur, Chennai",
            "discovery_category": "restaurant",
            "discovered_at": "2025-01-01T00:00:00Z"
        },
        {
            "id": "demo_005",
            "name": "Anand Hair Salon",
            "address": "89, Anna Nagar, Ramapuram, Chennai, Tamil Nadu 600089",
            "phone_national": "098123 45678",
            "phone_international": "+91 98123 45678",
            "website": "",
            "google_maps_url": "https://maps.google.com/?cid=6677889900",
            "rating": 4.7,
            "review_count": 210,
            "business_status": "OPERATIONAL",
            "primary_type": "hair_salon",
            "types": ["hair_care", "beauty_salon", "point_of_interest"],
            "photo_refs": ["photo_ref_1", "photo_ref_2", "photo_ref_3", "photo_ref_4", "photo_ref_5"],
            "business_hours": ["Monday: 9:00 AM – 9:00 PM"],
            "discovery_area": "Ramapuram, Chennai",
            "discovery_category": "salon",
            "discovered_at": "2025-01-01T00:00:00Z"
        }
    ]

    json_path = output_dir / "leads.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(demo_leads, f, indent=2, ensure_ascii=False)

    print(f"📋 Created {len(demo_leads)} demo leads at {json_path}")
    return demo_leads


def main():
    parser = argparse.ArgumentParser(
        description="🚀 AutoWeb Pipeline — End-to-end automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pipeline.py --demo                          # Test with sample data
  python pipeline.py --area "Ramapuram" --category "restaurant"  # Single search
  python pipeline.py --config config.json --target 0  # Run first config target
  python pipeline.py --config config.json --all       # Run all targets
        """
    )

    parser.add_argument("--demo", action="store_true", help="Run with demo data (no API key needed)")
    parser.add_argument("--config", type=str, help="Config file path")
    parser.add_argument("--target", type=int, help="Target index from config")
    parser.add_argument("--all", action="store_true", help="All targets from config")
    parser.add_argument("--area", type=str, help="Area to search")
    parser.add_argument("--category", type=str, help="Business category")
    parser.add_argument("--top", type=int, default=5, help="Number of top leads to generate sites for")
    parser.add_argument("--skip-discover", action="store_true", help="Skip discovery (use existing leads)")
    parser.add_argument("--skip-generate", action="store_true", help="Skip site generation")
    parser.add_argument("--skip-outreach", action="store_true", help="Skip outreach messages")
    parser.add_argument("--deploy", action="store_true", help="Deploy generated sites to GitHub Pages")

    args = parser.parse_args()

    python = sys.executable
    agents_dir = str(SCRIPT_DIR)

    print("🚀 AutoWeb Pipeline Starting...")
    print(f"   Working directory: {SCRIPT_DIR.parent}")
    print(f"   Max Sites/Outreach (Top): {args.top}")

    # ─── Step 1: Discover Leads ──────────────────────────────────────────
    if args.demo:
        print(f"\n{'='*60}")
        print(f"📦 Demo Mode — Creating sample data")
        print(f"{'='*60}")
        create_demo_data()
    elif not args.skip_discover:
        discover_cmd = [python, "lead-discovery/discover.py"]

        if args.config:
            discover_cmd.extend(["--config", args.config])
            if args.all:
                discover_cmd.append("--all")
            elif args.target is not None:
                discover_cmd.extend(["--target", str(args.target)])
        elif args.area and args.category:
            discover_cmd.extend(["--area", args.area, "--category", args.category])
        else:
            discover_cmd.extend(["--config", "config.json", "--target", "0"])

        success = run_step("Lead Discovery", discover_cmd, agents_dir)
        if not success:
            print("\n❌ Pipeline stopped at discovery stage")
            sys.exit(1)

    # ─── Step 2: Score Leads ─────────────────────────────────────────────
    success = run_step("Lead Scoring", [
        python, "lead-scoring/score.py",
        "--input", str(SCRIPT_DIR.parent / "output" / "leads.json"),
        "--output", str(SCRIPT_DIR.parent / "output" / "scored_leads.json"),
        "--config", str(SCRIPT_DIR / "config.json"),
    ], agents_dir)

    if not success:
        print("\n❌ Pipeline stopped at scoring stage")
        sys.exit(1)

    # ─── Step 3: Generate Sites ──────────────────────────────────────────
    if not args.skip_generate:
        success = run_step("Site Generation", [
            python, "site-generator/generate.py",
            "--input", str(SCRIPT_DIR.parent / "output" / "scored_leads.json"),
            "--top", str(args.top),
        ], agents_dir)

        if not success:
            print("\n⚠️  Site generation had issues (continuing anyway)")

    # ─── Step 4: Deploy Sites (Optional) ──────────────────────────────────
    preview_url_arg = ""
    if args.deploy:
        success = run_step("GitHub Pages Deployment", [
            python, "deployer/deploy_github.py"
        ], agents_dir)
        
        if success:
            # Get the base URL
            try:
                username_proc = subprocess.run(["gh", "api", "user", "-q", ".login"], capture_output=True, text=True, check=True)
                username = username_proc.stdout.strip()
                preview_url_arg = f"https://{username}.github.io/autoweb-sites"
            except Exception as e:
                print(f"⚠️ Could not get GitHub username for preview URLs: {e}")
        else:
             print("\n⚠️  Deployment had issues (continuing anyway)")

    # ─── Step 5: Outreach Messages ───────────────────────────────────────
    if not args.skip_outreach:
        outreach_cmd = [
            python, "outreach/outreach.py",
            "--input", str(SCRIPT_DIR.parent / "output" / "scored_leads.json"),
            "--channel", "whatsapp",
            "--top", str(args.top),
            "--preview",
        ]
        
        if preview_url_arg:
            outreach_cmd.extend(["--preview-url", preview_url_arg])
            
        success = run_step("Outreach Messages", outreach_cmd, agents_dir)

    # ─── Done ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"🎉 Pipeline Complete!")
    print(f"{'='*60}")
    print(f"\n📂 Output files:")
    print(f"   Leads:   {SCRIPT_DIR.parent / 'output' / 'leads.json'}")
    print(f"   Scored:  {SCRIPT_DIR.parent / 'output' / 'scored_leads.json'}")
    print(f"   Sites:   {SCRIPT_DIR.parent / 'output' / 'sites' / ''}")
    print(f"\n💡 Next steps:")
    print(f"   1. Review generated sites in output/sites/")
    print(f"   2. Send WhatsApp messages to HOT leads")
    print(f"   3. Deploy approved sites: python deployer/deploy.py --list")


if __name__ == "__main__":
    main()
