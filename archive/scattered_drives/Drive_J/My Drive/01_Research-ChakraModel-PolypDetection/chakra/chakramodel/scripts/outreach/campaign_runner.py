import csv
import time
import sys
import os
import json
import random
import argparse
import smtplib
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# LOAD CREDENTIALS SECURELY FROM .env
# ==========================================
def load_env(filepath=".env"):
    if not os.path.exists(filepath):
        print(f"ERROR: {filepath} not found.")
        sys.exit(1)
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip()

load_env()

SENDER_EMAIL       = os.environ.get("SENDER_EMAIL")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
BREVO_API_KEY      = os.environ.get("BREVO_API_KEY")
SENDER_NAME        = "Gokul R"

SENT_LOG  = "sent_emails.txt"
MIN_WAIT  = 25   # seconds between emails
MAX_WAIT  = 45
BATCH_DELAY_SECONDS = 3600  # 1 hour between batches

# ==========================================
# TEMPLATES  (3 variants, rotated)
# ==========================================
SUBJECTS = [
    "Loved your paper on {paper_title} — quick question",
    "Your work on {paper_title} caught my eye",
    "Fellow researcher reaching out re: {paper_title}",
]

BODIES = [
    """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.7;">
  <p>Hi Dr. {last_name},</p>
  <p>I came across your paper on <i>"{paper_title}"</i> while researching temporal consistency in medical video analysis, and found your approach really insightful.</p>
  <p>I'm Gokul, a final-year undergrad at Easwari Engineering College (Chennai) studying AI &amp; ML. My team and I have been building <b>PolypNet-3D</b> — a system that tackles a specific pain point in live colonoscopy: polyps flickering in and out of detections frame-to-frame due to motion blur. We fine-tune YOLOv8 on CVC-ClinicDB / Kvasir-SEG and add a Kalman filter layer on top to force bounding-box continuity across consecutive frames. Early results on CVC-ClinicVideoDB are encouraging.</p>
  <p>I'm actively looking for a <b>research internship</b> in medical imaging or computer vision. If your group has openings — or you know someone who might — I'd be really grateful for a nudge in the right direction.</p>
  <p>Happy to share more details or discuss our approach anytime!</p>
  <p>Thanks for your time,<br><br>
  <b>Gokul R</b><br>
  Undergrad Researcher · Dept. of AI &amp; ML<br>
  Easwari Engineering College, Chennai<br>
  <a href="https://github.com/Gokzz-glitch">GitHub</a> ·
  <a href="https://github.com/Gokzz-glitch/chakramodel">PolypNet-3D Code</a>
  </p>
</div>""",

    """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.7;">
  <p>Dear Dr. {last_name},</p>
  <p>I recently read your work on <i>"{paper_title}"</i> and wanted to introduce myself. Your research closely aligns with what my team has been working on.</p>
  <p>I'm Gokul R, a final-year undergraduate in AI &amp; ML at Easwari Engineering College, Chennai. We've been developing <b>PolypNet-3D</b> — a real-time polyp detection system for colonoscopy video that addresses detection flickering. Standard frame-by-frame detectors drop detections between frames due to motion artefacts, which makes clinicians hesitant to rely on them. We address this with a Kalman filter layer over YOLOv8 bounding-box outputs to enforce temporal consistency.</p>
  <p>I'm actively seeking a <b>research internship</b> in medical image analysis or computer vision, and would love to contribute my PyTorch and video-processing skills to a research group tackling related problems.</p>
  <p>If there are openings in your lab or you could point me toward the right contact, I'd sincerely appreciate it.</p>
  <p>Warm regards,<br><br>
  <b>Gokul R</b><br>
  Undergraduate Researcher · Dept. of AI &amp; ML<br>
  Easwari Engineering College, Chennai<br>
  <a href="https://github.com/Gokzz-glitch">GitHub</a> ·
  <a href="https://github.com/Gokzz-glitch/chakramodel">PolypNet-3D Code</a>
  </p>
</div>""",

    """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.7;">
  <p>Hi Dr. {last_name},</p>
  <p>Quick intro — I'm Gokul, an undergrad researcher at Easwari Engineering College working on real-time polyp detection for colonoscopy. I read your paper on <i>"{paper_title}"</i> and thought our work might resonate.</p>
  <p>We built <b>PolypNet-3D</b> — it pairs YOLOv8 with a Kalman filter to stop bounding boxes flickering between frames during live procedures. All open-source if you'd like a look.</p>
  <p>I'm hunting for a <b>research internship</b> in medical CV. Any leads or openings would be hugely appreciated!</p>
  <p>Best,<br><br>
  <b>Gokul R</b><br>
  Undergrad · AI &amp; ML — Easwari Engineering College<br>
  <a href="https://github.com/Gokzz-glitch">GitHub</a> ·
  <a href="https://github.com/Gokzz-glitch/chakramodel">PolypNet-3D Code</a>
  </p>
</div>""",
]

# ==========================================
# HELPERS
# ==========================================
def load_sent_emails():
    if not os.path.exists(SENT_LOG):
        return set()
    with open(SENT_LOG, 'r') as f:
        return set(line.strip().lower() for line in f if line.strip())

