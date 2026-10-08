"""
MASTER CAMPAIGN SCHEDULER
Reads internship_providers.csv, paper_authors.csv, researchers.csv
Sends in strict priority order: Tier1 → Tier2 → Tier3
Enforces Gmail's safe daily limit of 100 emails/day (well under the 500 hard cap)
Waits 24 hours between each day's batch automatically

Run: python master_campaign.py
"""

import csv, time, sys, os, json, random, smtplib, urllib.request, urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SENT_LOG        = "sent_emails.txt"
DAILY_LIMIT     = 100          # Safe cap (Gmail hard limit = 500/day)
BATCH_SLEEP     = 86400        # 24 hours between days
EMAIL_MIN_WAIT  = 20           # seconds between emails
EMAIL_MAX_WAIT  = 40

# ==========================================
# LOAD ENV
# ==========================================
def load_env():
    if not os.path.exists(".env"):
        print("ERROR: .env file not found."); sys.exit(1)
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ[k.strip()] = v.strip()

load_env()
SENDER_EMAIL       = os.environ.get("SENDER_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
BREVO_API_KEY      = os.environ.get("BREVO_API_KEY")
SENDER_NAME        = "Gokul R"

# ==========================================
# 3 EMAIL VARIANTS (rotated)
# ==========================================
SUBJECTS = [
    "Quick question about your work on {paper_title}",
    "Your research on {paper_title} — reaching out",
    "PolypNet-3D & your work on {paper_title}",
]

BODY_RESEARCHER = """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.7;">
  <p>Hi Dr. {last_name},</p>
  <p>I came across your work on <i>"{paper_title}"</i> and it immediately resonated with what my team has been building.</p>
  <p>I'm Gokul R, a final-year undergrad in AI & ML at Easwari Engineering College, Chennai. We've been developing <b>PolypNet-3D</b> — a real-time colonoscopy system that fixes the bounding-box flickering problem in live polyp detection by pairing YOLOv8 with a Kalman filter for temporal consistency. The code is fully open-source.</p>
  <p>I'm actively looking for a <b>research internship</b> in medical imaging or computer vision. If you have openings, or know someone who might, I'd be very grateful for a pointer.</p>
  <p>Thanks so much for your time.</p>
  <p>Best,<br><b>Gokul R</b><br>
  Undergrad Researcher · AI & ML · Easwari Engineering College, Chennai<br>
  <a href="https://github.com/Gokzz-glitch">GitHub</a> ·
  <a href="https://github.com/Gokzz-glitch/chakramodel">PolypNet-3D</a></p>
</div>"""

BODY_INTERNSHIP = """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.7;">
  <p>Hi,</p>
  <p>I'm Gokul R, a final-year undergraduate in AI & Machine Learning at Easwari Engineering College, Chennai. I'm reaching out about <b>research internship opportunities</b> at {affiliation}.</p>
  <p>I've been building <b>PolypNet-3D</b> — an open-source real-time polyp detection system for colonoscopy video that combines YOLOv8 for per-frame detection with Kalman filtering for temporal consistency. Our results on CVC-ClinicVideoDB show significant reduction in bounding-box flickering, a problem that actively reduces clinician trust in AI screening.</p>
  <p>I bring strong skills in PyTorch, object detection (YOLO series), video processing, and medical image datasets. I'm comfortable working remotely across time zones and can commit full-time.</p>
  <p>I've attached a brief overview of the project. Would love to discuss if there's any fit!</p>
  <p>Best regards,<br><b>Gokul R</b><br>
  Undergrad Researcher · AI & ML · Easwari Engineering College, Chennai<br>
  <a href="https://github.com/Gokzz-glitch">GitHub</a> ·
  <a href="https://github.com/Gokzz-glitch/chakramodel">PolypNet-3D</a></p>
</div>"""

# ==========================================
# HELPERS
# ==========================================
def load_sent():
    if not os.path.exists(SENT_LOG): return set()
    with open(SENT_LOG) as f:
        return set(l.strip().lower() for l in f if l.strip())

def log_sent(email):
    with open(SENT_LOG, 'a') as f:
        f.write(email.lower() + '\n')

def connect_gmail():
    s = smtplib.SMTP("smtp.gmail.com", 587)
    s.starttls()
    s.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
    return s

def send_gmail(server, to_email, to_name, subject, html):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html, "html"))
    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

def send_brevo(to_email, to_name, subject, html):
    payload = json.dumps({
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject, "htmlContent": html,
    }).encode()
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=payload, method="POST")
    req.add_header("api-key", BREVO_API_KEY)
    req.add_header("Content-Type", "application/json")
    urllib.request.urlopen(req, timeout=15)

