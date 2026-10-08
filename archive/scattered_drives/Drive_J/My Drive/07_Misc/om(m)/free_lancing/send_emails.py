import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# --- Credentials ---
EMAIL_ADDRESS = "310624148027@eec.srmrmp.edu.in"
APP_PASSWORD = "assb jicj kvrp cakn" 
YOUR_NAME = "Gokul"

# --- Target Companies ---
# For now, we are sending ALL of these to YOUR college email so you can see the tailored messages.
# Once you review them in your inbox, you can replace `EMAIL_ADDRESS` with the real company emails.
companies = {
    "Microsoft": EMAIL_ADDRESS, # Replace with actual Microsoft email
    "NVIDIA": EMAIL_ADDRESS,    # Replace with actual NVIDIA email
    "Bose": EMAIL_ADDRESS,      # Replace with actual Bose email
    "Sony": EMAIL_ADDRESS,      # Replace with actual Sony email
}

def get_tailored_email(company_name):
    if company_name == "Microsoft":
        subject = "Empowering AI Innovation: Request for Azure Student Credits & Microsoft Build"
        body = f"""Dear Microsoft University Relations Team,

My name is {YOUR_NAME}, and I am a third-year AI/Machine Learning Engineering student at SRM Institute of Science and Technology. I am a huge advocate for the Microsoft developer ecosystem. 

I am currently working on advanced deep learning projects. To train these resource-intensive models effectively, I am looking to leverage Azure's enterprise-grade cloud infrastructure. I was hoping to inquire if there are any Azure for Students grants or cloud computing credits available to help support my research. 

Additionally, I have been closely following the upcoming Microsoft Build conference. Attending this event would be a transformative opportunity. Could you let me know if Microsoft offers any sponsored student tickets for Build?

Thank you for building such incredible tools.

Best regards,
{YOUR_NAME}
SRM Institute of Science and Technology"""

    elif company_name == "NVIDIA":
        subject = "Accelerating AI: Request for GPU Compute Grants & GTC Student Access"
        body = f"""Dear NVIDIA Deep Learning Institute Team,

My name is {YOUR_NAME}, a third-year AI/ML Engineering student at SRM Institute of Science and Technology. I am a massive fan of NVIDIA's groundbreaking work in AI hardware and CUDA.

I am currently building complex simulation environments and training deep neural networks. Given NVIDIA's undisputed leadership in accelerated computing, I wanted to ask if there are any student programs or GPU compute grants available to support university researchers like myself.

Also, I am very eager to attend the next NVIDIA GTC. Does NVIDIA provide any student sponsorships or virtual access passes for the conference? 

Thank you for pushing the boundaries of AI.

Best regards,
{YOUR_NAME}
SRM Institute of Science and Technology"""

    elif company_name == "Bose":
        subject = "A Huge Student Fan Reaching Out! 🚀"
        body = f"""Dear Bose Team,

I hope you’re having a great week! 

My name is {YOUR_NAME}, a third-year AI engineering student at SRM Institute of Science and Technology. I am a massive fan of Bose and have always admired your industry-leading noise cancellation technology. 

As a student navigating a demanding workload, I spend hours coding in crowded libraries. I am currently saving up to upgrade my daily workflow with a pair of Bose QuietComfort headphones to help me focus. 

I was wondering if Bose ever sends out promotional goodies, care packages, or student discounts to your supporters? I would be absolutely thrilled to rock your gear! For reference, I wear a size L shirt.

Thank you for creating such amazing audio products!

Warmly,
{YOUR_NAME}"""

    elif company_name == "Sony":
        subject = "A Huge Student Fan Reaching Out! 🚀"
        body = f"""Dear Sony Team,

I hope you’re having a great week! 

My name is {YOUR_NAME}, a third-year AI engineering student at SRM Institute of Science and Technology. I have been a lifelong fan of Sony, from your incredible PlayStation ecosystem to your industry-leading audio gear.

As an engineering student, I am currently looking to upgrade my daily workflow and would love any support regarding Sony headphones or electronic accessories to help me power through long coding sessions. 

I know you receive countless messages, but I was wondering if Sony ever sends out promotional goodies, care packages, or product samples to student supporters? For reference, I typically wear a size L shirt, size 34-36 pants, and size 9 (Bata) shoes. 

Thank you for your time and for continuing to build phenomenal products!

Warmly,
{YOUR_NAME}"""

    else:
        subject = "Hello"
        body = "Test"
        
    return subject, body

def send_email(target_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = target_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        # Setup SMTP server (Gmail)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, APP_PASSWORD)
        
        text = msg.as_string()
        server.sendmail(EMAIL_ADDRESS, target_email, text)
        server.quit()
        
        print(f"[SUCCESS] Successfully sent email to {target_email} (Subject: {subject})")
    except Exception as e:
        print(f"[FAILED] Failed to send email to {target_email}. Error: {e}")

def main():
    print("Starting tailored email outreach (TEST RUN)...")
    
    for company, email in companies.items():
        print(f"Sending {company} email...")
        subject, body = get_tailored_email(company)
        send_email(email, subject, body)
        time.sleep(2) 

    print("Finished sending test emails! Check your inbox.")

if __name__ == "__main__":
    main()
