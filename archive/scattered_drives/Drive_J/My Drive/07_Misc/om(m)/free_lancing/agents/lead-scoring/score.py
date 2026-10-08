#!/usr/bin/env python3
"""
AutoWeb Lead Scoring Agent
============================
Scores discovered leads as Hot / Warm / Cold based on reviews, rating, and activity.

Usage:
    python score.py --input ../output/leads.json
    python score.py --input ../output/leads.json --config ../agents/config.json
"""

import argparse
import json
import os
import sys
from pathlib import Path


def score_lead(lead: dict, scoring_config: dict) -> dict:
    """
    Score a lead based on configured thresholds.
    Returns the lead with added 'score', 'score_label', and 'score_reasons' fields.
    """
    rating = lead.get("rating", 0) or 0
    review_count = lead.get("review_count", 0) or 0
    has_phone = bool(lead.get("phone_national") or lead.get("phone_international"))
    has_photos = len(lead.get("photo_refs", [])) > 0

    score = 0
    reasons = []

    # ─── Rating score (0-30 points) ─────────────────────────────────────
    if rating >= 4.5:
        score += 30
        reasons.append(f"Excellent rating ({rating}⭐)")
    elif rating >= 4.0:
        score += 25
        reasons.append(f"Great rating ({rating}⭐)")
    elif rating >= 3.5:
        score += 15
        reasons.append(f"Good rating ({rating}⭐)")
    elif rating >= 3.0:
        score += 10
        reasons.append(f"Average rating ({rating}⭐)")
    elif rating > 0:
        score += 5
        reasons.append(f"Low rating ({rating}⭐)")

    # ─── Review count score (0-30 points) ────────────────────────────────
    if review_count >= 100:
        score += 30
        reasons.append(f"Very popular ({review_count} reviews)")
    elif review_count >= 50:
        score += 25
        reasons.append(f"Popular ({review_count} reviews)")
    elif review_count >= 20:
        score += 20
        reasons.append(f"Active ({review_count} reviews)")
    elif review_count >= 10:
        score += 15
        reasons.append(f"Some reviews ({review_count})")
    elif review_count >= 5:
        score += 10
        reasons.append(f"Few reviews ({review_count})")
    elif review_count > 0:
        score += 5
        reasons.append(f"Very few reviews ({review_count})")

    # ─── Contact info score (0-20 points) ────────────────────────────────
    if has_phone:
        score += 20
        reasons.append("Has phone number ✅")
    else:
        reasons.append("No phone number ❌")

    # ─── Photo presence score (0-10 points) ──────────────────────────────
    photo_count = len(lead.get("photo_refs", []))
    if photo_count >= 3:
        score += 10
        reasons.append(f"Has {photo_count} photos")
    elif photo_count > 0:
        score += 5
        reasons.append(f"Has {photo_count} photo(s)")

    # ─── Business status (0-10 points) ───────────────────────────────────
    if lead.get("business_status") == "OPERATIONAL":
        score += 10
        reasons.append("Business is operational")

    # ─── Determine label ─────────────────────────────────────────────────
    hot_config = scoring_config.get("hot", {})
    warm_config = scoring_config.get("warm", {})

    if (rating >= hot_config.get("min_rating", 4.0) and
        review_count >= hot_config.get("min_reviews", 20) and
        (has_phone or not hot_config.get("requires_phone", True))):
        label = "🔥 HOT"
    elif (rating >= warm_config.get("min_rating", 3.5) and
          review_count >= warm_config.get("min_reviews", 5) and
          (has_phone or not warm_config.get("requires_phone", True))):
        label = "🟡 WARM"
    else:
        label = "🔵 COLD"

    lead["score"] = score
    lead["score_label"] = label
    lead["score_reasons"] = reasons

    return lead


def score_all_leads(leads: list[dict], scoring_config: dict) -> list[dict]:
    """Score all leads and sort by score (highest first)."""
    scored = [score_lead(lead, scoring_config) for lead in leads]
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def print_summary(scored_leads: list[dict]):
    """Print a summary of scored leads."""
    hot = [l for l in scored_leads if "HOT" in l["score_label"]]
    warm = [l for l in scored_leads if "WARM" in l["score_label"]]
    cold = [l for l in scored_leads if "COLD" in l["score_label"]]

    print(f"\n{'='*60}")
    print(f"📊 Lead Scoring Summary")
    print(f"{'='*60}")
    print(f"  🔥 HOT leads:  {len(hot)} (priority outreach)")
    print(f"  🟡 WARM leads: {len(warm)} (second priority)")
    print(f"  🔵 COLD leads: {len(cold)} (low priority)")
    print(f"  📋 Total:      {len(scored_leads)}")

    if hot:
        print(f"\n{'─'*60}")
        print(f"🔥 Top HOT Leads:")
        print(f"{'─'*60}")
        for i, lead in enumerate(hot[:10], 1):
            print(f"  {i}. {lead['name']}")
            print(f"     📍 {lead['address']}")
            print(f"     ⭐ {lead['rating']} ({lead['review_count']} reviews)")
            phone = lead.get('phone_national') or lead.get('phone_international') or 'N/A'
            print(f"     📞 {phone}")
            print(f"     🔗 {lead['google_maps_url']}")
            print()

    if warm:
        print(f"\n{'─'*60}")
        print(f"🟡 Top WARM Leads:")
        print(f"{'─'*60}")
        for i, lead in enumerate(warm[:5], 1):
            print(f"  {i}. {lead['name']}")
            print(f"     ⭐ {lead['rating']} ({lead['review_count']} reviews)")
            phone = lead.get('phone_national') or lead.get('phone_international') or 'N/A'
            print(f"     📞 {phone}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description="📊 AutoWeb Lead Scoring — Prioritize your leads",
    )
    parser.add_argument("--input", type=str, default=None, help="Path to leads.json")
    parser.add_argument("--config", type=str, default=None, help="Path to config.json for scoring rules")
    parser.add_argument("--output", type=str, default=None, help="Path to output scored_leads.json")

    args = parser.parse_args()

    # Default paths
    script_dir = Path(__file__).resolve().parent
    default_input = script_dir.parent / "output" / "leads.json"
    default_output = script_dir.parent / "output" / "scored_leads.json"
    default_config = script_dir.parent / "agents" / "config.json"

    input_path = args.input or str(default_input)
    output_path = args.output or str(default_output)

    # Load scoring config
    scoring_config = {"hot": {"min_rating": 4.0, "min_reviews": 20, "requires_phone": True},
                      "warm": {"min_rating": 3.5, "min_reviews": 5, "requires_phone": True},
                      "cold": {"min_rating": 0, "min_reviews": 0, "requires_phone": False}}

    config_path = args.config or str(default_config)
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            scoring_config = config.get("scoring", scoring_config)

    # Load leads
    if not os.path.exists(input_path):
        print(f"❌ Error: No leads file found at {input_path}")
        print("   Run discover.py first to find leads.")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        leads = json.load(f)

    if not leads:
        print("⚠️  No leads to score.")
        sys.exit(0)

    print(f"📋 Loaded {len(leads)} leads from {input_path}")

    # Score leads
    scored = score_all_leads(leads, scoring_config)

    # Save scored leads
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved scored leads to {output_path}")

    # Print summary
    print_summary(scored)


if __name__ == "__main__":
    main()
