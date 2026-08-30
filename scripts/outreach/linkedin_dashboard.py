import csv, os, json
from datetime import datetime
import urllib.parse

TARGET_FILES = [
    "priority_5_foreign_and_top_institutions.csv",
    "priority_1_colonoscopy_ai.csv",
    "priority_2_endoscopy_ai.csv"
]
LOG_FILE = "linkedin_contacted.txt"
OUTPUT_HTML = "linkedin_today.html"
DAILY_LIMIT = 20

def load_contacted():
    if not os.path.exists(LOG_FILE): return set()
    with open(LOG_FILE, encoding="utf-8") as f:
        return set(line.strip().lower() for line in f if line.strip())

def append_contacted(emails):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        for email in emails:
            if email:
                f.write(email.lower() + "\n")

def read_leads():
    leads = []
    for f in TARGET_FILES:
        if not os.path.exists(f): continue
        with open(f, encoding="utf-8") as file:
            for row in csv.DictReader(file):
                leads.append(row)
    return leads

def main():
    contacted = load_contacted()
    all_leads = read_leads()
    
    today_targets = []
    for lead in all_leads:
        email = lead.get("Email", "").strip().lower()
        # Fallback to name if email is empty for tracking
        track_key = email if email else lead.get("Name", "").strip().lower()
        
        if not track_key or track_key in contacted:
            continue
        
        lead["track_key"] = track_key
        today_targets.append(lead)
        if len(today_targets) >= DAILY_LIMIT:
            break
            
    if not today_targets:
        print("No more leads found!")
        return

    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>LinkedIn Outreach - {datetime.now().strftime('%Y-%m-%d')}</title>
        <style>
            body {{ font-family: -apple-system, system-ui, sans-serif; line-height: 1.6; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f3f2ef; }}
            .header {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            .card {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; flex-direction: column; gap: 10px; transition: opacity 0.3s; }}
            .card.done {{ opacity: 0.4; background: #e8e8e8; }}
            .info-row {{ display: flex; justify-content: space-between; align-items: baseline; }}
            .name {{ font-size: 1.2em; font-weight: bold; color: #0a66c2; text-decoration: none; }}
            .affiliation {{ color: #666; font-size: 0.9em; }}
            .paper {{ font-style: italic; color: #444; background: #f8f9fa; padding: 10px; border-radius: 4px; border-left: 3px solid #0a66c2; }}
            .buttons {{ display: flex; gap: 10px; margin-top: 10px; }}
            button {{ padding: 8px 16px; border: none; border-radius: 16px; font-weight: 600; cursor: pointer; transition: 0.2s; }}
            .btn-search {{ background: #0a66c2; color: white; text-decoration: none; padding: 8px 16px; border-radius: 16px; font-weight: 600; font-size: 13.33px; }}
            .btn-copy {{ background: #fff; color: #0a66c2; border: 1px solid #0a66c2; }}
            .btn-copy:hover {{ background: #f0f7ff; }}
            .btn-done {{ background: #057642; color: white; margin-left: auto; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>LinkedIn Daily Target: {len(today_targets)} Researchers</h1>
            <p>1. Click <b>Search</b> to find them on LinkedIn.<br>
            2. Click <b>Copy Request</b> and paste into the connection note (max 300 chars).<br>
            3. If they accept, message them with the <b>Follow-Up</b>.<br>
            4. Click <b>Mark Done</b> to cross them off today's list visually.</p>
        </div>
    """
    
    for i, lead in enumerate(today_targets):
        name = lead.get("Name", "Researcher")
        first_name = name.split()[0] if name else "there"
        affiliation = lead.get("Affiliation", "")
        paper = lead.get("Paper Title", "your recent research")
        search_query = urllib.parse.quote(f"{name} {affiliation}")
        
        req_msg = f"Hi {first_name}, I'm an AI undergrad building PolypNet-3D: a YOLOv8+Kalman pipeline hitting 49 FPS for real-time colonoscopy polyp detection. I admire your work and would love to connect to follow your research!"
        fup_msg = f"Thanks for connecting! I'm actively looking for a research internship in Computer Vision/Medical Imaging. My recent work focuses on solving frame-flickering in endoscopic feeds using cascaded YOLOv8n & PraNet with custom state machines.\n\nYou can view my portfolio & code here: https://github.com/Gokzz-glitch\nI'd be incredibly grateful if you have any feedback on my approach or know of any openings in your lab."
        
        # Escape quotes for JS string
        req_msg_js = req_msg.replace("'", "\\'").replace('"', '\\"')
        fup_msg_js = fup_msg.replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')
        
        html += f"""
        <div class="card" id="card-{i}">
            <div class="info-row">
                <div>
                    <a href="https://www.linkedin.com/search/results/all/?keywords={search_query}" target="_blank" class="name">{name}</a>
                    <span class="affiliation"> - {affiliation}</span>
                </div>
                <a href="https://www.linkedin.com/search/results/all/?keywords={search_query}" target="_blank" class="btn-search">🔍 Search LinkedIn</a>
            </div>
            <div class="paper">"{paper}"</div>
            <div class="buttons">
                <button class="btn-copy" onclick="copyText('{req_msg_js}')">📋 Copy Request (300 char)</button>
                <button class="btn-copy" onclick="copyText('{fup_msg_js}')">📋 Copy Follow-Up</button>
                <button class="btn-done" onclick="document.getElementById('card-{i}').classList.add('done')">✓ Mark Done</button>
            </div>
        </div>
        """
        
    html += """
        <script>
            function copyText(text) {
                navigator.clipboard.writeText(text).then(function() {
                    console.log('Copied');
                });
            }
        </script>
    </body>
    </html>
    """
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
        
    # Mark them as checked out for today
    append_contacted([l["track_key"] for l in today_targets])
    print(f"Generated {OUTPUT_HTML} with {len(today_targets)} targets.")
    print(f"Open file:///{os.path.abspath(OUTPUT_HTML).replace(chr(92), '/')} in your browser to begin.")

if __name__ == "__main__":
    main()
