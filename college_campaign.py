"""
College Email Campaign - HYPER-PERSONALIZED for Top-Priority Professors
Sends from 310624148027@eec.srmrmp.edu.in
- ALTERNATE DAYS ONLY (Mon/Wed/Fri)
- Max 8 emails/day
- 45-90 second delays between emails
- Each email individually researched and tailored to the professor's work
"""
import smtplib
import csv
import sys
import os
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

SENT_LOG = "college_sent_emails.txt"
SENDER_NAME = "Gokul R"
ATTACHMENTS = ["Gokul_Resume.pdf"]
DAILY_LIMIT = 8

# ==========================================
# HYPER-PERSONALIZED EMAILS
# Each one is hand-crafted based on deep research of the professor's actual publications
# ==========================================

PERSONALIZED_EMAILS = [
    # ---- TIER 1: DIRECT MATCH TO YOUR WORK (Colonoscopy AI) ----
    {
        "email": "mingazov-airat@coloproc.ru",
        "name": "Dr. Airat F. Mingazov",
        "subject": "PolypNet-3D: Addressing Temporal Flickering in Real-Time Colonoscopy AI (related to ArtInCol)",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Dr. Mingazov,</p>
  <p>I recently read your 2025 multicenter randomized clinical trial evaluating the <b>ArtInCol</b> system published in <i>Koloproktologia</i>. Your results are striking — a statistically significant increase in Adenoma Detection Rate from 41.3% to 47.2% across 1,128 patients and four institutions is exactly the kind of rigorous clinical validation the field needs.</p>
  <p>I am writing because my own project, <b>PolypNet-3D</b>, addresses a complementary challenge that I believe could directly enhance systems like ArtInCol. Specifically, we solve the <b>bounding-box temporal flickering problem</b> — when a real-time detection model correctly identifies a polyp in one frame but loses it in the next, causing unstable visual feedback for the endoscopist. Our approach uses:</p>
  <ul>
    <li>A <b>YOLOv8n + PraNet</b> cascaded pipeline for real-time detection with sub-pixel boundary refinement.</li>
    <li>A <b>Kalman filter persistence layer</b> that maintains stable bounding boxes across frames even when the model momentarily loses the polyp.</li>
    <li><b>TensorRT optimization</b> achieving 49 FPS on edge hardware, ensuring compatibility with standard endoscopic video systems (Olympus, Pentax, Fujifilm) — the same systems ArtInCol integrates with.</li>
  </ul>
  <p>I am a pre-final year (3rd year) undergraduate in AI & ML at Easwari Engineering College (SRM Group), Chennai, India. I would be deeply honoured to intern at the <b>Ryzhikh National Medical Research Center of Coloproctology</b> and contribute to ArtInCol's next iteration. I am flexible on dates and would be grateful for any accommodation/stipend support.</p>
  <p>My Resume is attached. Portfolio: <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Thank you for your time, Dr. Mingazov.<br><br>
  <b>Gokul R</b><br>
  310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    {
        "email": "artincol@alnisoft.ru",
        "name": "ArtInCol Engineering Team",
        "subject": "Temporal Consistency Module for ArtInCol - Potential Collaboration (PolypNet-3D)",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear ArtInCol / Alnisoft Engineering Team,</p>
  <p>I have been following ArtInCol's development closely — the integration with Legendo for automated report generation and real-time quality tracking is a very smart architectural choice. Your recent multicenter RCT demonstrating a 5.9% ADR uplift across 1,128 patients is compelling clinical evidence.</p>
  <p>I am reaching out because I have independently built a module that I believe could be a valuable addition to ArtInCol's detection pipeline. My project, <b>PolypNet-3D</b>, specifically addresses <b>temporal flickering</b> — the frame-to-frame instability of bounding boxes that can distract endoscopists during live procedures. My solution uses a Kalman filter persistence layer on top of YOLOv8n detections, achieving stable tracking at <b>49 FPS via TensorRT</b>.</p>
  <p>I am a 3rd year AI/ML undergraduate actively looking for an internship in real-time medical computer vision. I would love the opportunity to work with your engineering team at Alnisoft to integrate or test this temporal consistency approach within the ArtInCol architecture.</p>
  <p>Resume attached. Code on <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Best regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    {
        "email": "vasily.isakov@gmail.com",
        "name": "Dr. Vasily Isakov",
        "subject": "Real-Time Polyp Detection at 49 FPS — Regarding Your Review on AI for Endoscopic Screening",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Dr. Isakov,</p>
  <p>I read your comprehensive review on the effectiveness and application of AI for endoscopic screening of colorectal cancer with great interest. Your analysis highlighted several critical challenges — particularly around real-time inference speed and clinical integration — that my own project directly attempts to solve.</p>
  <p>I have built <b>PolypNet-3D</b>, a system that runs at <b>49 FPS on edge devices</b> using TensorRT-optimized YOLOv8n, with a Kalman filter layer for temporal persistence of detections across video frames. This directly addresses the real-time viability concern you raised in your review.</p>
  <p>I am a pre-final year undergraduate in AI & ML from India, actively seeking a research internship at the <b>Federal Research Center of Nutrition, Biotechnology and Food Safety</b>. I would be grateful for the opportunity to contribute to your ongoing work in AI-driven gastroenterology.</p>
  <p>Resume attached. Portfolio: <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>With warm regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    
    # ---- TIER 2: COMPUTATIONAL IMAGING & MEDICAL AI PROFESSORS ----
    {
        "email": "dmitry.dylov@skoltech.ru",
        "name": "Prof. Dmitry V. Dylov",
        "subject": "Anomaly Detection in Medical Imaging Meets Real-Time Endoscopy - Internship Inquiry",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Prof. Dylov,</p>
  <p>I have been reading your work at the Computational Imaging Lab with great admiration — particularly your paper on <i>\"Anomaly Detection in Medical Imaging with Deep Perceptual Autoencoders\"</i> (IEEE Access, 2020) and your more recent work on <i>\"Image Quality Assessment for Magnetic Resonance Imaging\"</i>. Your approach to combining fundamental principles of image formation with modern deep learning architectures is exactly the kind of rigorous methodology I aspire to follow.</p>
  <p>I am writing because my own project operates at a similar intersection of image quality and real-time clinical inference. I built <b>PolypNet-3D</b>, a real-time colonoscopy polyp detection system that addresses the <b>temporal flickering problem</b> — when detection models produce unstable bounding boxes across video frames. My solution uses:</p>
  <ul>
    <li><b>YOLOv8n + PraNet</b> cascaded detection with sub-pixel boundary refinement.</li>
    <li>A <b>Kalman filter persistence layer</b> for frame-to-frame detection stability.</li>
    <li><b>TensorRT optimization</b> achieving 49 FPS on edge hardware.</li>
  </ul>
  <p>I believe your lab's expertise in image quality assessment and anomaly detection could significantly inform the next phase of my work — particularly in handling noisy endoscopic video feeds where image quality varies dramatically.</p>
  <p>I am a pre-final year (3rd year) AI/ML undergraduate from Easwari Engineering College (SRM Group), Chennai, India. I would be deeply honoured to join your Computational Imaging Lab as a research intern. I am flexible with dates and would appreciate any accommodation/stipend support if available.</p>
  <p>Resume attached. Portfolio: <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Thank you for your time, Prof. Dylov.<br><br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    {
        "email": "e.burnaev@skoltech.ru",
        "name": "Prof. Evgeny Burnaev",
        "subject": "From 3D CAD Shapes to 3D Polyp Surfaces - Geometric Deep Learning for Medical Imaging",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Prof. Burnaev,</p>
  <p>Your <b>ABC dataset</b> paper (CVPR 2019) and CAD-Deform (ECCV 2020) fundamentally changed how I think about 3D geometric representations in deep learning. Your recent work on diffusion models for 3D alignment further demonstrates the potential of geometric methods for real-world vision tasks.</p>
  <p>I am reaching out because I see a natural extension of your geometric deep learning expertise into <b>medical imaging</b> — specifically, 3D polyp surface reconstruction from endoscopic video. My current project, <b>PolypNet-3D</b>, performs real-time 2D polyp detection at 49 FPS using YOLOv8 + Kalman filtering. The next frontier I want to explore is reconstructing the <b>3D morphology of detected polyps</b> from monocular endoscopic video — a problem that fundamentally requires the kind of manifold learning and geometric priors your lab specializes in.</p>
  <p>I am a pre-final year undergraduate in AI & ML from India, and I would be thrilled to join your AI Center at Skoltech as a research intern to explore this intersection of geometric deep learning and clinical endoscopy.</p>
  <p>Resume attached. Portfolio: <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Best regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    {
        "email": "panov.ai@mipt.ru",
        "name": "Prof. Aleksandr I. Panov",
        "subject": "Real-Time Object Navigation Meets Real-Time Polyp Detection — Internship Inquiry",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Prof. Panov,</p>
  <p>I have been reading your work at the Center for Cognitive Modeling and AIRI with great interest — particularly your IEEE Access paper on <i>\"Real-time Object Navigation with Deep Neural Networks and Hierarchical Reinforcement Learning\"</i> and your AAAI 2024 paper on decentralized lifelong multi-agent pathfinding. Your neurosymbolic approach to combining neural perception with symbolic planning is remarkably elegant.</p>
  <p>I am writing because the real-time perception challenges you solve in robotic navigation are architecturally very similar to the ones I face in medical video analysis. My project, <b>PolypNet-3D</b>, performs real-time polyp detection in live colonoscopy feeds using YOLOv8 + a Kalman filter persistence layer, optimized to 49 FPS via TensorRT. The core challenge — maintaining stable, temporally consistent object detection in a dynamic visual environment — mirrors the perception challenges in your embodied AI work.</p>
  <p>I am a 3rd year AI/ML undergraduate from India, and I would be honoured to join your Center for Cognitive Modeling as a research intern. I am particularly excited about potentially applying your hierarchical RL framework to adaptive detection thresholding in endoscopy.</p>
  <p>Resume attached. Portfolio: <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>With warm regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    
    # ---- TIER 3: CV/ML RESEARCHERS ----
    {
        "email": "vladislav.goncharenko@phystech.edu",
        "name": "Vladislav Goncharenko",
        "subject": "Object Detection + Temporal Tracking (Autonomous Driving -> Medical Endoscopy) - Internship Inquiry",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Mr. Goncharenko,</p>
  <p>I came across your work on neural networks for <b>object detection, segmentation, and tracking</b> in autonomous driving — specifically your experience leading perception teams working with multivariate data (images + LiDAR) at Evocargo. The core perception problem you solve — maintaining stable, real-time object tracking in a dynamic visual environment — is architecturally identical to what I face in medical endoscopy.</p>
  <p>My project, <b>PolypNet-3D</b>, performs real-time polyp detection in live colonoscopy video using YOLOv8n + a Kalman filter persistence layer to eliminate bounding-box temporal flickering. I optimized it to 49 FPS via TensorRT. The tracking challenge is essentially the same as yours: an object (polyp/vehicle) appears, disappears behind occlusion, and must be re-associated across frames in real time.</p>
  <p>I am a 3rd year AI/ML undergraduate from India, and I would love to learn from your expertise in perception systems at MIPT. If you have any research or TA positions available, I would be very grateful for the opportunity.</p>
  <p>Resume attached. Portfolio: <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Best regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    {
        "email": "neychev@phystech.edu",
        "name": "Radoslav Neychev",
        "subject": "Deep Learning for Real-Time Medical Video Analysis — Internship Inquiry at MIPT",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Mr. Neychev,</p>
  <p>I have been following your deep learning and reinforcement learning research at MIPT. Your work on applying modern DL architectures to practical perception tasks resonates strongly with my own project.</p>
  <p>I built <b>PolypNet-3D</b> — a real-time colonoscopy polyp detection system that solves the temporal flickering problem using a YOLOv8 + Kalman filter pipeline, optimized to 49 FPS with TensorRT. The next direction I want to explore is using <b>reinforcement learning</b> to adaptively adjust detection confidence thresholds based on video quality — a problem where your RL expertise would be invaluable.</p>
  <p>I am a 3rd year AI/ML undergraduate from India, actively seeking a research internship at MIPT. I would be grateful for any opportunity to work in your group.</p>
  <p>Resume attached. Portfolio: <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Best regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    {
        "email": "nikolay.karpachev@phystech.edu",
        "name": "Nikolay Karpachev",
        "subject": "Real-Time Medical Computer Vision — Internship Inquiry at MIPT",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Mr. Karpachev,</p>
  <p>I have been following your computer vision and machine learning research at MIPT. I am reaching out because my current project involves applying modern CV techniques to a challenging real-time medical imaging problem.</p>
  <p>I built <b>PolypNet-3D</b>, a real-time colonoscopy polyp detection system using YOLOv8n with a Kalman filter for temporal tracking stability, optimized to 49 FPS via TensorRT for edge deployment. The pipeline handles sub-pixel boundary refinement using PraNet and solves the common bounding-box flickering issue in live medical video feeds.</p>
  <p>I am a 3rd year AI/ML undergraduate from India, seeking a research internship at MIPT. If you have any openings or could point me in the right direction, I would be very grateful.</p>
  <p>Resume attached. Portfolio: <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>Best regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    {
        "email": "info-isp@ispras.ru",
        "name": "Research Center for Trusted AI",
        "subject": "µ-Net vs PolypNet-3D: Complementary Approaches to Colorectal Polyp Segmentation — Internship Inquiry",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Sir/Madam,</p>
  <p>I recently read the paper on the <b>µ-Net framework</b> for colorectal polyp segmentation with explainable AI, authored by Maria Lapina and Mikhail Babenko at your Research Center for Trusted AI. The integration of explainability into the segmentation pipeline is a critical contribution — clinicians need to trust the AI's decisions, and your approach directly addresses that trust gap.</p>
  <p>I am writing because my own project, <b>PolypNet-3D</b>, tackles a complementary problem: <b>temporal consistency</b> of polyp detections across video frames. While µ-Net focuses on per-frame segmentation quality and explainability, PolypNet-3D ensures that detections remain stable over time using a Kalman filter persistence layer, running at 49 FPS via TensorRT.</p>
  <p>I believe combining µ-Net's explainable segmentation with PolypNet-3D's temporal consistency could create a uniquely powerful clinical tool. I am a 3rd year AI/ML undergraduate from India, seeking a research internship at ISP RAS to explore this direction.</p>
  <p>Resume attached. Portfolio: <a href="https://github.com/Gokzz-glitch" style="color:#0056b3;font-weight:bold;">GitHub</a>.</p>
  <p>With warm regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    {
        "email": "computerscience@hse.ru",
        "name": "Faculty of Computer Science",
        "subject": "Research Internship Inquiry — Real-Time Medical Computer Vision (PolypNet-3D)",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Faculty of Computer Science,</p>
  <p>I am writing to inquire about research internship opportunities at HSE University's Faculty of Computer Science, specifically within your AI for medicine or biomedical research groups.</p>
  <p>I am Gokul R, a pre-final year undergraduate in AI & ML from India. I have built <b>PolypNet-3D</b>, a real-time colonoscopy polyp detection system using YOLOv8n + Kalman filtering, optimized to 49 FPS via TensorRT for edge deployment. I am seeking a research internship where I can apply my skills in real-time medical computer vision.</p>
  <p>I would be grateful if you could forward this to any faculty members whose research aligns with medical imaging, computer vision, or clinical AI. Resume attached.</p>
  <p>Best regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
    {
        "email": "sciencesechenov@yandex.ru",
        "name": "Biomedical Science & Technology Park",
        "subject": "Research Internship — AI for Clinical Diagnostics (Real-Time Colonoscopy Detection System)",
        "body": """<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;line-height:1.75;">
  <p>Dear Sechenov Biomedical Science & Technology Park,</p>
  <p>I am writing to inquire about research internship opportunities at Sechenov University's Institute of Digital Medicine and School of Intelligent Theranostics Systems.</p>
  <p>I have built <b>PolypNet-3D</b>, a real-time AI system for colonoscopy polyp detection optimized for edge deployment (49 FPS via TensorRT). The system uses YOLOv8n with a Kalman filter persistence layer to provide temporally stable detections for endoscopists. I believe this project demonstrates my ability to bridge the gap between AI engineering and clinical practice — which is exactly the mission of your institute.</p>
  <p>I am a pre-final year AI/ML undergraduate from Easwari Engineering College (SRM Group), India. I would be honoured to contribute to Sechenov's digital medicine research. Resume attached.</p>
  <p>Best regards,<br><b>Gokul R</b><br>310624148027@eec.srmrmp.edu.in</p>
</div>"""
    },
]

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

def connect_college_smtp(email, pwd):
    s = smtplib.SMTP_SSL("smtp.gmail.com", 465)
    s.login(email, pwd)
    return s

def build_msg(sender, to_email, subject, html):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"{SENDER_NAME} <{sender}>"
    msg["To"] = to_email
    
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

def main():
    today = datetime.now()
    
    # ALTERNATE DAYS: Mon(0), Wed(2), Fri(4)
    if today.weekday() not in [0, 2, 4]:
        print(f"[*] Today is {today.strftime('%A')}. College email sends on Mon/Wed/Fri only.")
        print("[*] Skipping to protect your college account.")
        return
    
    load_env()
    college_email = os.environ.get("COLLEGE_EMAIL")
    college_pwd = os.environ.get("COLLEGE_APP_PASSWORD")
    
    if not college_email or not college_pwd:
        print("ERROR: COLLEGE_EMAIL or COLLEGE_APP_PASSWORD not set in .env")
        sys.exit(1)
    
    sent_set = load_sent()
    
    # Filter to unsent emails only
    targets = [e for e in PERSONALIZED_EMAILS if e["email"].lower() not in sent_set]
    targets = targets[:DAILY_LIMIT]
    
    if not targets:
        print("[*] All top-priority professors have already been emailed from college account!")
        return
    
    print("=" * 60)
    print(f"COLLEGE EMAIL CAMPAIGN - {today.strftime('%A %B %d, %Y')}")
    print(f"From: {college_email}")
    print(f"Targets: {len(targets)} (limit: {DAILY_LIMIT}/day)")
    print("=" * 60)
    
    for filename in ATTACHMENTS:
        if not os.path.exists(filename):
            print(f"[WARNING] Attachment '{filename}' not found.")
    
    server = None
    try:
        server = connect_college_smtp(college_email, college_pwd)
        print("College SMTP: Connected\n")
    except Exception as e:
        print(f"College SMTP: FAILED ({e})")
        return
    
    sent_count = 0
    for entry in targets:
        email = entry["email"]
        subject = entry["subject"]
        body = entry["body"]
        name = entry["name"]
        
        print(f"  [COLLEGE] [{sent_count+1}/{len(targets)}] {name} ({email})")
        print(f"            Subject: {subject[:60]}...")
        sys.stdout.flush()
        
        try:
            msg = build_msg(college_email, email, subject, body)
            try:
                server.sendmail(college_email, email, msg.as_string())
            except smtplib.SMTPServerDisconnected:
                server = connect_college_smtp(college_email, college_pwd)
                server.sendmail(college_email, email, msg.as_string())
            
            print(f"            -> SENT OK")
            log_sent(email)
            sent_set.add(email.lower())
            sent_count += 1
            
            # Safety delay: 45-90 seconds (increases with each email)
            delay = 45 + (sent_count * 6)
            print(f"            Waiting {delay}s...")
            time.sleep(delay)
            
        except Exception as e:
            print(f"            -> FAILED: {e}")
    
    if server:
        try: server.quit()
        except: pass
    
    print(f"\n{'='*60}")
    print(f"Done! Sent {sent_count}/{len(targets)} emails from college account.")
    print(f"Next college email day: {'Wednesday' if today.weekday() == 0 else 'Friday' if today.weekday() == 2 else 'Monday'}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
