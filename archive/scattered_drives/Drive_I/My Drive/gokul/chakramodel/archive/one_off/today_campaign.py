import smtplib
import json
import urllib.request
import csv
import sys
import os
import time
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

SENT_LOG = "sent_emails.txt"
SENDER_NAME = "Gokul R"
ATTACHMENTS = ["Gokul_Resume.pdf"]

# Russia/Moscow is TOP PRIORITY (400 out of 500)
TARGET_FILES = [
    {"file": "russia_moscow_leads.csv",                     "template": "russia_personalized"},
    {"file": "fully_funded_foreign.csv",                    "template": "internship"},
    {"file": "corporate_leads.csv",                         "template": "corporate_internship"},
    {"file": "priority_5_foreign_and_top_institutions.csv", "template": "internship"},
    {"file": "priority_1_colonoscopy_ai.csv",               "template": "researcher"},
    {"file": "priority_2_endoscopy_ai.csv",                 "template": "researcher"}
]

# ==========================================
# EMAIL TEMPLATES
# ==========================================

# PERSONALIZED Russia/Moscow template - references each person's specific work
SUBJECT_RUSSIA = "Research Internship Inquiry - Real-Time Colonoscopy AI (PolypNet-3D)"

def build_russia_body(contact):
    name = contact.get("Name", "").strip()
    personal_note = contact.get("PersonalNote", "your research in AI and medical imaging")
    affiliation = contact.get("Affiliation", "your institution")
    paper_title = contact.get("Paper Title", "")
    
    # Determine greeting
    if name in ["International Department", "HR Department", "General Info", 
                 "International Office", "International Admissions", "Careers Office",
                 "Admissions Office", "PhysBio Institute", "ArtInCol Team"]:
        greeting = "Dear Sir/Madam"
    else:
        last = name.split()[-1] if name.split() else "Professor"
        greeting = f"Dear Prof. {last}"
    
    # Build the personalized opening
    if "ArtInCol" in paper_title or "colonoscopy" in paper_title.lower():
        opening = f"""<p>I recently came across {personal_note}, and I was truly impressed. Our projects share a remarkably similar goal: improving real-time polyp detection during live colonoscopy using AI.</p>"""
    elif "Internship" in paper_title:
        opening = f"""<p>I am writing to express my strong interest in a research internship at <b>{affiliation}</b>. I have been closely following {personal_note}, and I believe my skills and ongoing project would be an excellent fit.</p>"""
    else:
        opening = f"""<p>I have been following {personal_note} with great interest. Your work directly intersects with a project I have been building, and I wanted to reach out to explore potential research collaboration or internship opportunities.</p>"""
    
    body = f"""<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>{greeting},</p>
  {opening}
  <p>I am Gokul R, a pre-final year (3rd year) undergraduate in AI & Machine Learning at Easwari Engineering College, Chennai, India. I have been developing <b>PolypNet-3D</b>, a real-time clinical decision support system for colonoscopy designed explicitly for edge deployment. Key highlights include:</p>
  <ul>
    <li>A cascaded pipeline using <b>YOLOv8n + PraNet</b> for real-time detection and sub-pixel boundary refinement.</li>
    <li>A <b>Kalman filter</b> layer to resolve bounding-box flickering, achieving temporal persistence across frames.</li>
    <li><b>TensorRT optimization</b> achieving 49 FPS, ensuring viability for live colonoscopy procedures on edge devices.</li>
  </ul>
  <p>I am actively seeking a <b>research internship</b> (ideally with accommodation/stipend support) where I can contribute my expertise in real-time medical computer vision and edge-optimized AI architectures. I would be honored to work under your guidance at <b>{affiliation}</b>.</p>
  <p>I have attached my <b>Resume</b> for your reference. My portfolio and code can be viewed on my <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Thank you very much for your time and consideration. I look forward to hearing from you.</p>
  <p>With warm regards,<br>
  <b>Gokul R</b><br>
  Undergraduate Researcher, Dept. of AI & ML<br>
  Easwari Engineering College, Chennai, India<br>
  Email: gokulrajasekar324@gmail.com</p>
</div>"""
    return body

