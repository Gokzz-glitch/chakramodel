#!/usr/bin/env python3
"""
AutoWeb Lead Discovery Agent
=============================
Discovers local businesses WITHOUT websites using Apify Google Maps Scraper.

Usage:
    python discover.py --area "Ramapuram, Chennai" --category "restaurant"
    python discover.py --config ../agents/config.json --target 0
    python discover.py --config ../agents/config.json --all

Output:
    Saves leads to ../output/leads.json and ../output/leads.csv
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

# ─── Constants ───────────────────────────────────────────────────────────────

APIFY_RUN_URL = "https://api.apify.com/v2/acts/compass~crawler-google-places/run-sync-get-dataset-items"
# Request timeout for Apify (it waits up to this amount for the scraper to finish)
TIMEOUT_SECONDS = 300 

# ─── Core Functions ──────────────────────────────────────────────────────────

def search_businesses(api_key: str, query: str, max_results: int = 60) -> list[dict]:
    """
    Search for businesses using Apify Google Maps Scraper.
    Returns a list of place objects.
    """
    url = f"{APIFY_RUN_URL}?token={api_key}"
    payload = {
        "searchStringsArray": [query],
        "maxCrawledPlacesPerSearch": max_results,
        "language": "en"
    }
    
    print(f"  🚀 Calling Apify Google Maps Scraper (this may take 1-3 minutes)...")
    try:
        response = requests.post(url, json=payload, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        print(f"  📦 Fetched {len(data)} results from Apify")
        return data
    except requests.exceptions.RequestException as e:
        print(f"  ❌ API Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"     Response: {e.response.text[:500]}")
        return []


def filter_no_website(places: list[dict]) -> list[dict]:
    """Filter places that do NOT have a website."""
    no_website = []
    has_website = 0

    for place in places:
        website = place.get("website", "")
        if not website or website.strip() == "":
            no_website.append(place)
        else:
            has_website += 1

    print(f"  🔍 Filter: {len(no_website)} without website, {has_website} with website")
    return no_website


def extract_lead(place: dict, area: str, category: str) -> dict:
    """Extract a clean lead object from Apify's response."""
    return {
        "id": place.get("placeId", "") or place.get("url", ""), # Fallback to URL if placeId missing
        "name": place.get("title", "Unknown Business"),
        "address": place.get("address", ""),
        "phone_national": place.get("phoneUnformatted", place.get("phone", "")),
        "phone_international": place.get("phone", ""),
        "website": place.get("website", ""),
        "google_maps_url": place.get("url", ""),
        "rating": place.get("totalScore", 0),
        "review_count": place.get("reviewsCount", 0),
        "business_status": place.get("status", "OPERATIONAL").upper(),
        "primary_type": category,
        "types": place.get("categories", []),
        "photo_refs": place.get("imageUrls", [])[:5],
        "business_hours": [f"{h.get('day', '')}: {h.get('hours', '')}" for h in place.get("openingHours", []) if isinstance(h, dict)],
        "discovery_area": area,
        "discovery_category": category,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
    }


def deduplicate_leads(existing: list[dict], new_leads: list[dict]) -> list[dict]:
    """Remove duplicates based on place ID."""
    existing_ids = {lead["id"] for lead in existing if lead.get("id")}
    unique_new = [lead for lead in new_leads if lead.get("id") not in existing_ids]
    print(f"  🔄 Dedup: {len(new_leads)} new → {len(unique_new)} unique (skipped {len(new_leads) - len(unique_new)} duplicates)")
    return unique_new


def save_leads(leads: list[dict], output_dir: str):
    """Save leads to JSON and CSV files."""
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "leads.json")
    csv_path = os.path.join(output_dir, "leads.csv")

    # Load existing leads
    existing = []
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # Deduplicate
    unique_new = deduplicate_leads(existing, leads)
    all_leads = existing + unique_new

    # Save JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_leads, f, indent=2, ensure_ascii=False)

    # Save CSV
    if all_leads:
        csv_fields = [
            "name", "address", "phone_national", "phone_international",
            "rating", "review_count", "google_maps_url", "primary_type",
            "discovery_area", "discovery_category", "discovered_at"
        ]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_leads)

    print(f"\n✅ Saved {len(all_leads)} total leads ({len(unique_new)} new)")
    print(f"   JSON: {json_path}")
    print(f"   CSV:  {csv_path}")

    return all_leads


