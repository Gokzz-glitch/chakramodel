#!/usr/bin/env python3
"""
Automated AI/ML Research Internship & Research Assistant (RA) Monitor
Tailored for: Undergraduates in Computer Vision, Medical Imaging & Deep Learning
Priorities: Russia (Tier 1) > China & Hong Kong (Tier 2) > Global Medicine + AI (Tier 3)
"""

import os
import sys
import re
import json
import hashlib
import argparse
from datetime import datetime
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

# Ensure Windows terminal doesn't crash on unicode emojis
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def load_json(filepath, default_val=None):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Warning: Could not read {filepath}: {e}")
    return default_val if default_val is not None else {}

def save_json(filepath, data):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def compute_job_id(title, company, link):
    key = f"{title.strip().lower()}|{company.strip().lower()}|{link.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

def clean_html(raw_html):
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator=" ").strip()

def extract_links_from_cell(cell_html):
    soup = BeautifulSoup(cell_html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        links.append({"text": a.get_text(strip=True), "href": a["href"]})
    return links

def score_item(title, company, description, location, config):
    text_corpus = f"{title} {company} {description} {location}".lower()
    
    # Exclude non-technical false positives like "World Vision" charity
    if "world vision" in text_corpus and not any(k in text_corpus for k in ["computer vision", "segmentation", "deep learning", "pytorch", "neural"]):
        return 0, []

    score = 0
    matched_tags = []
    has_domain_or_tier = False

    # Priority Tiers
    tiers = config.get("priority_tiers", {})
    for tier_id, tier_info in tiers.items():
        weight = tier_info.get("score_weight", 10)
        for kw in tier_info.get("keywords", []):
            if re.search(r"\b" + re.escape(kw) + r"\b", text_corpus, re.IGNORECASE):
                score += weight
                matched_tags.append(tier_info.get("name", tier_id))
                has_domain_or_tier = True
                break

    # Domain Keywords (Medical Vision / Computer Vision)
    domains = config.get("domain_keywords", {})
    for dom_id, dom_info in domains.items():
        weight = dom_info.get("score_weight", 5)
        for kw in dom_info.get("keywords", []):
            if re.search(r"\b" + re.escape(kw) + r"\b", text_corpus, re.IGNORECASE):
                score += weight
                matched_tags.append(kw)
                has_domain_or_tier = True
                break

    # General AI/Research anchor keywords
    ai_research_anchors = ["research", "researcher", "scientist", "deep learning", "machine learning", "ai", "artificial intelligence", "perception", "robotics"]
    has_research_anchor = any(re.search(r"\b" + re.escape(k) + r"\b", text_corpus, re.IGNORECASE) for k in ai_research_anchors)

    # If it's a generic job with neither domain/tier nor AI research anchor, drop it
    if not (has_domain_or_tier or has_research_anchor):
        return 0, []

    # Role Keywords (Undergraduate / Intern / RA)
    roles = config.get("role_keywords", {})
    for role_id, role_info in roles.items():
        weight = role_info.get("score_weight", 5)
        for kw in role_info.get("keywords", []):
            if re.search(r"\b" + re.escape(kw) + r"\b", text_corpus, re.IGNORECASE):
                score += weight
                matched_tags.append(f"role:{kw}")
                break

    return score, list(set(matched_tags))

def parse_markdown_table_feed(source_info, config):
    name = source_info.get("name", "Markdown Source")
    url = source_info.get("url")
    print(f"[*] Fetching tracker: {name}...")
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[!] Received status {resp.status_code} for {url}")
            return items
        
        lines = resp.text.splitlines()
        for line in lines:
            if not line.strip().startswith("|") or line.strip().count("|") < 3:
                continue
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if not cols or any(h in cols[0].lower() for h in ["company", "organization", "name", "---"]):
                continue

            company_html = cols[0]
            title_html = cols[1] if len(cols) > 1 else ""
            loc_html = cols[2] if len(cols) > 2 else ""
            app_html = cols[3] if len(cols) > 3 else ""

            company_text = clean_html(company_html)
            title_text = clean_html(title_html)
            loc_text = clean_html(loc_html)

            # Find direct link
            links = extract_links_from_cell(app_html) or extract_links_from_cell(title_html) or extract_links_from_cell(company_html)
            link = links[0]["href"] if links else url

            # Skip generic non-intern/non-research rows if irrelevant
            combined = f"{company_text} {title_text} {loc_text}"
            score, tags = score_item(title_text, company_text, "", loc_text, config)

            min_score = config.get("search_settings", {}).get("min_relevance_score", 5)
            if score >= min_score:
                job_id = compute_job_id(title_text, company_text, link)
                items.append({
                    "id": job_id,
                    "title": title_text,
                    "company": company_text,
                    "location": loc_text,
                    "link": link,
                    "source": name,
                    "score": score,
                    "tags": tags,
                    "discovered_at": datetime.now().strftime("%Y-%m-%d")
                })
    except Exception as e:
        print(f"[!] Error parsing {name}: {e}")
    return items

def parse_rss_feed(source_info, config):
    name = source_info.get("name", "RSS Feed")
    url = source_info.get("url")
    print(f"[*] Fetching academic RSS: {name}...")
    items = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[!] Received status {resp.status_code} for {url}")
            return items
        
        root = ET.fromstring(resp.content)
        channel = root.find("channel")
        if channel is None:
            return items
        
        for item_node in channel.findall("item"):
            title = item_node.find("title").text if item_node.find("title") is not None else ""
            link = item_node.find("link").text if item_node.find("link") is not None else ""
            desc = item_node.find("description").text if item_node.find("description") is not None else ""
            
            clean_desc = clean_html(desc)
            score, tags = score_item(title, "Academic Lab / University", clean_desc, "Global", config)
            min_score = config.get("search_settings", {}).get("min_relevance_score", 5)

            if score >= min_score:
                job_id = compute_job_id(title, "Academic Lab", link)
                items.append({
                    "id": job_id,
                    "title": title,
                    "company": "Academic Lab / University",
                    "location": "Global / Remote",
                    "link": link,
                    "source": name,
                    "score": score,
                    "tags": tags,
                    "discovered_at": datetime.now().strftime("%Y-%m-%d")
                })
    except Exception as e:
        print(f"[!] Error parsing RSS feed {name}: {e}")
    return items

def generate_markdown_report(all_items, new_items, config, report_date):
    curated_portals = config.get("curated_lab_portals", [])
    
    # Sort items by score descending
    all_items = sorted(all_items, key=lambda x: x["score"], reverse=True)
    new_items_set = {it["id"] for it in new_items}

    lines = []
    lines.append(f"# 🛰️ Weekly AI/ML & Medical Vision Research Monitor")
    lines.append(f"**Report Generated:** {report_date}")
    lines.append(f"**Target Profile:** Undergraduate / Bachelor's Researcher in Computer Vision & Medical Imaging (Polyp & Tumor Segmentation, Endoscopy, Healthcare AI)")
    lines.append(f"**Priority Order:** 🇷🇺 Russia (Tier 1) > 🇨🇳 & 🇭🇰 China / HK (Tier 2) > 🌐 Global Medicine + AI (Tier 3)\n")
    
    lines.append(f"> [!NOTE]\n> Found **{len(all_items)}** highly relevant research opportunities, with **{len(new_items)} new opportunities** detected since last run.\n")

    # Section 1: Newly Discovered Opportunities
    lines.append("## ⚡ 1. Newly Discovered Postings This Week")
    if new_items:
        lines.append("| Status | Score | Role / Title | Company / Lab | Location | Tags | Application Link |")
        lines.append("| :---: | :---: | :--- | :--- | :--- | :--- | :--- |")
        for it in sorted(new_items, key=lambda x: x["score"], reverse=True):
            tags_str = ", ".join(it["tags"][:3])
            link_md = f"[Apply / Inspect]({it['link']})"
            lines.append(f"| **NEW** | `{it['score']}` | {it['title']} | {it['company']} | {it['location']} | `{tags_str}` | {link_md} |")
    else:
        lines.append("_No brand new postings recorded today; tracking continues on all active cycles below._")
    lines.append("\n---\n")

    # Section 2: Top Ranked Positions by Region / Domain
    lines.append("## 🏆 2. Top-Scoring Active Openings")
    lines.append("| Relevance | Title / Role | Institution / Company | Location | Tags | Direct Link |")
    lines.append("| :---: | :--- | :--- | :--- | :--- | :--- |")
    for it in all_items[:25]:  # Top 25
        status_prefix = "**[NEW]** " if it["id"] in new_items_set else ""
        tags_str = ", ".join(it["tags"][:3])
        link_md = f"[View Listing]({it['link']})"
        lines.append(f"| `{it['score']}` | {status_prefix}{it['title']} | {it['company']} | {it['location']} | `{tags_str}` | {link_md} |")
    lines.append("\n---\n")

    # Section 3: Curated Target Laboratories & Direct PI Contact
    lines.append("## 🏛️ 3. Priority Curated Lab Portals (Direct Undergraduate Application)")
    lines.append("Direct cold outreach to lab PIs or checking institutional student portals is the #1 method to secure research assistantships in medical computer vision:\n")

    # Group curated by Tier
    tier_groups = {}
    for p in curated_portals:
        t = p.get("tier", "Other")
        tier_groups.setdefault(t, []).append(p)

    for tier_name, portals in tier_groups.items():
        lines.append(f"### {tier_name}")
        lines.append("| Institution / Organization | Laboratory / Unit | Location | Direct Link | Strategy / Key Info |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")
        for p in portals:
            link_md = f"[Official Portal]({p['url']})"
            lines.append(f"| **{p['institution']}** | {p['lab']} | {p['location']} | {link_md} | {p['notes']} |")
        lines.append("")

    lines.append("\n---\n")

    # Section 4: Cold Outreach Email Template
    lines.append("## ✉️ 4. Tailored Cold Email Template (Medical Image Segmentation)")
    lines.append("```markdown")
    lines.append("Subject: Prospective Research Intern / RA: [Your Name] | Polyp Segmentation & PyTorch")
    lines.append("")
    lines.append("Dear Professor [Last Name],")
    lines.append("")
    lines.append("I have been following your lab's recent work on [mention 1 paper, e.g. robust endoscopic polyp segmentation / boundary loss].")
    lines.append("I am an undergraduate student in [Your Major] with hands-on experience building deep learning pipelines for medical image segmentation in PyTorch (specifically colonoscopy polyp segmentation, boundary-aware loss functions, and data augmentations).")
    lines.append("")
    lines.append("You can inspect my benchmarks, code, and project documentation here: [GitHub / Portfolio Link].")
    lines.append("I am eager to contribute to [Lab Name]'s upcoming research as an Undergraduate Research Intern or Visiting Research Assistant for [e.g., Summer 2027 / 6-month rotation].")
    lines.append("")
    lines.append("Would you be open to a 10-minute introductory call, or may I share a brief 1-page research statement? My CV is attached.")
    lines.append("")
    lines.append("Sincerely,")
    lines.append("[Your Name]")
    lines.append("[GitHub / LinkedIn / Google Scholar]")
    lines.append("```")

    return "\n".join(lines)

def run_monitor(config_path=DEFAULT_CONFIG_PATH):
    print("=" * 65)
    print("🚀 Starting AI/ML Research Internship & RA Monitor")
    print(f"⏰ Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    config = load_json(config_path)
    if not config:
        print("[!] Failed to load config.json, exiting.")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    seen_jobs_path = os.path.join(DATA_DIR, "seen_jobs.json")
    seen_jobs = load_json(seen_jobs_path, default_val={})

    discovered_items = []

    # 1. Parse GitHub Markdown trackers
    github_sources = config.get("online_sources", {}).get("github_trackers", [])
    for src in github_sources:
        items = parse_markdown_table_feed(src, config)
        discovered_items.extend(items)
        print(f"  -> Found {len(items)} matched entries from {src.get('name')}")

    # 2. Parse RSS feeds
    rss_sources = config.get("online_sources", {}).get("rss_feeds", [])
    for src in rss_sources:
        items = parse_rss_feed(src, config)
        discovered_items.extend(items)
        print(f"  -> Found {len(items)} matched entries from {src.get('name')}")

    # Deduplicate items in current batch
    unique_items = {}
    for it in discovered_items:
        jid = it["id"]
        if jid not in unique_items or it["score"] > unique_items[jid]["score"]:
            unique_items[jid] = it

    all_items = list(unique_items.values())
    print(f"[*] Total unique matching opportunities in current run: {len(all_items)}")

    # Check for new items
    new_items = []
    current_timestamp = datetime.now().isoformat()
    for it in all_items:
        jid = it["id"]
        if jid not in seen_jobs:
            new_items.append(it)
            seen_jobs[jid] = {
                "title": it["title"],
                "company": it["company"],
                "score": it["score"],
                "first_seen": current_timestamp
            }

    print(f"[*] New opportunities discovered: {len(new_items)}")
    save_json(seen_jobs_path, seen_jobs)

    # Generate Reports
    today_str = datetime.now().strftime("%Y-%m-%d")
    report_md = generate_markdown_report(all_items, new_items, config, today_str)

    # Save dated report and latest report
    dated_report_path = os.path.join(REPORTS_DIR, f"report_{today_str}.md")
    latest_report_path = os.path.join(REPORTS_DIR, "latest_weekly_report.md")

    with open(dated_report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    with open(latest_report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    print(f"[✓] Saved dated report: {dated_report_path}")
    print(f"[✓] Saved latest report: {latest_report_path}")
    print("=" * 65)
    print("✅ Monitor run complete!")
    print("=" * 65)

    return all_items, new_items

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI/ML Research Internship Monitor")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Path to config.json")
    args = parser.parse_args()
    run_monitor(args.config)