SUBJECT_CORPORATE  = "AI/CV Engineering Intern (Edge Optimization & Real-Time Inference)"
SUBJECT_INTERNSHIP = "Research Internship Inquiry - AI & Medical Imaging"
SUBJECT_RESEARCHER = "Quick question about your work on {paper_title}"
SUBJECT_AUTHOR     = "Your paper on {paper_title} - reaching out"

BODY_CORPORATE = """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Hi,</p>
  <p>I'm Gokul R, an AI/CV undergraduate engineer with a strong background in deploying edge-optimized models. I am actively seeking a paid engineering or research internship at <b>{affiliation}</b>, ideally with relocation/accommodation support if available.</p>
  <p>To give you a sense of my work, I recently built a real-time clinical decision support system (PolypNet-3D) designed explicitly for edge constraints. Key highlights include:</p>
  <ul>
    <li>Developing a cascaded pipeline utilizing YOLOv8n and PraNet for real-time object detection and sub-pixel boundary refinement.</li>
    <li>Integrating a Kalman filter layer to resolve bounding-box flickering, achieving temporal persistence across frames.</li>
    <li>Optimizing the model via TensorRT to run at a solid 49 FPS, ensuring viability for live video feeds.</li>
  </ul>
  <p>I would love to bring my expertise in optimizing medical CV architectures and edge deployment to your engineering team. I have attached my <b>Resume</b> for your reference, and my portfolio can be viewed on my <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Thank you for your time and consideration. I look forward to hearing from you.</p>
  <p>Best regards,<br>
  <b>Gokul R</b><br>
  Undergraduate AI/ML Engineer</p>
</div>
"""

BODY_INTERNSHIP = """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Hi,</p>
  <p>I'm Gokul R, a pre-final year (3rd year) undergraduate in AI & Machine Learning at Easwari Engineering College, Chennai. I'm reaching out to enquire about <b>research internship openings</b> at <b>{affiliation}</b>.</p>
  <p>Recently, I built a real-time clinical decision support system (PolypNet-3D) designed explicitly for edge constraints. Key highlights of my work include:</p>
  <ul>
    <li>Developing a cascaded pipeline utilizing YOLOv8n and PraNet for real-time object detection and sub-pixel boundary refinement.</li>
    <li>Integrating a Kalman filter layer to resolve bounding-box flickering, achieving temporal persistence across frames.</li>
    <li>Optimizing the model via TensorRT to run at 49 FPS, ensuring viability for live colonoscopy procedures.</li>
  </ul>
  <p>I would love to bring my expertise in optimizing medical CV architectures to your team. I have attached my <b>Resume</b> for your reference. My portfolio can be viewed on my <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Thank you for your time. I look forward to hearing from you.</p>
  <p>Best regards,<br>
  <b>Gokul R</b><br>
  Undergraduate Researcher, Dept. of AI & ML<br>
  Easwari Engineering College</p>
</div>
"""

BODY_AUTHOR = """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Hi Dr. {last_name},</p>
  <p>I came across your work on <i>"{paper_title}"</i> - it immediately resonated with what my team has been building, so I wanted to reach out directly.</p>
  <p>I'm Gokul R, a pre-final year (3rd year) undergrad in AI & ML at Easwari Engineering College. We've been developing <b>PolypNet-3D</b>, a real-time polyp detection system that solves the bounding-box flickering problem in live colonoscopy feeds using YOLOv8 and a Kalman filter.</p>
  <p>I'm actively looking for a <b>research internship</b> in medical imaging or computer vision where I can contribute meaningfully. I have attached my <b>Resume</b> for your reference. You can also find my portfolio on my <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>. If your group has any openings, I'd be very grateful for a lead.</p>
  <p>Thanks so much for your time.<br><br>
  <b>Gokul R</b><br>
  Undergrad Researcher, AI & ML<br>
  Easwari Engineering College</p>
</div>
"""

