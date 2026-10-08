import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import csv
import time
import os
import sys
import datetime
from google import genai

sys.path.append(r"M:\chakramodel")
import linkedin_bot

sys.path.append(r"M:\free_lancing")
import database

EMAIL_ADDRESS = "310624148027@eec.srmrmp.edu.in"
APP_PASSWORD = "assb jicj kvrp cakn" 
YOUR_NAME = "Gokul R."
PORTFOLIO_LINK = "https://gokzz-glitch.github.io/PORTFOLIO?utm_source=auto_mailer&utm_medium=email&utm_campaign=ai_outreach" 
CSV_FILE = r"M:\free_lancing\targets.csv"
RESUME_FILE = r"M:\free_lancing\resume.pdf"
LOG_FILE = r"M:\free_lancing\report.log"

GEMINI_API_KEY = "AQ.Ab8RN6LSkpTRsRxkw2D9wQCK1ilO82mA0eYGhNGc3OFiCzOWUQ"
client = genai.Client(api_key=GEMINI_API_KEY)

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    with open(LOG_FILE, "a") as f:
        f.write(formatted + "\n")

def run_opportunity_engine():
    sys.path.append(r"M:\chakramodel")
    try:
        log("Running daily opportunity engine to discover new leads...")
        import opportunity_engine
        opportunity_engine.main()
        
        try:
            import github_engine
            github_engine.scrape_github_devrels()
        except Exception as e:
            log(f"Error running github engine: {e}")
            
        try:
            import event_engine
            event_engine.generate_event_leads()
        except Exception as e:
            log(f"Error running event engine: {e}")
        
        # Pull new leads from the priority file into targets.csv
        priority_file = r"M:\chakramodel\priority_5_foreign_and_top_institutions.csv"
        swag_file = r"M:\free_lancing\swag_targets.csv"
        
        # Read existing emails in targets to avoid duplicates
        existing_emails = set()
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_emails.add(row.get("Email", "").lower())
        
        new_rows = []
        
        # 1. Add Swag/Goodies targets
        added_swag = 0
        if os.path.exists(swag_file):
            with open(swag_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get("Email", "").lower()
                    # We use company name + email combo to avoid duplicates for the same email but different targets
                    target_key = row.get("Company", "") + email
                    if email and target_key not in existing_emails:
                        new_rows.append({
                            "Company": row.get("Company", ""),
                            "Email": email,
                            "Context": row.get("Context", ""),
                            "Type": row.get("Type", "brand"),
                            "Status": "Pending"
                        })
                        existing_emails.add(target_key)
                        added_swag += 1

        # 2. Add Researcher opportunities
        added_researchers = 0
        if os.path.exists(priority_file):
            with open(priority_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    email = row.get("Email", "").lower()
                    if email and email not in existing_emails:
                        new_rows.append({
                            "Company": row.get("Name", "Researcher"),
                            "Email": email,
                            "Context": row.get("Paper Title", ""),
                            "Type": "researcher",
                            "Status": "Pending"
                        })
                        existing_emails.add(email)
                        added_researchers += 1
                        
        if new_rows:
            file_exists = os.path.exists(CSV_FILE)
            with open(CSV_FILE, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=["Company", "Email", "Context", "Type", "Status"])
                if not file_exists:
                    writer.writeheader()
                for r in new_rows:
                    writer.writerow(r)
            log(f"Added {added_swag} new swag targets and {added_researchers} new researcher leads to targets queue.")
    except Exception as e:
        log(f"Error running opportunity engine: {e}")

def get_humanly_email(company_or_name, context, type):
    log(f"Asking Gemini to write a tailored email for {company_or_name}...")
    
    if type == "researcher":
        prompt = f"""
You are {YOUR_NAME}, a 3rd-year AI & Machine Learning Engineering student at SRM Institute of Science and Technology.
You are writing a cold outreach email to {company_or_name}, an academic researcher.
Their recent paper/work: "{context}"

Your goal is to reach out regarding your own open-source project called "PolypNet-3D" (a hybrid YOLOv8 + R-CNN pipeline with Temporal Consistency Filtering for real-time colonoscopy polyp detection).
Mention you read their paper and thought your work might resonate with theirs, as you are solving the problem of bounding-box flickering during live procedures.
You are actively looking for a research internship in medical imaging or computer vision, and want to ask if they have any openings in their lab.
You have attached your resume and linked your portfolio ({PORTFOLIO_LINK}).

Write the email to sound extremely human, concise, conversational, and appreciative. Do NOT make it sound like an AI wrote it. 
First line of your response MUST be the Subject line. The rest of the response should be the email body in clean HTML format. Use <p>, <b>, and <a href="..."> tags to make it look professional. Do NOT include markdown code blocks like ```html. Do not include labels like "Subject:" or "Body:".
"""
    elif type == "tech":
        prompt = f"""
You are {YOUR_NAME}, a 3rd-year AI & Machine Learning Engineering student at SRM Institute of Science and Technology.
You are writing a cold outreach email to {company_or_name}'s University Relations or DevRel team.
Context/Event to mention: {context if context and context != 'None' else 'general AI/ML programs'}

Your goal is to ask if they have any active student grants, cloud credits, or compute resources available for your ML research (specifically your PolypNet-3D medical imaging project).
If a specific event is mentioned in the context above, enthusiastically ask if they have student sponsorships or virtual passes to attend it.
You have attached your resume and linked your portfolio ({PORTFOLIO_LINK}).

Write the email to sound extremely human, conversational, and appreciative. Do NOT make it sound like an AI wrote it. Avoid overly formal corporate speak. Be a passionate student.
First line of your response MUST be the Subject line. The rest of the response should be the email body in clean HTML format. Use <p>, <b>, and <a href="..."> tags to make it look professional. Do NOT include markdown code blocks like ```html. Do not include labels like "Subject:" or "Body:".
"""
    else:
        prompt = f"""
You are {YOUR_NAME}, a 3rd-year AI engineering student at SRM Institute of Science and Technology.
You are writing a cold fan email to the specific team at {company_or_name}.
Team/Region/Context to specifically mention and tailor the email around: {context if context and context != 'None' else 'general appreciation'}

You are a huge fan of {company_or_name} and want to upgrade your daily engineering workflow (e.g., headphones, backpack, or laptop).
You are writing to ask if they ever send out care packages, promotional goodies, or product samples to student supporters who actively use and promote their brand.

CRITICAL REQUIREMENT: Instead of just asking for goodies, strongly emphasize your technical skills to prove you are worth supporting! Mention your GitHub portfolio ({PORTFOLIO_LINK}) and your ongoing open-source projects (like PolypNet-3D, an AI-assisted colonoscopy polyp detection model). Tell them you would love to proudly represent their brand while you code and attend hackathons.
Also mention naturally that you wear a size L shirt, size 34-36 pants, and size 9 Bata shoes.
You have attached your resume just in case they have student ambassador or internship opportunities.

Write the email to sound extremely human, enthusiastic, and appreciative. It must feel highly tailored to {company_or_name} and their specific regional team (e.g., if it says Marvel India, mention you are an Indian fan/developer; if it says GitHub Education, mention you use GitHub daily). Do NOT make it sound like an AI wrote it.
First line of your response MUST be the Subject line. The rest of the response should be the email body in clean HTML format. Use <p>, <b>, and <a href="..."> tags to make it look professional. Do NOT include markdown code blocks like ```html. Do not include labels like "Subject:" or "Body:".
"""

    response = client.models.generate_content(
        model='gemini-3.6-flash',
        contents=prompt
    )
    text = response.text.strip()
    
    lines = text.split("\n", 1)
    if len(lines) >= 2:
        subject = lines[0].strip()
        body = lines[1].strip()
    else:
        subject = "Hello from a student!"
        body = text
        
    return subject, body

def send_email(target_email, subject, body, resume_path):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = target_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'html'))

        # Attach Resume if it exists
        if os.path.exists(resume_path):
            with open(resume_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(resume_path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(resume_path)}"'
            msg.attach(part)
        else:
            log(f"WARNING: Resume not found at {resume_path}. Sending without attachment.")

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_ADDRESS, APP_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, target_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        log(f"ERROR connecting or sending to {target_email}: {e}")
        return False

import reply_handler

def main():
    log("=== Starting Daily Outreach Job ===")
    
    # Phase 2: Check IMAP for replies and auto-respond before sending new emails
    reply_handler.check_inbox()
    
    run_opportunity_engine()
    
    if not os.path.exists(CSV_FILE):
        log(f"CSV file not found: {CSV_FILE}")
        return

    rows = []
    with open(CSV_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    target_found = False
    target_row = None
    
    # Priority 1: brand or tech
    for row in rows:
        if row.get('Status') == 'Pending' and row.get('Type') in ['brand', 'tech']:
            target_row = row
            break
            
    # Priority 2: researcher
    if target_row is None:
        for row in rows:
            if row.get('Status') == 'Pending':
                target_row = row
                break

    if target_row:
        company = target_row['Company']
        email = target_row['Email']
        context = target_row['Context']
        type = target_row['Type']
        
        log(f"Found pending target: {company} ({email})")
        
        subject, body = get_humanly_email(company, context, type)
        
        success = send_email(email, subject, body, RESUME_FILE)
        if success:
            log(f"SUCCESSfully sent email to {company}.")
            target_row['Status'] = 'Sent'
            
            # Phase 2: Log to Database for Follow-ups
            database.log_email_sent(email, company)
            
            # Phase 3: Omni-Channel (Trigger LinkedIn Bot silently)
            log(f"Triggering Omni-Channel LinkedIn Bot for {company}...")
            linkedin_bot.trigger_omni_channel(company, "")
            
        else:
            log(f"FAILED to send email to {company}.")
        
        target_found = True
        
    if not target_found:
        log("No pending targets found in CSV. Checking for Phase 2 follow-ups...")
        
        follow_ups = database.get_pending_followups()
        if follow_ups:
            f = follow_ups[0]
            log(f"Found pending follow-up target: {f['Company']} ({f['Email']})")
            
            prompt = f"""
You are {YOUR_NAME}. Write a very short (2-3 sentences max) polite follow-up email to {f['Company']}.
You emailed them a few days ago regarding {PORTFOLIO_LINK} and your project PolypNet-3D. 
Just bumping the thread to see if they had a chance to read it or if they have any feedback.
Do NOT sound like an AI. First line must be Subject.
"""
            response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
            text = response.text.strip().split("\n", 1)
            f_subject = text[0].strip() if len(text) >= 2 else "Following up!"
            f_body = text[1].strip() if len(text) >= 2 else response.text.strip()
            
            if send_email(f['Email'], f_subject, f_body, RESUME_FILE):
                log(f"SUCCESSfully sent follow-up to {f['Company']}.")
                database.mark_followup_sent(f['Email'])
            else:
                log(f"FAILED to send follow-up to {f['Company']}.")
        else:
            log("No pending follow-ups either.")
        
    if target_found:
        with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            
    log("=== Finished Daily Outreach Job ===")

if __name__ == "__main__":
    main()
