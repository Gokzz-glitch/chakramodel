import time
import datetime
import subprocess
import sys
import os

def wait_until_6am():
    now = datetime.datetime.now()
    # If it's before 6 AM, wait until 6 AM
    if now.hour < 6:
        # Calculate time until 6 AM today
        target = now.replace(hour=6, minute=0, second=0, microsecond=0)
        sleep_seconds = (target - now).total_seconds()
        print(f"[*] It's before 6 AM. Waiting {sleep_seconds/3600:.2f} hours until 6 AM...")
        time.sleep(sleep_seconds)

def main():
    print("==================================================")
    print(" CHAKRAMODEL AUTO-STARTER")
    print("==================================================")
    
    # 1. Wait 4 minutes
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Waiting 4 minutes for the system to settle...")
    time.sleep(240)
    
    # 2. Ensure it's past 6 AM
    wait_until_6am()
    
    # 3. Track days since first run
    start_date_file = "start_date.txt"
    if not os.path.exists(start_date_file):
        with open(start_date_file, "w") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d"))
        days_running = 0
    else:
        with open(start_date_file, "r") as f:
            start_date_str = f.read().strip()
            start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
            days_running = (datetime.datetime.now() - start_date).days

    print(f"[*] System has been running for {days_running} days.")
    
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Launching campaigns...")
    
    # Define absolute paths
    cwd = r"m:\chakramodel"
    
    # Start Email Campaign
    print("[*] Starting Email Campaign (today_campaign.py)...")
    email_process = subprocess.Popen([sys.executable, "-u", "today_campaign.py"], cwd=cwd)
    
    # Start College Email Campaign (Mon/Wed/Fri only, max 10/day)
    print("[*] Starting College Email Campaign (college_campaign.py)...")
    college_process = subprocess.Popen([sys.executable, "-u", "college_campaign.py"], cwd=cwd)
    
    # Start LinkedIn Bot
    print("[*] Starting LinkedIn Bot (linkedin_bot.py)...")
    linkedin_process = subprocess.Popen([sys.executable, "-u", "linkedin_bot.py"], cwd=cwd)
    
    # Start Opportunity Engine if on Day 7 or later (days >= 6)
    opp_process = None
    if days_running >= 6:
        print("[*] Phase 2 Activated: Starting Opportunity Engine (opportunity_engine.py)...")
        opp_process = subprocess.Popen([sys.executable, "-u", "opportunity_engine.py"], cwd=cwd)
    
    print("\n[*] All active campaigns are running in the background of this window.")
    print("[*] DO NOT CLOSE THIS WINDOW. It will close automatically when they finish.")
    
    # Wait for all to finish
    email_process.wait()
    college_process.wait()
    linkedin_process.wait()
    if opp_process:
        opp_process.wait()
        
    print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] All daily tasks completed successfully! Closing in 10 seconds...")
    time.sleep(10)

if __name__ == "__main__":
    main()
