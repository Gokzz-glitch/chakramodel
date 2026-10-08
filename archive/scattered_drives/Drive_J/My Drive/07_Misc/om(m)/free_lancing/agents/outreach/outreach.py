#!/usr/bin/env python3
"""
AutoWeb Outreach Agent
========================
Sends personalized pitch messages to discovered leads via email.
Prepares WhatsApp messages for manual/semi-manual sending.

Usage:
    python outreach.py --input ../output/scored_leads.json --channel email --top 10
    python outreach.py --input ../output/scored_leads.json --channel whatsapp --hot-only
    python outreach.py --preview  # Just preview messages without sending
"""

import argparse
import json
import os
import re
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SCRIPT_DIR = Path(__file__).resolve().parent


# ─── Message Templates ──────────────────────────────────────────────────────

def generate_email_html(lead: dict, preview_url: str = "") -> str:
    """Generate a professional HTML email for outreach."""
    business_name = lead.get("name", "Your Business")
    rating = lead.get("rating", 0)
    review_count = lead.get("review_count", 0)
    brand_name = os.getenv("BRAND_NAME", "AutoWeb")
    brand_phone = os.getenv("BRAND_PHONE", "+91-XXXXXXXXXX")
    brand_email = os.getenv("BRAND_EMAIL", "hello@autoweb.in")

    preview_section = ""
    if preview_url:
        preview_section = f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 24px; margin: 20px 0; text-align: center;">
            <p style="color: #fff; font-size: 16px; margin: 0 0 16px;">🎁 We've created a FREE website preview for you!</p>
            <a href="{preview_url}" style="display: inline-block; background: #fff; color: #764ba2; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px;">View Your Preview Website →</a>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; color: #333;">
        <div style="background: #f8f9fa; border-radius: 16px; padding: 32px; border: 1px solid #e9ecef;">
            <h2 style="color: #1a1a2e; margin-top: 0;">Hi {business_name}! 👋</h2>

            <p>I noticed your business has <strong>{rating}⭐ rating</strong> with <strong>{review_count} reviews</strong> on Google Maps — that's impressive! 🎉</p>

            <p>However, I noticed you don't have a website yet. In today's digital world, a professional website can help you:</p>

            <ul style="line-height: 2;">
                <li>✅ Get found on <strong>Google Search</strong> (not just Maps)</li>
                <li>✅ Show your <strong>services and pricing</strong> to new customers</li>
                <li>✅ Build <strong>trust and credibility</strong> instantly</li>
                <li>✅ Share your <strong>WhatsApp/phone number</strong> easily</li>
            </ul>

            {preview_section}

            <div style="background: #fff; border-radius: 8px; padding: 20px; margin: 20px 0; border: 2px solid #28a745;">
                <p style="margin: 0; font-size: 18px; color: #28a745; font-weight: bold;">💰 Our websites start at just ₹4,000</p>
                <p style="margin: 8px 0 0; color: #666;">One-time payment. No monthly fees. The website is yours forever.</p>
            </div>

            <p><strong>What you get:</strong></p>
            <ul style="line-height: 2;">
                <li>📱 Beautiful, mobile-friendly design</li>
                <li>⚡ Lightning-fast loading speed</li>
                <li>🔍 SEO optimized for Google</li>
                <li>📍 Google Maps integration</li>
                <li>📞 Click-to-call button</li>
                <li>🆓 Free hosting included</li>
            </ul>

            <p>Would you like to discuss this? I'd love to help {business_name} reach more customers online.</p>

            <p style="margin-top: 24px;">
                Best regards,<br>
                <strong>{brand_name}</strong><br>
                📞 {brand_phone}<br>
                📧 {brand_email}
            </p>
        </div>

        <p style="text-align: center; color: #999; font-size: 12px; margin-top: 16px;">
            You're receiving this because your business is listed on Google Maps. 
            <a href="mailto:{brand_email}?subject=Unsubscribe" style="color: #999;">Unsubscribe</a>
        </p>
    </body>
    </html>
    """


def generate_whatsapp_message(lead: dict, preview_url: str = "") -> str:
    """Generate a WhatsApp-friendly plain text message."""
    business_name = lead.get("name", "Your Business")
    rating = lead.get("rating", 0)
    review_count = lead.get("review_count", 0)
    brand_name = os.getenv("BRAND_NAME", "AutoWeb")
    brand_phone = os.getenv("BRAND_PHONE", "+91-XXXXXXXXXX")

    preview_line = ""
    if preview_url:
        preview_line = f"\nTo show you what's possible, my team built a custom website preview for *{business_name}*, completely free of charge. You can view it here:\n🔗 {preview_url}\n"

    return f"""Hi *{business_name}* team, 👋

My name is {brand_name}. I was looking for local services and came across your profile on Google Maps. You have a fantastic reputation (*{rating}⭐ across {review_count} reviews*)! 👏

I did notice, however, that you don't currently have a website listed. A lot of your potential customers might be searching for your services online and going to competitors who have a web presence.
{preview_line}
If you like it, we can make it officially yours and set it up on your own domain. Our pricing is very affordable for local businesses (a one-time fee of just ₹4,000, with no monthly maintenance costs).

Let me know if you're interested or if you'd like to see any changes to the design!

