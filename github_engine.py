import requests
import csv
import os
from datetime import datetime

GITHUB_SEARCH_URL = "https://api.github.com/search/users"
USER_URL = "https://api.github.com/users/{}"
SWAG_TARGETS_FILE = r"M:\free_lancing\swag_targets.csv"

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def scrape_github_devrels():
    log("=== Starting GitHub DevRel Scraper ===")
    
    # We search for users with "DevRel" or "Developer Advocate"
    queries = ["DevRel", "Developer Advocate", "Developer Relations"]
    
    added_count = 0
    
    # Check existing emails to prevent duplicates
    existing_emails = set()
    if os.path.exists(SWAG_TARGETS_FILE):
        with open(SWAG_TARGETS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_emails.add(row.get("Email", "").lower())
                
    new_rows = []
    headers = {"Accept": "application/vnd.github.v3+json"}
    
    try:
        # Just pick the first query for the daily run to avoid rate limits
        q = "Developer Advocate followers:>100"
        log(f"Searching GitHub for: {q}")
        
        resp = requests.get(GITHUB_SEARCH_URL, params={"q": q, "per_page": 10}, headers=headers)
        if resp.status_code == 200:
            users = resp.json().get("items", [])
            for u in users:
                username = u.get("login")
                # Fetch detailed profile to get email
                prof_resp = requests.get(USER_URL.format(username), headers=headers)
                if prof_resp.status_code == 200:
                    profile = prof_resp.json()
                    email = profile.get("email")
                    company = profile.get("company")
                    name = profile.get("name") or username
                    
                    if email and email.lower() not in existing_emails:
                        if company:
                            # Clean up company string (often starts with @)
                            company = company.strip("@").strip()
                            display_name = f"{company} DevRel ({name})"
                        else:
                            display_name = f"{name} (DevRel)"
                        
                        # Phase 1: Fetch their most recently updated repository for LLM personalization
                        latest_repo = "your amazing projects"
                        try:
                            repos_resp = requests.get(f"https://api.github.com/users/{username}/repos?sort=updated&per_page=1", headers=headers)
                            if repos_resp.status_code == 200 and len(repos_resp.json()) > 0:
                                latest_repo = repos_resp.json()[0].get("name", "your latest project")
                        except Exception as e:
                            pass
                            
                        new_rows.append({
                            "Company": display_name,
                            "Email": email,
                            "Context": f"Found your amazing work on GitHub as a Developer Advocate. I was specifically looking at your recent work on the '{latest_repo}' repository and it blew me away! Huge fan of what you do at {company or 'your organization'}.",
                            "Type": "brand"
                        })
                        existing_emails.add(email.lower())
                        added_count += 1
                        
                        # Only add up to 2 per day to slowly trickle them in and avoid massive spam
                        if added_count >= 2:
                            break
        else:
            log(f"GitHub API Error: {resp.status_code} - {resp.text}")
            
    except Exception as e:
        log(f"Error scraping GitHub: {e}")
        
    if new_rows:
        file_exists = os.path.exists(SWAG_TARGETS_FILE)
        with open(SWAG_TARGETS_FILE, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Company", "Email", "Context", "Type"])
            if not file_exists:
                writer.writeheader()
            for r in new_rows:
                writer.writerow(r)
                
    log(f"=== Added {added_count} new DevRel targets to {SWAG_TARGETS_FILE} ===")

if __name__ == "__main__":
    scrape_github_devrels()
