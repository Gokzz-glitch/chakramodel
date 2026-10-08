import json
import time
import os
import sys
import re
from pathlib import Path
import pywhatkit

# Ensure outreach.py can be imported
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.append(str(SCRIPT_DIR))
from outreach import generate_whatsapp_message, is_valid_mobile

def main():
    # Base configuration
    output_dir = SCRIPT_DIR.parent.parent / "output"
    input_path = output_dir / "scored_leads.json"
    
    if not input_path.exists():
        print(f"❌ Could not find {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        leads = json.load(f)

    # Filter HOT leads only
    leads = [l for l in leads if "HOT" in l.get("score_label", "")]

    if not leads:
        print("❌ No HOT leads found to message.")
        return

    # Assuming the GitHub Pages URL structure from your deployment
    base_preview_url = "https://Gokzz-glitch.github.io/autoweb-sites"

    print("================================================================")
    print(f"🚀 WhatsApp Automation Starting for {len(leads)} HOT leads!")
    print("================================================================")
    print("⚠️ WARNING: DO NOT TOUCH YOUR MOUSE OR KEYBOARD while this runs!")
    print("⚠️ 1. Make sure your default browser has WhatsApp Web logged in.")
    print("⚠️ 2. Make sure your default browser is not minimized.")
    print("⚠️ 3. Sit back and watch the magic happen.")
    print("================================================================\n")
    
    # Give user 10 seconds to switch to their browser and leave the mouse alone
    for i in range(10, 0, -1):
        print(f"Starting in {i} seconds...", end="\r")
        time.sleep(1)
    print("\n🚀 GO!")

    success_count = 0
    
    for i, lead in enumerate(leads, 1):
        phone = lead.get("phone_international", "") or lead.get("phone_national", "")
        name = lead.get("name", "Unknown Business")
        
        clean_phone = is_valid_mobile(phone)
        
        if not clean_phone:
            print(f"[{i}/{len(leads)}] ⏭️ Skipping {name} - Invalid or landline number ({phone}).")
            continue

        # Construct Preview URL
        safe_name = re.sub(r'[^\w\s-]', '', name).strip()
        safe_name = re.sub(r'[-\s]+', '-', safe_name).lower()
        preview_url = f"{base_preview_url}/{safe_name}"
        
        # Generate the exact message
        msg = generate_whatsapp_message(lead, preview_url)
        
        print(f"\n[{i}/{len(leads)}] 📨 Sending to {name} ({clean_phone})...")
        
        try:
            # sendwhatmsg_instantly automatically opens the browser, types the message, and hits enter.
            # wait_time=20 seconds for the browser to open and WhatsApp web to load completely.
            # tab_close=True will close the tab after sending.
            # close_time=5 seconds to wait after sending before closing the tab.
            pywhatkit.sendwhatmsg_instantly(
                phone_no=clean_phone,
                message=msg,
                wait_time=20,
                tab_close=True,
                close_time=5
            )
            success_count += 1
            print(f"   ✅ Successfully sent!")
            
            # Anti-ban delay: Wait 15-20 seconds before starting the next one.
            print("   ⏳ Waiting 15 seconds before next message to avoid WhatsApp ban...")
            time.sleep(15)
            
        except Exception as e:
            print(f"   ❌ Failed to send to {name}: {e}")
            
    print(f"\n🎉 Automation Complete! Successfully sent {success_count} messages.")

if __name__ == "__main__":
    main()
