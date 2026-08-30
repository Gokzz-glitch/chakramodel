import urllib.request
import urllib.parse
import json
import csv
import os
import re
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import time

PRIORITY_FILE = "priority_5_foreign_and_top_institutions.csv"
DASHBOARD_FILE = "daily_opportunities.html"

# Keywords for new research papers
RESEARCH_KEYWORDS = [
    "colonoscopy polyp detection",
    "endoscopy artificial intelligence",
    "YOLO medical imaging",
    "surgical video analysis"
]

# Keywords for job search
JOB_KEYWORDS = [
    "Computer Vision Intern",
    "Machine Learning Intern",
    "Medical AI Internship",
    "Edge AI Engineer Intern"
]

def search_pubmed(query, max_results=10):
    print(f"[*] Searching PubMed for: {query}")
    try:
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={urllib.parse.quote(query)}&retmode=json&retmax={max_results}"
        req = urllib.request.urlopen(url)
        res = json.loads(req.read().decode('utf-8'))
        id_list = res.get('esearchresult', {}).get('idlist', [])
        return id_list
    except Exception as e:
        print(f"[-] PubMed search failed: {e}")
        return []

def fetch_pubmed_details(id_list):
    if not id_list: return []
    ids = ",".join(id_list)
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={ids}&retmode=xml"
    try:
        req = urllib.request.urlopen(url)
        xml_data = req.read()
        root = ET.fromstring(xml_data)
        
        results = []
        for article in root.findall('.//PubmedArticle'):
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else "Unknown Title"
            
            for author in article.findall('.//Author'):
                last_name = author.find('LastName')
                last_name = last_name.text if last_name is not None else ""
                first_name = author.find('ForeName')
                first_name = first_name.text if first_name is not None else ""
                
                name = f"{first_name} {last_name}".strip()
                if not name: continue
                
                affil_elem = author.find('.//Affiliation')
                affiliation = affil_elem.text if affil_elem is not None else ""
                
                # Extract email using regex
                email = ""
                if affiliation:
                    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', affiliation)
                    if match:
                        email = match.group(0)
                        
                if email:
                    results.append({
                        "Name": name,
                        "Email": email.lower(),
                        "Affiliation": affiliation[:100].replace('\n', ' ') + "...",
                        "Paper Title": title
                    })
        return results
    except Exception as e:
        print(f"[-] PubMed fetch failed: {e}")
        return []

def append_leads_to_csv(new_leads):
    if not new_leads: return 0
    
    existing_emails = set()
    if os.path.exists(PRIORITY_FILE):
        with open(PRIORITY_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_emails.add(row.get("Email", "").lower())
                
    added = 0
    file_exists = os.path.exists(PRIORITY_FILE)
    
    with open(PRIORITY_FILE, "a", encoding="utf-8", newline="") as f:
        fieldnames = ["Name", "Email", "Affiliation", "Paper Title"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
            
        for lead in new_leads:
            if lead["Email"] not in existing_emails:
                writer.writerow(lead)
                existing_emails.add(lead["Email"])
                added += 1
    return added

def generate_dashboard():
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Daily Opportunities</title>
        <style>
            body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: #f4f7f6; }}
            h1 {{ color: #2c3e50; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            a.btn {{ display: inline-block; padding: 10px 15px; background: #3498db; color: white; text-decoration: none; border-radius: 4px; margin-right: 10px; margin-bottom: 10px; }}
            a.btn:hover {{ background: #2980b9; }}
            .linkedin {{ background: #0077b5; }}
            .google {{ background: #ea4335; }}
        </style>
    </head>
    <body>
        <h1>Opportunities Dashboard - {datetime.now().strftime('%Y-%m-%d')}</h1>
        <div class="card">
            <h2>Internship Search Links</h2>
            <p>Click these links to see live internship postings updated today:</p>
    """
    
    for kw in JOB_KEYWORDS:
        html += f"<h3>{kw}</h3>"
        li_query = urllib.parse.quote(kw)
        go_query = urllib.parse.quote(kw + " jobs")
        html += f"<a class='btn linkedin' href='https://www.linkedin.com/jobs/search/?keywords={li_query}&f_TPR=r86400' target='_blank'>LinkedIn Jobs (Past 24h)</a>"
        html += f"<a class='btn google' href='https://www.google.com/search?q={go_query}&ibp=htl;jobs' target='_blank'>Google Jobs</a><br>"

    html += """
        </div>
    </body>
    </html>
    """
    
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[*] Generated {DASHBOARD_FILE}")

def main():
    print("========================================")
    print(" OPPORTUNITY ENGINE ")
    print("========================================")
    
    # 1. Generate Job Dashboard
    generate_dashboard()
    
    # 2. Mine new researchers from PubMed
    total_added = 0
    for kw in RESEARCH_KEYWORDS:
        ids = search_pubmed(kw, max_results=15)
        if ids:
            leads = fetch_pubmed_details(ids)
            added = append_leads_to_csv(leads)
            total_added += added
            print(f"    -> Found {added} new unique researchers for '{kw}'")
        time.sleep(1) # Rate limit
        
    print(f"[*] Engine finished. Added {total_added} total new researchers to the email campaign queue.")
    
if __name__ == "__main__":
    main()