# ==========================================
# LOAD CONTACTS FROM MULTIPLE CSVS IN PRIORITY ORDER
# ==========================================
def load_all_contacts():
    """
    Returns list of contacts sorted:
      Tier 1 (foreign) first, then Tier 2 (Indian top), then Tier 3 (local)
    File order: internship_providers → paper_authors → researchers
    """
    file_configs = [
        ("internship_providers.csv", "internship"),
        ("paper_authors.csv",        "researcher"),
        ("researchers.csv",          "researcher"),
    ]

    buckets = {1: [], 2: [], 3: []}

    for fname, contact_type in file_configs:
        if not os.path.exists(fname):
            print(f"  Warning: {fname} not found, skipping.")
            continue
        with open(fname, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                row["_type"] = contact_type
                tier = int(row.get("Tier", 3))
                buckets[tier].append(row)

    all_contacts = buckets[1] + buckets[2] + buckets[3]
    print(f"Loaded contacts: Tier1={len(buckets[1])} | Tier2={len(buckets[2])} | Tier3={len(buckets[3])}")
    return all_contacts


# ==========================================
# MAIN CAMPAIGN RUNNER
# ==========================================
def run_master_campaign():
    all_contacts = load_all_contacts()
    sent_set     = load_sent()
    total_new    = sum(1 for c in all_contacts if c.get("Email","").lower() not in sent_set)
    
    print(f"\nTotal contacts: {len(all_contacts)}")
    print(f"Already sent:   {len(sent_set)}")
    print(f"Remaining:      {total_new}")
    print(f"Daily limit:    {DAILY_LIMIT} emails/day")
    days_needed = -(-total_new // DAILY_LIMIT)
    print(f"Estimated days: {days_needed}\n")

    sent_today = 0
    day_num    = 1
    idx        = 0

    gmail_server = None
    try:
        gmail_server = connect_gmail()
        print("Gmail SMTP connected ✓\n")
        use_gmail = True
    except Exception as e:
        print(f"Gmail failed: {e}. Using Brevo.\n")
        use_gmail = False

    for contact in all_contacts:
        email        = contact.get("Email", "").strip()
        name         = contact.get("Name", "").strip()
        paper_title  = contact.get("Paper Title", contact.get("Focus", "medical imaging"))
        affiliation  = contact.get("Affiliation", "your organization")
        contact_type = contact.get("_type", "researcher")
        tier         = int(contact.get("Tier", 3))

        if not email or email.lower() in sent_set:
            continue

        name_parts = name.split()
        last_name  = name_parts[-1] if name_parts else "there"

        # Choose subject and body
        subject = SUBJECTS[idx % len(SUBJECTS)].format(paper_title=paper_title)
        if contact_type == "internship":
            body = BODY_INTERNSHIP.format(affiliation=affiliation)
        else:
            body = BODY_RESEARCHER.format(last_name=last_name, paper_title=paper_title)

        tier_label = "🌍" if tier == 1 else ("🇮🇳" if tier == 2 else "📍")
        print(f"Day {day_num} [{sent_today+1}/{DAILY_LIMIT}] {tier_label} -> {email}...", end=" ")
        sys.stdout.flush()

        try:
            if use_gmail and gmail_server:
                try:
                    send_gmail(gmail_server, email, name, subject, body)
                except smtplib.SMTPServerDisconnected:
                    gmail_server = connect_gmail()
                    send_gmail(gmail_server, email, name, subject, body)
            else:
                send_brevo(email, name, subject, body)

            log_sent(email)
            sent_set.add(email.lower())
            sent_today += 1
            idx        += 1
            print("SENT ✓")

        except Exception as e:
            idx += 1
            print(f"FAILED: {e}")

        # Daily limit check
        if sent_today >= DAILY_LIMIT:
            print(f"\n✅ Day {day_num} complete! Sent {sent_today} emails.")
            print(f"😴 Sleeping 24 hours before Day {day_num + 1}...\n")
            if gmail_server:
                try: gmail_server.quit()
                except: pass
                gmail_server = None
            time.sleep(BATCH_SLEEP)
            day_num   += 1
            sent_today = 0
            # Reconnect Gmail for next day
            try:
                gmail_server = connect_gmail()
                use_gmail = True
            except:
                use_gmail = False
        else:
            time.sleep(random.randint(EMAIL_MIN_WAIT, EMAIL_MAX_WAIT))

    if gmail_server:
        try: gmail_server.quit()
        except: pass

    print(f"\n{'='*60}")
    print(f"ENTIRE CAMPAIGN COMPLETE! Total sent: {len(sent_set)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_master_campaign()