# ─── CLI Interface ───────────────────────────────────────────────────────────

def discover_single(api_key: str, area: str, category: str, output_dir: str):
    """Discover leads for a single area + category combination."""
    query = f"{category} in {area}"
    print(f"\n🔎 Searching: \"{query}\"")

    # Limit to 15 per search to save Apify compute resources
    places = search_businesses(api_key, query, max_results=15)
    if not places:
        print("  ⚠️  No results found")
        return []

    no_website = filter_no_website(places)
    leads = [extract_lead(p, area, category) for p in no_website]

    # Only keep operational businesses
    leads = [l for l in leads if l.get("business_status", "") != "PERMANENTLY_CLOSED"]
    print(f"  ✅ {len(leads)} qualified leads (operational, no website)")

    return leads


def discover_from_config(config_path: str, target_index: int | None = None):
    """Run discovery using config file."""
    api_key = os.getenv("APIFY_API_KEY")
    if not api_key or api_key == "apify_api_your_key_here":
        print("❌ Error: Set APIFY_API_KEY in your .env file")
        sys.exit(1)

    with open(config_path, "r") as f:
        config = json.load(f)

    output_dir = os.path.join(os.path.dirname(config_path), config.get("output_dir", "../output"))
    all_leads = []

    targets = config["targets"]
    if target_index is not None:
        targets = [targets[target_index]]

    for target in targets:
        area = target["area"]
        categories = target["categories"]

        print(f"\n{'='*60}")
        print(f"📍 Area: {area} (Priority: {target.get('priority', '?')})")
        print(f"   Categories: {len(categories)}")
        print(f"{'='*60}")

        for category in categories:
            leads = discover_single(api_key, area, category, output_dir)
            all_leads.extend(leads)
            time.sleep(2)  # Delay between categories

    # Save all collected leads
    if all_leads:
        save_leads(all_leads, output_dir)
    else:
        print("\n⚠️  No leads found. Try different categories or areas.")

    return all_leads


def main():
    parser = argparse.ArgumentParser(
        description="🔍 AutoWeb Lead Discovery — Find businesses without websites via Apify",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python discover.py --area "Ramapuram, Chennai" --category "restaurant"
  python discover.py --config ../agents/config.json --target 0
  python discover.py --config ../agents/config.json --all
        """
    )

    parser.add_argument("--config", type=str, help="Path to config.json file")
    parser.add_argument("--target", type=int, help="Target index from config (0-based)")
    parser.add_argument("--all", action="store_true", help="Run all targets from config")
    parser.add_argument("--area", type=str, help="Area to search (e.g., 'Ramapuram, Chennai')")
    parser.add_argument("--category", type=str, help="Business category to search")
    parser.add_argument("--output", type=str, default=None, help="Output directory")

    args = parser.parse_args()

    # Determine output directory
    script_dir = Path(__file__).resolve().parent
    default_output = script_dir.parent / "output"

    if args.config:
        discover_from_config(args.config, args.target if not args.all else None)
    elif args.area and args.category:
        api_key = os.getenv("APIFY_API_KEY")
        if not api_key:
            print("❌ Error: Set APIFY_API_KEY in your .env file")
            sys.exit(1)

        output_dir = args.output or str(default_output)
        leads = discover_single(api_key, args.area, args.category, output_dir)
        if leads:
            save_leads(leads, output_dir)
    else:
        parser.print_help()
        print("\n💡 Quick start:")
        print('   python discover.py --area "Ramapuram, Chennai" --category "restaurant"')


if __name__ == "__main__":
    main()

