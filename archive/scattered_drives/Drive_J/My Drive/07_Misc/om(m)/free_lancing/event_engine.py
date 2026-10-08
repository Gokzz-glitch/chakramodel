import csv
import os
import datetime

SWAG_TARGETS_FILE = r"M:\free_lancing\swag_targets.csv"
LOG_FILE = r"M:\free_lancing\report.log"

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    with open(LOG_FILE, "a") as f:
        f.write(formatted + "\n")

# A curated list of known tech organizations that offer student travel grants, hackathon sponsorships, and event diversity funding.
# We will inject these into the outreach pipeline.
EVENT_TARGETS = [
    {
        "Company": "Linux Foundation (Diversity & Travel)",
        "Email": "scholarships@linuxfoundation.org",
        "Context": "I am looking for student travel funding/scholarships to attend upcoming Linux Foundation events like KubeCon. I'd love to showcase my open-source AI projects there.",
        "Type": "tech"
    },
    {
        "Company": "GitHub Education (Campus Experts)",
        "Email": "education@github.com",
        "Context": "I would love to learn if GitHub Education offers student grants or sponsorships to attend upcoming tech events or hackathons.",
        "Type": "tech"
    },
    {
        "Company": "Google Developers (Student Clubs/Events)",
        "Email": "google-dev-community-india@google.com",
        "Context": "I'm looking for opportunities to attend Google Developer events in India and was wondering if there are any student travel grants or accommodations available.",
        "Type": "tech"
    },
    {
        "Company": "MLH (Major League Hacking) Events",
        "Email": "hi@mlh.io",
        "Context": "I am an active hackathon participant and would love to know if MLH provides travel stipends or accommodations for students attending international hackathons.",
        "Type": "tech"
    },
    {
        "Company": "AWS Educate & Events",
        "Email": "aws-educate@amazon.com",
        "Context": "I heavily use AWS for my ML models and would love to attend AWS re:Invent or local AWS Summits. Do you offer student travel scholarships for these events?",
        "Type": "tech"
    }
]

def generate_event_leads():
    log("=== Starting Event & Travel Funding Engine ===")
    
    existing_emails = set()
    if os.path.exists(SWAG_TARGETS_FILE):
        with open(SWAG_TARGETS_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing_emails.add(row.get("Email", "").lower())
                
    new_rows = []
    added = 0
    for target in EVENT_TARGETS:
        if target["Email"].lower() not in existing_emails:
            new_rows.append(target)
            existing_emails.add(target["Email"].lower())
            added += 1
            
    if new_rows:
        file_exists = os.path.exists(SWAG_TARGETS_FILE)
        with open(SWAG_TARGETS_FILE, "a", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Company", "Email", "Context", "Type"])
            if not file_exists:
                writer.writeheader()
            for r in new_rows:
                writer.writerow(r)
                
    log(f"Added {added} event/travel funding targets to the campaign queue.")
    log("=== Finished Event Engine ===")

if __name__ == "__main__":
    generate_event_leads()