BODY_RESEARCHER = """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Hi Dr. {last_name},</p>
  <p>I read your paper <i>"{paper_title}"</i> recently and found it genuinely useful for some problems we've been working on.</p>
  <p>I'm Gokul, a pre-final year (3rd year) undergrad building <b>PolypNet-3D</b> - a temporal consistency layer (Kalman filter + YOLOv8) for real-time colonoscopy polyp detection.</p>
  <p>I'm currently seeking a <b>research internship</b> in medical CV. I've attached my <b>Resume</b> for your reference. My portfolio can also be found on my <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>. If there are any openings in your lab, I'd love to hear about them. And if you ever have a moment, I'd genuinely value your take on our Kalman approach.</p>
  <p>Cheers,<br>
  <b>Gokul R</b><br>
  Undergrad Researcher, AI & ML<br>
  Easwari Engineering College</p>
</div>
"""

# ==========================================
# HELPERS
# ==========================================
def load_env():
    if not os.path.exists(".env"):
        print("ERROR: .env not found"); sys.exit(1)
    with open(".env") as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

def load_sent():
    if not os.path.exists(SENT_LOG): return set()
    with open(SENT_LOG) as f:
        return set(l.strip().lower() for l in f if l.strip())

def log_sent(email):
    with open(SENT_LOG, "a") as f:
        f.write(email.lower() + "\n")

def connect_gmail(sender, pwd):
    s = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    s.login(sender, pwd)
    return s

def get_gmail_msg_with_attachments(sender, to_email, to_name, subject, html):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"{SENDER_NAME} <{sender}>"
    msg["To"]      = to_email
    
    msg_alt = MIMEMultipart("alternative")
    msg_alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(msg_alt)
    
    for filename in ATTACHMENTS:
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(filename))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(filename)}"'
            msg.attach(part)
    return msg

def send_gmail(server, sender, to_email, to_name, subject, html):
    msg = get_gmail_msg_with_attachments(sender, to_email, to_name, subject, html)
    server.sendmail(sender, to_email, msg.as_string())

def send_brevo(api_key, sender, to_email, to_name, subject, html):
    payload_dict = {
        "sender":      {"name": SENDER_NAME, "email": sender},
        "to":          [{"email": to_email, "name": to_name}],
        "subject":     subject,
        "htmlContent": html,
    }
    attachments_list = []
    for filename in ATTACHMENTS:
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            attachments_list.append({"name": os.path.basename(filename), "content": encoded})
    if attachments_list:
        payload_dict["attachment"] = attachments_list
    payload = json.dumps(payload_dict).encode("utf-8")
    req = urllib.request.Request("https://api.brevo.com/v3/smtp/email", data=payload, method="POST")
    req.add_header("api-key", api_key)
    req.add_header("Content-Type", "application/json")
    urllib.request.urlopen(req, timeout=15)

