import requests
import json
import csv
import re
import time
import os

def fetch_researchers(query, max_results, filename):
    print(f"\n--- Fetching up to {max_results} leads for: {filename} ---")
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    cursor = "*"
    results = []
    
    while len(results) < max_results:
        params = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "cursorMark": cursor,
            "pageSize": 100
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code != 200:
                print("Error fetching data")
                break
        except Exception as e:
            print("Request failed:", e)
            break
            
        data = response.json()
        articles = data.get("resultList", {}).get("result", [])
        
        if not articles:
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
                            email = email_match.group(0)
                            first_name = author.get("firstName", "")
                            last_name = author.get("lastName", "")
                            full_name = f"{first_name} {last_name}".strip()
                            clean_aff = affiliation_str.replace(email, "").strip(" .,;")
                            
                            # Deduplicate by email globally
                            if not any(r['Email'] == email for r in results) and email not in global_emails:
                                results.append({
                                    "Name": full_name,
                                    "Email": email,
                                    "Affiliation": clean_aff,
                                    "Paper Title": title
                                })
                                global_emails.add(email)
                                
        cursor = data.get("nextCursorMark")
        if not cursor or cursor == "*":
            break
            
        time.sleep(0.5)
        print(f"Found {len(results)} researchers so far...")
        
        if len(results) >= max_results:
            break
            
    # Save to CSV
    filepath = os.path.join(os.getcwd(), filename)
    with open(filepath, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Name", "Email", "Affiliation", "Paper Title"])
        writer.writeheader()
        writer.writerows(results[:max_results])
        
    print(f"Saved {min(len(results), max_results)} contacts to {filename}")

if __name__ == "__main__":
    global_emails = set()
    
    # Priority 1: Exact match (Colonoscopy AI)
    q1 = '("colonoscopy" OR "polyp detection") AND ("deep learning" OR "artificial intelligence" OR "YOLO")'
    fetch_researchers(q1, 100, "priority_1_colonoscopy_ai.csv")
    
    # Priority 2: General Endoscopy
    q2 = '("endoscopy" OR "gastrointestinal") AND ("deep learning" OR "artificial intelligence")'
    fetch_researchers(q2, 100, "priority_2_endoscopy_ai.csv")
    
    # Priority 3: Medical Video / YOLO
    q3 = '("medical video" OR "surgical video") AND ("YOLO" OR "object detection" OR "temporal consistency")'
    fetch_researchers(q3, 100, "priority_3_medical_video_ai.csv")
    
    # Priority 4: General Medical Vision
    q4 = '("medical image analysis" OR "computer vision") AND ("deep learning" OR "artificial intelligence") AND ("disease" OR "diagnosis")'
    fetch_researchers(q4, 100, "priority_4_general_med_vision.csv")
    
    print("\nAll lead generation complete!")