def log_sent_email(email):
    with open(SENT_LOG, 'a') as f:
        f.write(email.lower() + '\n')

# ---- Gmail SMTP ----
def connect_gmail():
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
    return server

def send_via_gmail(server, to_email, to_name, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"]      = to_email
    msg.attach(MIMEText(html_body, "html"))
    server.sendmail(SENDER_EMAIL, to_email, msg.as_string())

# ---- Brevo fallback ----
def send_via_brevo(to_email, to_name, subject, html_body):
    url     = "https://api.brevo.com/v3/smtp/email"
    payload = json.dumps({
        "sender":      {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to":          [{"email": to_email, "name": to_name}],
        "subject":     subject,
        "htmlContent": html_body,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("api-key", BREVO_API_KEY)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    resp = urllib.request.urlopen(req, timeout=15)
    return resp.status

# ==========================================
# CAMPAIGN RUNNER
# ==========================================
def run_campaign(csv_files, total_emails, batch_size, use_gmail=True):
    print(f"Campaign start | Total: {total_emails} | Batch: {batch_size} | Via: {'Gmail' if use_gmail else 'Brevo'}")

    # Load all contacts
    all_contacts = []
    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            print(f"  Skipping {csv_file} — not found.")
            continue
        with open(csv_file, mode='r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                all_contacts.append(row)
    print(f"Loaded {len(all_contacts)} contacts total.\n")

    sent_overall = 0
    global_idx   = 0

    while sent_overall < total_emails:
        sent_this_batch  = 0
        already_sent     = load_sent_emails()

        print(f"[{time.strftime('%H:%M:%S')}] Starting Batch {sent_overall // batch_size + 1} ...")

        # (Re)connect Gmail each batch in case connection dropped
        gmail_server = None
        if use_gmail and GMAIL_APP_PASSWORD:
            try:
                gmail_server = connect_gmail()
                print("  Gmail SMTP connected ✓")
            except Exception as e:
                print(f"  Gmail connect failed: {e}. Falling back to Brevo.")
                use_gmail = False

        for contact in all_contacts:
            if sent_this_batch >= batch_size or sent_overall >= total_emails:
                break

            email       = contact.get("Email", "").strip()
            name        = contact.get("Name", "").strip()
            paper_title = contact.get("Paper Title", "medical imaging")

            if not email or email.lower() in already_sent:
                continue

            name_parts = name.split()
            last_name  = name_parts[-1] if name_parts else name
            subject    = SUBJECTS[global_idx % len(SUBJECTS)].format(paper_title=paper_title)
            body       = BODIES[global_idx % len(BODIES)].format(last_name=last_name, paper_title=paper_title)

            label = f"[{sent_this_batch+1}/{batch_size} | Total {sent_overall+1}/{total_emails}]"
            print(f"{label} -> {email} ...", end=" ")
            sys.stdout.flush()

            try:
                if use_gmail and gmail_server:
                    send_via_gmail(gmail_server, email, f"Dr. {last_name}", subject, body)
                else:
                    send_via_brevo(email, f"Dr. {last_name}", subject, body)

                log_sent_email(email)
                already_sent.add(email.lower())
                sent_this_batch += 1
                sent_overall    += 1
                global_idx      += 1
                print("SENT ✓")

            except smtplib.SMTPServerDisconnected:
                # Reconnect and retry once
                try:
                    gmail_server = connect_gmail()
                    send_via_gmail(gmail_server, email, f"Dr. {last_name}", subject, body)
                    log_sent_email(email)
                    already_sent.add(email.lower())
                    sent_this_batch += 1
                    sent_overall    += 1
                    global_idx      += 1
                    print("SENT ✓ (reconnected)")
                except Exception as e2:
                    global_idx += 1
                    print(f"FAILED: {e2}")
            except Exception as e:
                global_idx += 1
                print(f"FAILED: {e}")

            if sent_this_batch < batch_size and sent_overall < total_emails:
                time.sleep(random.randint(MIN_WAIT, MAX_WAIT))

        if gmail_server:
            try:
                gmail_server.quit()
            except:
                pass

        if sent_this_batch == 0:
            print("No more new contacts. Campaign finished.")
            break

        print(f"\nBatch done. Sent {sent_this_batch} this batch | {sent_overall} total.")
        if sent_overall < total_emails:
            print(f"Sleeping {BATCH_DELAY_SECONDS // 60} min before next batch...")
            time.sleep(BATCH_DELAY_SECONDS)

    print(f"\n{'='*50}")
    print(f"Campaign complete! Total sent: {sent_overall}")
    print(f"{'='*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--files",      nargs='+', required=True, help="CSV files to process")
    parser.add_argument("--total",      type=int,  default=240,   help="Total emails to send")
    parser.add_argument("--batch-size", type=int,  default=60,    help="Emails per batch")
    parser.add_argument("--brevo",      action="store_true",      help="Force Brevo instead of Gmail")
    args = parser.parse_args()

    run_campaign(args.files, args.total, args.batch_size, use_gmail=not args.brevo)