def read_csv(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def is_indian(contact):
    email = contact.get("Email", "").lower()
    affil = contact.get("Affiliation", "").lower()
    indian_domains = ['.in', 'iit', 'nit', 'aiims', 'bits', 'iiit', 'isb', 'iim']
    if any(d in email for d in indian_domains): return True
    indian_keywords = ['india', 'delhi', 'mumbai', 'bangalore', 'bengaluru', 'chennai', 'hyderabad', 'kolkata', 'pune', 'kanpur', 'kharagpur', 'madras', 'roorkee', 'guwahati']
    if any(k in affil for k in indian_keywords): return True
    return False

# ==========================================
# MAIN
# ==========================================
def main():
    load_env()
    sender     = os.environ.get("SENDER_EMAIL")
    gmail_pwd  = os.environ.get("GMAIL_APP_PASSWORD")
    brevo_key  = os.environ.get("BREVO_API_KEY")
    sent_set   = load_sent()

    for filename in ATTACHMENTS:
        if not os.path.exists(filename):
            print(f"[WARNING] Attachment '{filename}' not found. It will be skipped.")

    print("=" * 60)
    print("TODAY'S CAMPAIGN - RUSSIA/MOSCOW PRIORITY")
    print("=" * 60)

    gmail_server = None
    try:
        gmail_server = connect_gmail(sender, gmail_pwd)
        use_gmail = True
        print("Gmail SMTP: Connected")
    except Exception as e:
        use_gmail = False
        print(f"Gmail SMTP: Failed ({e}) - using Brevo only")

    # ---- PHASE 1: Send ALL Russia/Moscow leads first (top priority) ----
    russia_leads = read_csv("russia_moscow_leads.csv")
    russia_unsent = [c for c in russia_leads if c.get("Email", "").strip().lower() not in sent_set]
    
    # ---- PHASE 2: Fill remaining budget with other leads ----
    other_files = [tf for tf in TARGET_FILES if tf["file"] != "russia_moscow_leads.csv"]
    other_leads = []
    for tf in other_files:
        contacts = read_csv(tf["file"])
        for c in contacts:
            email = c.get("Email", "").strip().lower()
            if not email or email in sent_set: continue
            c["template_type"] = tf["template"]
            other_leads.append(c)

    daily_budget = 400
    russia_count = min(len(russia_unsent), daily_budget)
    remaining_for_others = daily_budget - russia_count
    
    # Build final send list: Russia first, then others
    selected_leads = []
    
    for c in russia_unsent[:russia_count]:
        c["template_type"] = "russia_personalized"
        selected_leads.append(c)
    
    selected_leads.extend(other_leads[:remaining_for_others])
    
    print(f"\nRussia/Moscow leads: {russia_count}")
    print(f"Other leads: {min(remaining_for_others, len(other_leads))}")
    print(f"Total to send: {len(selected_leads)}\n")

    grand_total = 0
    for contact in selected_leads:
        email = contact.get("Email", "").strip().lower()
        name = contact.get("Name", "").strip()
        last_name = name.split()[-1] if name.split() else "there"
        paper_title = contact.get("Paper Title", "your recent research")
        template = contact.get("template_type", "researcher")
        
        if template == "russia_personalized":
            sub = SUBJECT_RUSSIA
            body = build_russia_body(contact)
        elif template == "corporate_internship":
            sub = SUBJECT_CORPORATE
            body = BODY_CORPORATE.format(affiliation=contact.get("Affiliation", "your company"))
        elif template == "internship":
            sub = SUBJECT_INTERNSHIP
            body = BODY_INTERNSHIP.format(affiliation=contact.get("Affiliation", "your institution"))
        elif template == "author":
            sub = SUBJECT_AUTHOR.format(paper_title=paper_title)
            body = BODY_AUTHOR.format(last_name=last_name, paper_title=paper_title)
        else:
            sub = SUBJECT_RESEARCHER.format(paper_title=paper_title)
            body = BODY_RESEARCHER.format(last_name=last_name, paper_title=paper_title)

        tag = "[RU]" if template == "russia_personalized" else "[GL]"
        print(f"  {tag} [{grand_total+1}/{len(selected_leads)}] {email} ... ", end="")
        sys.stdout.flush()

        try:
            if use_gmail and gmail_server:
                try:
                    send_gmail(gmail_server, sender, email, name, sub, body)
                except smtplib.SMTPServerDisconnected:
                    gmail_server = connect_gmail(sender, gmail_pwd)
                    send_gmail(gmail_server, sender, email, name, sub, body)
            else:
                send_brevo(brevo_key, sender, email, name, sub, body)
                
            print("SENT")
            log_sent(email)
            sent_set.add(email)
            grand_total += 1
            
        except Exception as e:
            print(f"FAILED: {e}")
            if "Daily user sending quota exceeded" in str(e) or "421" in str(e):
                print("\n[!] Rate limit reached. Stopping campaign for today.")
                break
        
        time.sleep(1)

    if gmail_server:
        try: gmail_server.quit()
        except: pass
        
    print(f"\nAll done! Sent {grand_total} emails today.")

if __name__ == "__main__":
    main()
