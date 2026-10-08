import requests
import json
import csv
import re
import time

def fetch_researchers(query, max_results=400):
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    cursor = "*"
    results = []
    
    print(f"Fetching papers for query: {query}")
    
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
                        
                        # Extract email using regex if present
                        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', affiliation_str)
                        if email_match:
                            email = email_match.group(0)
                            first_name = author.get("firstName", "")
                            last_name = author.get("lastName", "")
                            full_name = f"{first_name} {last_name}".strip()
                            
                            # Clean up affiliation by removing the email part
                            clean_aff = affiliation_str.replace(email, "").strip(" .,;")
                            
                            # Add to results if email not already present
                            if not any(r['Email'] == email for r in results):
                                results.append({
                                    "Name": full_name,
                                    "Email": email,
                                    "Affiliation": clean_aff,
                                    "Paper Title": title
                                })
                                
        cursor = data.get("nextCursorMark")
        if not cursor or cursor == "*":
            break
            
        time.sleep(0.5)
        print(f"Found {len(results)} researchers with emails so far...")
        
        if len(results) >= max_results:
            break
            
    return results[:max_results]

if __name__ == "__main__":
    query = '("colonoscopy" OR "polyp detection") AND ("deep learning" OR "artificial intelligence" OR "YOLO")'
    researchers = fetch_researchers(query, max_results=400)
    
    csv_file = "researcher_leads.csv"
    with open(csv_file, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Name", "Email", "Affiliation", "Paper Title"])
        writer.writeheader()
        writer.writerows(researchers)
        
    print(f"\nSuccessfully saved {len(researchers)} contacts to {csv_file}")
