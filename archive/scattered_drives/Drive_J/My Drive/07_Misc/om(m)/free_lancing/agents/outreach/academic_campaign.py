import os
import csv
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

# Paths
CHAKRA_ENV = Path("M:/chakramodel/.env")
CSV_PATH = Path("M:/chakramodel/priority_1_colonoscopy_ai.csv")
SENT_LOG = Path("M:/free_lancing/output/sent_academic_emails.txt")

# Configuration
BATCH_SIZE = 15  # Increased batch size
NUM_BATCHES = 6  # Total number of batches
TOTAL_LIMIT = BATCH_SIZE * NUM_BATCHES
EMAIL_DELAY = 5  # Seconds between emails within a batch
BATCH_DELAY = 60  # Seconds between batches

def load_env(filepath):
    env_vars = {}
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()
    return env_vars

def get_sent_emails():
    if not SENT_LOG.exists():
        return set()
    with open(SENT_LOG, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def log_sent_email(email):
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SENT_LOG, "a", encoding="utf-8") as f:
        f.write(email + "\n")

def create_email_content(name, affiliation, paper_title):
    subject = f"Elevating your research visibility online"
    
    body = f"""
    <div style="font-family: Arial, sans-serif; font-size: 14px; color: #222; line-height: 1.7;">
        <p>Dear {name},</p>

        <p>I recently came across your paper, <i>"{paper_title}"</i>, and was deeply impressed by your contributions to the field at {affiliation}. As AI in medical imaging advances, it's becoming increasingly vital for researchers to showcase their work, datasets, and lab achievements clearly.</p>

        <p>We specialize in designing elite, lightning-fast static websites tailored specifically for academic labs, personal portfolios, and research groups. A dedicated professional website amplifies your research visibility, helps attract prospective students and grants, and serves as a permanent hub for your publications.</p>

        <p>Our bespoke web development service starts at just $50 (or ₹4,000) for a fully custom, mobile-responsive design—with absolutely no ongoing hosting fees.</p>

        <p>I would love to create a tailored mockup for your lab's digital presence. Please let me know if you would be open to a brief conversation this week.</p>

        <p>Best regards,<br><br>
        <b>Gokul Rajasekar</b><br>
        Founder, AutoWeb Solutions
        </p>
    </div>
    """
    return subject, body

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email_gmail(to_email, subject, body, sender_email, app_password):
    msg = MIMEMultipart()
    msg['From'] = f"Gokul Rajasekar <{sender_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    
    # Attach HTML body
    msg.attach(MIMEText(body, 'html'))
    
    try:
        # Try port 465 (SSL) which might bypass port 587 blocks
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10)
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

def main():
    print("🚀 Starting Academic Outreach Automation (via direct Gmail SMTP)...")
    
    # Load credentials
    env_vars = load_env(CHAKRA_ENV)
    sender_email = env_vars.get("SENDER_EMAIL")
    app_password = env_vars.get("GMAIL_APP_PASSWORD")
    
    if not sender_email or not app_password:
        print("❌ Error: Missing SENDER_EMAIL or GMAIL_APP_PASSWORD in M:/chakramodel/.env")
        return
        
    sent_emails = get_sent_emails()
    leads = []
    
    if not CSV_PATH.exists():
        print(f"❌ Error: Could not find CSV at {CSV_PATH}")
        return
        
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            leads.append(row)
            
    print(f"📋 Loaded {len(leads)} leads from {CSV_PATH.name}")
    print(f"⚙️  Configuration: {NUM_BATCHES} batches of {BATCH_SIZE} emails ({TOTAL_LIMIT} total)")
    
    sent_count = 0
    batch_count = 1
    
    for lead in leads:
        email = lead.get("Email", "").strip()
        name = lead.get("Name", "").strip()
        affiliation = lead.get("Affiliation", "").strip()
        paper_title = lead.get("Paper Title", "").strip()
        
        if not email or email in sent_emails:
            continue
            
        print(f"\n[Batch {batch_count}/{NUM_BATCHES}] 📧 Preparing to email: {name} ({email})")
        subject, body = create_email_content(name, affiliation, paper_title)
        
        success = send_email_gmail(email, subject, body, sender_email, app_password)
        
        if success:
            print(f"✅ Email sent successfully to {email}")
            log_sent_email(email)
            sent_emails.add(email)
            sent_count += 1
            
            if sent_count >= TOTAL_LIMIT:
                print(f"\n✋ Reached total limit of {TOTAL_LIMIT} emails ({NUM_BATCHES} batches of {BATCH_SIZE}).")
                break
                
            if sent_count % BATCH_SIZE == 0:
                print(f"\n📦 Batch {batch_count} complete! Waiting {BATCH_DELAY} seconds before next batch...")
                time.sleep(BATCH_DELAY)
                batch_count += 1
            else:
                print(f"⏳ Waiting {EMAIL_DELAY} seconds before next email...")
                time.sleep(EMAIL_DELAY)
                
    print(f"\n🎉 Automation Complete! Total emails sent today: {sent_count}")

if __name__ == "__main__":
    main()
