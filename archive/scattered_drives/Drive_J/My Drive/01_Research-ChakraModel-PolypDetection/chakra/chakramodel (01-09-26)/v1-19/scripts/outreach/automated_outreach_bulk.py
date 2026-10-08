import csv
import time
import sys
import os
import json
import random
import argparse
import urllib.request
import urllib.error

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

SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
BREVO_API_KEY = os.environ.get("BREVO_API_KEY")
SENDER_NAME = "Gokul R"

if not SENDER_EMAIL or not BREVO_API_KEY:
    print("ERROR: SENDER_EMAIL and BREVO_API_KEY must be set in .env file.")
    sys.exit(1)

# Wait randomly to look human
MIN_WAIT = 8
MAX_WAIT = 20

# ==========================================
# 3 HUMAN EMAIL VARIANTS
# ==========================================
SUBJECTS = [
    "Loved your paper on {paper_title} — quick question",
    "Your work on {paper_title} caught my eye",
    "Fellow researcher reaching out re: {paper_title}",
]

BODIES = [
    """\
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #222; line-height: 1.7;">
    <p>Hi Dr. {last_name},</p>
    <p>I came across your paper on <i>"{paper_title}"</i> while researching temporal consistency in medical video analysis, and I found your approach really insightful.</p>
    <p>A bit about me — I'm Gokul, a final-year undergrad at Easwari Engineering College (Chennai), studying AI & Machine Learning. For the past few months, my team and I have been building <b>PolypNet-3D</b>, a system that tackles a specific clinical pain point: when you run a deep learning detector on a live colonoscopy feed, polyps get detected in one frame and then lost in the next due to motion blur or camera angle changes. Gastroenterologists find this flickering really distracting and it undermines their trust in AI-assisted screening.</p>
    <p>Our solution fine-tunes YOLOv8 on CVC-ClinicDB and Kvasir-SEG for per-frame detection, and then layers a Kalman filter on top to enforce bounding-box continuity across consecutive frames. Early results on CVC-ClinicVideoDB have been promising.</p>
    <p>I'm writing because I'm actively looking for a <b>research internship</b> in medical imaging or computer vision. If your group has any openings — or if you could point me toward someone who might — I'd be very grateful.</p>
    <p>Either way, I'd love to hear your quick thoughts on our temporal approach if you ever have a spare moment.</p>
    <p>Thank you for your time,<br><br>
    <b>Gokul R</b><br>
    Undergrad Researcher, Dept. of AI & ML<br>
    Easwari Engineering College, Chennai<br>
    <a href="https://github.com/Gokzz-glitch">GitHub</a> &#183;
    <a href="https://github.com/Gokzz-glitch/chakramodel">PolypNet-3D Code</a>
    </p>
</div>
""",
    """\
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #222; line-height: 1.7;">
    <p>Dear Dr. {last_name},</p>
    <p>I recently read your work on <i>"{paper_title}"</i> and wanted to reach out. Your research closely aligns with what my team has been working on, and I thought it was worth a brief introduction.</p>
    <p>I'm Gokul R, a final-year undergraduate in AI & Machine Learning at Easwari Engineering College, Chennai. Over the past several months, we have been developing <b>PolypNet-3D</b> — a real-time polyp detection system designed specifically for colonoscopy video streams. The core problem we address is detection flickering: standard frame-by-frame detectors tend to drop detections between consecutive frames due to motion artifacts, which makes clinicians hesitant to rely on them during live procedures.</p>
    <p>We tackle this by adding a temporal consistency layer built on Kalman filtering over the YOLOv8 bounding-box outputs. We have validated the approach on CVC-ClinicVideoDB sequences with encouraging results so far.</p>
    <p>I am reaching out because I am actively seeking a <b>research internship opportunity</b> in the area of medical image analysis or computer vision. I would be happy to contribute my skills in PyTorch, object detection architectures, and video processing to a research group working on related problems.</p>
    <p>If there are any openings in your lab or if you could suggest someone I should speak with, I would sincerely appreciate it.</p>
    <p>Warm regards,<br><br>
    <b>Gokul R</b><br>
    Undergraduate Researcher, Dept. of AI & ML<br>
    Easwari Engineering College, Chennai<br>
    <a href="https://github.com/Gokzz-glitch">GitHub</a> &#183;
    <a href="https://github.com/Gokzz-glitch/chakramodel">PolypNet-3D Code</a>
    </p>
</div>
""",
    """\
<div style="font-family: Arial, sans-serif; font-size: 14px; color: #222; line-height: 1.7;">
    <p>Hi Dr. {last_name},</p>
    <p>Quick intro — I'm Gokul, an undergrad researcher at Easwari Engineering College working on real-time polyp detection in colonoscopy video. I read your paper on <i>"{paper_title}"</i> and thought our work might resonate with yours.</p>
    <p>We built a system called <b>PolypNet-3D</b> that pairs YOLOv8 with Kalman filtering to stop the bounding boxes from flickering between frames during live procedures. The code is open-source if you'd like to take a look.</p>
    <p>I'm currently looking for a <b>research internship</b> in medical CV or imaging. If you have any leads or openings, I'd really appreciate hearing about them.</p>
    <p>Thanks for your time!</p>
    <p>Best,<br><br>
    <b>Gokul R</b><br>
    Undergrad, AI & ML — Easwari Engineering College<br>
    <a href="https://github.com/Gokzz-glitch">GitHub</a> &#183;
    <a href="https://github.com/Gokzz-glitch/chakramodel">PolypNet-3D Code</a>
    </p>
</div>
""",
]


