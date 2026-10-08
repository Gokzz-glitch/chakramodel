import os
import time
import sqlite3
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Setup API and Email credentials
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PERSONAL_EMAIL = os.getenv("PERSONAL_EMAIL")
PERSONAL_APP_PASSWORD = os.getenv("PERSONAL_APP_PASSWORD")
COLLEGE_EMAIL = os.getenv("COLLEGE_EMAIL")
COLLEGE_APP_PASSWORD = os.getenv("COLLEGE_APP_PASSWORD")

# Initialize Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

# Context about you and your project (ChakraModel)
MY_CONTEXT = """
I am Gokul R, a student and researcher. I developed 'ChakraModel', an advanced deep learning framework for medical imaging, specifically focusing on polyp detection in colonoscopy videos. My work achieves State-of-the-Art (SOTA) results, outperforming existing models in accuracy and robustness. I am looking for a research internship or collaboration opportunity.
"""

def generate_email_content(author_name, institution, paper_title, abstract):
    prompt = f"""
    You are an AI assistant helping a student (Gokul) write a highly personalized cold email for an internship/research collaboration.
    
    Target Researcher: {author_name}
    Institution: {institution}
    Their Recent Paper: "{paper_title}"
    Paper Abstract: "{abstract}"
    
    My Context:
    {MY_CONTEXT}
    
    Instructions:
    1. Write a professional, polite, and enthusiastic cold email to this researcher.
    2. Mention their paper and how it inspired you or relates to your interests.
    3. Introduce my project (ChakraModel) briefly and highlight its relevance to their work (medical imaging/CV/deep learning).
    4. Ask if they have any open internship or research assistant roles in their lab.
    5. Also, use your search capabilities to find their LinkedIn profile or lab website and mention it naturally if you find it.
    6. Output ONLY the email body. Do not include subject line or placeholders. Keep it under 200 words.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[{"google_search": {}}],  # Enable Google Search to find LinkedIn
            temperature=0.7,
        ),
    )
    return response.text

def send_email(sender_email, sender_password, to_email, subject, body):
    if not sender_email or not sender_password:
        print(f"[DRY RUN] Would send from {sender_email} to {to_email}")
        print(f"Subject: {subject}\nBody:\n{body}\n---")
        return True

    msg = EmailMessage()
    msg.set_content(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email

    try:
        # Assuming Gmail for personal, Outlook for college as a default example.
        # Adjust SMTP server based on actual provider.
        smtp_server = "smtp.gmail.com" if "gmail" in sender_email else "smtp.office365.com"
        port = 587 if "office365" in smtp_server else 465
        
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port)
        else:
            server = smtplib.SMTP(smtp_server, port)
            server.starttls()
            
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

def main():
    conn = sqlite3.connect('leads.db')
    c = conn.cursor()
    
    # Get 100 uncontacted leads
    c.execute('SELECT id, author_name, institution, paper_title, paper_abstract FROM leads WHERE contacted = 0 LIMIT 100')
    leads = c.fetchall()
    
    if not leads:
        print("No uncontacted leads found in database. Run find_leads.py first.")
        return

    print(f"Found {len(leads)} leads to contact today.")
    
    personal_count = 0
    college_count = 0
    
    for i, lead in enumerate(leads):
        lead_id, author_name, institution, paper_title, paper_abstract = lead
        print(f"Processing {i+1}/{len(leads)}: {author_name}")
        
        # Decide which account to use
        if personal_count < 60:
            sender_email = PERSONAL_EMAIL
            sender_password = PERSONAL_APP_PASSWORD
            account_type = "Personal"
            personal_count += 1
        else:
            sender_email = COLLEGE_EMAIL
            sender_password = COLLEGE_APP_PASSWORD
            account_type = "College"
            college_count += 1
            
        try:
            # Generate email body
            email_body = generate_email_content(author_name, institution, paper_title, paper_abstract)
            subject = f"Inspired by your work on {paper_title[:50]}... - Research Internship Inquiry"
            
            # Since OpenAlex doesn't always provide emails, you might need to guess the email 
            # based on institution or use an API like Hunter.io. For now, we simulate the email:
            guessed_email = f"{author_name.split()[-1].lower()}@{institution.replace(' ', '').lower()}.edu"
            
            # Send Email
            success = send_email(sender_email, sender_password, guessed_email, subject, email_body)
            
            if success:
                # Mark as contacted
                c.execute('UPDATE leads SET contacted = 1 WHERE id = ?', (lead_id,))
                conn.commit()
                print(f"Sent via {account_type} to {author_name}")
            
            # Sleep to respect rate limits (Gemini API free tier)
            time.sleep(4)
            
        except Exception as e:
            print(f"Error processing {author_name}: {e}")
            
    conn.close()
    print("Daily batch complete!")

if __name__ == "__main__":
    main()
