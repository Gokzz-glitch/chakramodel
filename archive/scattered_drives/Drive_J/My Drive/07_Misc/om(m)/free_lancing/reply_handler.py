import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
import datetime
import os
from google import genai

EMAIL_ADDRESS = "310624148027@eec.srmrmp.edu.in"
APP_PASSWORD = "assb jicj kvrp cakn" 
GEMINI_API_KEY = "AQ.Ab8RN6LSkpTRsRxkw2D9wQCK1ilO82mA0eYGhNGc3OFiCzOWUQ"
DB_PATH = r"M:\free_lancing\campaign.db"
LOG_FILE = r"M:\free_lancing\report.log"
YOUR_NAME = "Gokul R."

client = genai.Client(api_key=GEMINI_API_KEY)

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    with open(LOG_FILE, "a") as f:
        f.write(formatted + "\n")

def is_target(from_email):
    # Extract raw email if it's in the format "Name <email@domain.com>"
    if "<" in from_email and ">" in from_email:
        from_email = from_email.split("<")[1].split(">")[0].strip()
    from_email = from_email.lower().strip()
    
    if from_email == EMAIL_ADDRESS.lower():
        return from_email, None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT company FROM outreach WHERE email = ?", (from_email,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return from_email, row[0]
    return from_email, None

def mark_replied(email_address):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE outreach SET status = 'replied' WHERE email = ?", (email_address,))
    conn.commit()
    conn.close()

def extract_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                return part.get_payload(decode=True).decode('utf-8', errors='ignore')
    else:
        return msg.get_payload(decode=True).decode('utf-8', errors='ignore')
    return ""

def generate_reply(company, incoming_message):
    prompt = f"""
You are {YOUR_NAME}, a 3rd-year AI student. You recently emailed {company} asking for goodies/student support for your ML research (PolypNet-3D).
They just replied to your email!

Their Reply:
"{incoming_message}"

Write a short, extremely human, and polite reply to them. If they asked for your address, provide a placeholder [YOUR_ADDRESS] (do NOT make up an address).
If they said no, thank them for their time politely.
If they said yes, express massive gratitude!
Do NOT sound like an AI. Keep it to 3-5 sentences.
First line must be the Subject line (e.g. "Re: ...").
"""
    response = client.models.generate_content(model='gemini-3.6-flash', contents=prompt)
    text = response.text.strip().split("\n", 1)
    subject = text[0].strip() if len(text) >= 2 else f"Re: Your email"
    body = text[1].strip() if len(text) >= 2 else response.text.strip()
    return subject, body

def send_email(target_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = target_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_ADDRESS, APP_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, target_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        log(f"ERROR sending reply to {target_email}: {e}")
        return False

def check_inbox():
    log("=== Starting IMAP Reply Monitor ===")
    try:
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(EMAIL_ADDRESS, APP_PASSWORD)
        mail.select('inbox')

        status, response = mail.search(None, 'UNSEEN')
        unread_msg_nums = response[0].split()

        for e_id in unread_msg_nums:
            status, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    from_header = msg.get('From', '')
                    raw_email, company = is_target(from_header)
                    
                    if company:
                        log(f"New reply detected from target: {company} ({raw_email})")
                        body = extract_body(msg)
                        
                        log(f"Generating intelligent AI reply...")
                        reply_subj, reply_body = generate_reply(company, body)
                        
                        success = send_email(raw_email, reply_subj, reply_body)
                        if success:
                            log(f"Successfully auto-replied to {company}!")
                            mark_replied(raw_email)
                            
                            # Forward a summary to the user's own email so they know
                            summary = f"Good news! {company} replied to your outreach.<br><br><b>Their message:</b><br>{body}<br><br><b>AI Auto-Reply Sent:</b><br>{reply_body}"
                            send_email(EMAIL_ADDRESS, f"ALERT: Reply from {company}!", summary)
                    else:
                        pass
                        # Not a target, leave it unseen or ignore
        mail.close()
        mail.logout()
    except Exception as e:
        log(f"IMAP Error: {e}")
    log("=== Finished IMAP Reply Monitor ===")

if __name__ == "__main__":
    check_inbox()