def send_email_brevo(to_email, to_name, subject, html_content):
    url = "https://api.brevo.com/v3/smtp/email"
    payload = json.dumps({
        "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": subject,
        "htmlContent": html_content,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("api-key", BREVO_API_KEY)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    resp = urllib.request.urlopen(req, timeout=15)
    return resp.status


def send_emails(csv_files, total_limit):
    print(f"Using Brevo API. Sender: {SENDER_EMAIL}")
    print(f"Total sending limit across all files: {total_limit}")
    print(f"CSVs to process: {', '.join(csv_files)}\n")

    sent_count = 0
    failed_count = 0
    global_idx = 0

    for csv_file in csv_files:
        if sent_count >= total_limit:
            break
            
        print(f"\n--- Processing {csv_file} ---")
        if not os.path.exists(csv_file):
            print(f"Skipping {csv_file}, file not found.")
            continue
            
        contacts = []
        with open(csv_file, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                contacts.append(row)

        for contact in contacts:
            if sent_count >= total_limit:
                print(f"\nReached total limit of {total_limit} emails.")
                break

            name = contact.get("Name", "")
            email = contact.get("Email", "")
            paper_title = contact.get("Paper Title", "medical imaging")

            if not email:
                continue

            name_parts = name.split()
            last_name = name_parts[-1] if name_parts else name

            subject = SUBJECTS[global_idx % len(SUBJECTS)].format(paper_title=paper_title)
            body = BODIES[global_idx % len(BODIES)].format(last_name=last_name, paper_title=paper_title)

            print(f"[{sent_count+1}/{total_limit}] -> {email} (Dr. {last_name})...", end=" ")
            sys.stdout.flush()
            
            try:
                status = send_email_brevo(email, f"Dr. {last_name}", subject, body)
                if status in (200, 201):
                    sent_count += 1
                    print("SENT")
                else:
                    failed_count += 1
                    print(f"HTTP {status}")
            except urllib.error.HTTPError as e:
                failed_count += 1
                print(f"FAILED: {e}")
                try:
                    print(f"    API Error Info: {e.read().decode('utf-8')}")
                except:
                    pass
            except Exception as e:
                failed_count += 1
                print(f"FAILED: {e}")

            global_idx += 1
            if sent_count < total_limit:
                delay = random.randint(MIN_WAIT, MAX_WAIT)
                time.sleep(delay)

    print(f"\n{'='*40}")
    print(f"RESULTS: {sent_count} sent, {failed_count} failed out of {total_limit} max.")
    print(f"{'='*40}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send personalized cold emails via Brevo API across multiple CSVs.")
    parser.add_argument("--files", nargs='+', help="List of CSV files to process", required=True)
    parser.add_argument("--limit", type=int, default=100, help="Total emails to send across all files")
    args = parser.parse_args()
    send_emails(args.files, args.limit)
