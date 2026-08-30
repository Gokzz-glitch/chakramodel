import time
import os
import csv
import random
import urllib.parse
import sys

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==========================================
# CONFIGURATION
# ==========================================
TARGET_FILES = [
    "priority_5_foreign_and_top_institutions.csv",
    "priority_1_colonoscopy_ai.csv",
    "priority_2_endoscopy_ai.csv"
]
LOG_FILE = "linkedin_contacted.txt"
DAILY_LIMIT = 6 # Extremely conservative limit to guarantee account safety

# ==========================================
# TEMPLATES
# ==========================================
def get_note(first_name):
    note = f"Hi {first_name}, I'm an AI undergrad building PolypNet-3D: a YOLOv8+Kalman pipeline hitting 49 FPS for real-time colonoscopy polyp detection. I admire your work and would love to connect to follow your research!"
    return note[:300]

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

def load_contacted():
    if not os.path.exists(LOG_FILE): return set()
    with open(LOG_FILE, encoding="utf-8") as f:
        return set(line.strip().lower() for line in f if line.strip())

def log_contact(track_key):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(track_key.lower() + "\n")

def read_leads():
    leads = []
    for f in TARGET_FILES:
        if not os.path.exists(f): continue
        with open(f, encoding="utf-8") as file:
            for row in csv.DictReader(file):
                leads.append(row)
    return leads

def delay(min_s=3, max_s=8):
    time.sleep(random.uniform(min_s, max_s))

# ==========================================
# BOT LOGIC
# ==========================================
def init_driver():
    print("[*] Initializing undetectable Chrome driver...")
    options = uc.ChromeOptions()
    options.add_argument("--disable-popup-blocking")
    # Force version 151 to match the user's installed Chrome browser
    driver = uc.Chrome(options=options, version_main=151)
    driver.maximize_window()
    return driver

def login_linkedin(driver, email, pwd):
    print("[*] Logging into LinkedIn...")
    driver.get("https://www.linkedin.com/login")
    delay(3, 5)
    
    username_field = driver.find_element(By.ID, "username")
    username_field.send_keys(email)
    delay(2, 4)
    
    password_field = driver.find_element(By.ID, "password")
    password_field.send_keys(pwd)
    delay(1, 3)
    
    password_field.send_keys(Keys.RETURN)
    delay(8, 12)
    
    if "feed" not in driver.current_url.lower():
        print("[!] Login might have failed, or requires verification. Please solve it in the browser.")
        input("Press Enter here in the terminal once you are logged in and on the feed page...")

def send_connection_request(driver, name, affiliation):
    first_name = name.split()[0] if name else "there"
    
    query = urllib.parse.quote(f"{name} {affiliation}")
    url = f"https://www.linkedin.com/search/results/people/?keywords={query}"
    driver.get(url)
    delay(6, 10) # Wait for page to fully load
    
    try:
        buttons = driver.find_elements(By.TAG_NAME, "button")
        connect_btn = None
        for btn in buttons:
            if btn.text.strip().lower() == "connect":
                connect_btn = btn
                break
                
        if not connect_btn:
            print(f"[-] No 'Connect' button found for {name}. They might be 3rd+ degree.")
            return False
            
        connect_btn.click()
        delay(3, 5)
        
        note_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Add a note')]")
        if note_btns:
            note_btns[0].click()
            delay(2, 4)
            
            textbox = driver.find_element(By.NAME, "message")
            textbox.send_keys(get_note(first_name))
            delay(3, 6)
            
            send_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Send')]")
            if send_btns:
                send_btns[0].click()
                print(f"[+] Sent connection request to {name}")
                delay(4, 7)
                return True
                
        print(f"[-] Failed to send note to {name}")
        return False
        
    except Exception as e:
        print(f"[-] Error processing {name}: {e}")
        return False

def is_indian(contact):
    email = contact.get("Email", "").lower()
    affil = contact.get("Affiliation", "").lower()
    indian_domains = ['.in', 'iit', 'nit', 'aiims', 'bits', 'iiit', 'isb', 'iim']
    if any(d in email for d in indian_domains): return True
    indian_keywords = ['india', 'delhi', 'mumbai', 'bangalore', 'bengaluru', 'chennai', 'hyderabad', 'kolkata', 'pune', 'kanpur', 'kharagpur', 'madras', 'roorkee', 'guwahati']
    if any(k in affil for k in indian_keywords): return True
    return False

def main():
    load_env()
    email = os.environ.get("LINKEDIN_EMAIL")
    pwd = os.environ.get("LINKEDIN_PASSWORD")
    
    if not email or not pwd:
        print("ERROR: LINKEDIN_EMAIL or LINKEDIN_PASSWORD not set in .env")
        print("Please add them to the .env file.")
        sys.exit(1)
        
    contacted = load_contacted()
    all_leads = read_leads()
    
    indian_leads = []
    foreign_leads = []
    
    for lead in all_leads:
        em = lead.get("Email", "").strip().lower()
        track_key = em if em else lead.get("Name", "").strip().lower()
        if not track_key or track_key in contacted: continue
        
        lead["track_key"] = track_key
        if is_indian(lead):
            indian_leads.append(lead)
        else:
            foreign_leads.append(lead)
            
    target_each = DAILY_LIMIT // 2
    targets = []
    
    indians_to_add = min(target_each, len(indian_leads))
    targets.extend(indian_leads[:indians_to_add])
    
    foreign_to_add = min(target_each, len(foreign_leads))
    targets.extend(foreign_leads[:foreign_to_add])
    
    remaining_spots = DAILY_LIMIT - len(targets)
    if remaining_spots > 0:
        if indians_to_add < target_each:
            targets.extend(foreign_leads[foreign_to_add:foreign_to_add + remaining_spots])
        elif foreign_to_add < target_each:
            targets.extend(indian_leads[indians_to_add:indians_to_add + remaining_spots])
        
    if not targets:
        print("[*] No more leads found!")
        return
        
    print(f"[*] Starting bot for {len(targets)} targets (Indian: {indians_to_add}, Foreign: {len(targets)-indians_to_add}). Daily limit: {DAILY_LIMIT}")
    print("[*] Using heavy delays (3-5 minutes per request) for maximum safety.")
    
    driver = init_driver()
    try:
        login_linkedin(driver, email, pwd)
        
        sent_count = 0
        for lead in targets:
            name = lead.get("Name", "Researcher")
            affiliation = lead.get("Affiliation", "")
            print(f"\n[*] Processing: {name} ({affiliation})...")
            
            success = send_connection_request(driver, name, affiliation)
            if success:
                log_contact(lead["track_key"])
                sent_count += 1
                wait_time = random.uniform(180, 300) # 3 to 5 minutes
                print(f"    --> Success. Sleeping for {int(wait_time/60)}m {int(wait_time%60)}s to avoid ban...")
                time.sleep(wait_time)
            else:
                log_contact(lead["track_key"])
                delay(10, 20)
                
        print(f"\n[*] Done for today! Successfully sent {sent_count} connection requests.")
        
    finally:
        print("[*] Closing browser in 5 seconds...")
        time.sleep(5)
        driver.quit()

def trigger_omni_channel(name, affiliation):
    load_env()
    email = os.environ.get("LINKEDIN_EMAIL")
    pwd = os.environ.get("LINKEDIN_PASSWORD")
    if not email or not pwd:
        print("Omni-Channel skipped: LinkedIn credentials missing.")
        return False
        
    driver = init_driver()
    try:
        login_linkedin(driver, email, pwd)
        success = send_connection_request(driver, name, affiliation)
        return success
    except Exception as e:
        print(f"Omni-Channel Error: {e}")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