Best regards,
*{brand_name}*
📞 {brand_phone}"""


def is_valid_mobile(phone_str: str) -> str | None:
    """Validates and formats an Indian mobile number. Returns None if invalid/landline."""
    if not phone_str:
        return None
    digits = re.sub(r'\D', '', phone_str)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    
    if len(digits) == 10 and digits[0] in "6789":
        return "+91" + digits
    return None


def generate_tamil_whatsapp_message(lead: dict, preview_url: str = "") -> str:
    """Generate a WhatsApp message in Tamil + English mix."""
    business_name = lead.get("name", "Your Business")
    rating = lead.get("rating", 0)
    brand_name = os.getenv("BRAND_NAME", "AutoWeb")
    brand_phone = os.getenv("BRAND_PHONE", "+91-XXXXXXXXXX")

    preview_line = ""
    if preview_url:
        preview_line = f"\n🎁 உங்கள் business-க்கு FREE preview website உருவாக்கியுள்ளோம்:\n🔗 {preview_url}\n"

    return f"""வணக்கம் *{business_name}*! 👋

Google Maps-ல் உங்கள் business-ஐ பார்த்தேன் — *{rating}⭐ rating!* 👏
{preview_line}
உங்கள் business-க்கு ஒரு professional website இருந்தால்:
✅ Google Search-ல் வாடிக்கையாளர்கள் எளிதாக கண்டுபிடிக்கலாம்
✅ Services & pricing காட்டலாம்
✅ நம்பகத்தன்மை அதிகரிக்கும்

💰 *Website ₹4,000 மட்டுமே* (ஒரே முறை payment)
மாதாந்திர கட்டணம் இல்லை!

📱 Mobile-friendly design
⚡ வேகமான loading
🔍 Google SEO optimized

ஆர்வமா? Reply பண்ணுங்க! 🙏

— *{brand_name}*
📞 {brand_phone}"""


# ─── Email Sending ───────────────────────────────────────────────────────────

def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email via SMTP."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not smtp_email or not smtp_password:
        print("  ❌ SMTP credentials not configured in .env")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_email
    msg["To"] = to_email

    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"  ❌ Email failed: {e}")
        return False


# ─── CLI Interface ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="📧 AutoWeb Outreach — Send pitch messages to leads",
    )
    parser.add_argument("--input", type=str, help="Path to scored_leads.json")
    parser.add_argument("--channel", choices=["email", "whatsapp", "whatsapp-tamil"], default="whatsapp",
                        help="Outreach channel")
    parser.add_argument("--top", type=int, help="Process top N leads")
    parser.add_argument("--hot-only", action="store_true", help="Only HOT leads")
    parser.add_argument("--preview", action="store_true", help="Preview messages without sending")
    parser.add_argument("--preview-url", type=str, default="", help="Base URL for website previews")

    args = parser.parse_args()

    # Load leads
    default_input = SCRIPT_DIR.parent.parent / "output" / "scored_leads.json"
    input_path = args.input or str(default_input)

    if not os.path.exists(input_path):
        print(f"❌ No leads file found at {input_path}")
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        leads = json.load(f)

    # Filter
    if args.hot_only:
        leads = [l for l in leads if "HOT" in l.get("score_label", "")]
    if args.top:
        leads = leads[:args.top]

    print(f"📋 Processing {len(leads)} leads via {args.channel}")
    print(f"{'='*60}\n")

    # Generate and optionally send messages
    for i, lead in enumerate(leads, 1):
        name = lead.get("name", "Unknown")
        phone = lead.get("phone_national", "") or lead.get("phone_international", "")
        score = lead.get("score_label", "")

        print(f"{'─'*60}")
        print(f"Lead #{i}: {name} {score}")
        print(f"📞 Phone: {phone}")
        print(f"📍 {lead.get('address', 'N/A')}")

        # Build preview URL if available
        preview_url = args.preview_url
        if preview_url and not preview_url.endswith("/"):
            safe_name = re.sub(r'[^\w\s-]', '', name).strip()
            safe_name = re.sub(r'[-\s]+', '-', safe_name).lower()
            preview_url = f"{preview_url}/{safe_name}"
            
        clean_phone = is_valid_mobile(phone)

        if args.channel == "whatsapp":
            if not clean_phone:
                print(f"  ⚠️  Skipping WhatsApp message for {name} - Invalid or landline number ({phone})")
                continue
                
            msg = generate_whatsapp_message(lead, preview_url)
            print(f"\n📱 WhatsApp Message:\n")
            print(msg)
            if not args.preview:
                # Generate WhatsApp click-to-chat link
                clean_phone_url = clean_phone.replace("+", "")
                wa_link = f"https://wa.me/{clean_phone_url}?text={__import__('urllib.parse', fromlist=['quote']).quote(msg)}"
                print(f"\n🔗 Click to send: {wa_link}")

        elif args.channel == "whatsapp-tamil":
            msg = generate_tamil_whatsapp_message(lead, preview_url)
            print(f"\n📱 WhatsApp Message (Tamil):\n")
            print(msg)

        elif args.channel == "email":
            html = generate_email_html(lead, preview_url)
            if args.preview:
                # Save preview to file
                preview_dir = SCRIPT_DIR.parent / "output" / "email_previews"
                os.makedirs(preview_dir, exist_ok=True)
                safe_name = name.lower().replace(" ", "-")
                preview_path = preview_dir / f"{safe_name}.html"
                preview_path.write_text(html, encoding="utf-8")
                print(f"  📧 Email preview saved: {preview_path}")
            else:
                # Would need email address — for now, log
                print(f"  ⚠️  Email sending requires email addresses (not available from Google Maps)")
                print(f"  💡 Consider using email finder services or in-person outreach")

        print()

    # Summary
    print(f"\n{'='*60}")
    print(f"✅ Processed {len(leads)} leads")
    if args.channel == "whatsapp":
        print(f"💡 Copy-paste WhatsApp messages or use the click-to-send links above")
    elif args.channel == "email":
        print(f"💡 Email previews saved to output/email_previews/")


if __name__ == "__main__":
    main()
