import requests
import json
import csv
import re
import time
import os

def fetch_foreign_researchers(max_results, filename):
    print(f"\n--- Fetching up to {max_results} highly-targeted leads for: {filename} ---")
    
    # Broad but relevant query to ensure we find enough people
    query = '("colonoscopy" OR "endoscopy" OR "polyp detection" OR "medical video" OR "medical image analysis") AND ("deep learning" OR "artificial intelligence" OR "YOLO")'
    
    # Target keywords user requested
    target_keywords = [
        "taiwan", "germany", " us ", "usa", "united states", 
        " uk ", "united kingdom", "dubai", "uae", "united arab emirates",
        "iit ", "indian institute of technology", "nit ", "national institute of technology",
        "stanford", "mit", "harvard", "oxford", "cambridge", "eth zurich"
    ]
    
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    cursor = "*"
    results = []
    global_emails = set()
    
    # Also load existing emails so we don't scrape the same people
    if os.path.exists("sent_emails.txt"):
        with open("sent_emails.txt", "r") as f:
            for line in f:
                if line.strip():
                    global_emails.add(line.strip().lower())
    
    while len(results) < max_results:
        params = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "cursorMark": cursor,
            "pageSize": 100
        }
        
        success = False
        for attempt in range(3):
            try:
                response = requests.get(url, params=params, timeout=30)
                if response.status_code == 200:
                    success = True
                    break
                else:
                    print(f"Error fetching data: HTTP {response.status_code}")
            except Exception as e:
                print(f"Request failed (attempt {attempt+1}): {e}")
                time.sleep(2)
                
        if not success:
            print("Failed to fetch data after 3 attempts.")
            break
            
        data = response.json()
        articles = data.get("resultList", {}).get("result", [])
        
        if not articles:
            print("No more articles found in Europe PMC.")
            break
            
        for article in articles:
            title = article.get("title", "")
            authors = article.get("authorList", {}).get("author", [])
            
            for author in authors:
                if "authorAffiliationDetailsList" in author:
                    affiliations = author["authorAffiliationDetailsList"].get("authorAffiliation", [])
                    for aff in affiliations:
                        affiliation_str = aff.get("affiliation", "")
                        
                        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', affiliation_str)
                        if email_match:
                            email = email_match.group(0).lower()
                            
                            # Check if affiliation matches our targets
                            aff_lower = affiliation_str.lower()
                            is_target = any(keyword in aff_lower for keyword in target_keywords)
                            
                            if is_target and email not in global_emails:
                                first_name = author.get("firstName", "")
                                last_name = author.get("lastName", "")
                                full_name = f"{first_name} {last_name}".strip()
                                clean_aff = affiliation_str.replace(email_match.group(0), "").strip(" .,;")
                                
                                results.append({
                                    "Name": full_name,
                                    "Email": email,
                                    "Affiliation": clean_aff,
                                    "Paper Title": title
                                })
                                global_emails.add(email)
                                
                                if len(results) >= max_results:
                                    break
                                    
            if len(results) >= max_results:
                break
                                
        cursor = data.get("nextCursorMark")
        if not cursor or cursor == "*":
            break
            
        time.sleep(0.5)
        print(f"Found {len(results)} highly-targeted researchers so far...")
        
    # Save to CSV
    filepath = os.path.join(os.getcwd(), filename)
    with open(filepath, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Name", "Email", "Affiliation", "Paper Title"])
        writer.writeheader()
        writer.writerows(results)
        
    print(f"\nDone! Saved {len(results)} contacts to {filename}")

if __name__ == "__main__":
    # Fetch 600 targeted leads
    fetch_foreign_researchers(600, "priority_5_foreign_and_top_institutions.csv")
