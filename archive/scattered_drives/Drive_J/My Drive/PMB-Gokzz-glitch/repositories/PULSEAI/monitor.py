import psutil # pyre-ignore[21]

import time
from datetime import datetime
import winsound

def check_hardware():
    cpu = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory().percent
    
    msg = f"[{datetime.now().isoformat()}] CPU: {cpu}%, RAM: {ram}%"
    print(msg, end='\r')
    
    if cpu > 50 or ram > 50:
        warning = f"\n[{datetime.now().isoformat()}] WARNING: CPU/RAM usage exceeded 50% (CPU: {cpu}%, RAM: {ram}%). Please ensure tasks are offloaded to Colab.\n"
        print(warning)
        with open('hardware_log.txt', 'a') as f:
            f.write(warning)
        # Beep to alert user (only if on Windows and Beep exists)
        # Beep to alert user (only if on Windows)
        try:
            if hasattr(winsound, "Beep"):
                winsound.Beep(1000, 500) # type: ignore
        except (AttributeError, Exception):
            print("\a") # Standard terminal bell fallback

print("Starting hardware monitor (limit 60% CPU)...")
while True:
    check_hardware()
    time.sleep(2)
