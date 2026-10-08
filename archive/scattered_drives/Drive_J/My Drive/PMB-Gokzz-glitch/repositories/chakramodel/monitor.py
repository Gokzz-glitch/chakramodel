import time
import os
import sys

TARGET = 240
LOG_FILE = "sent_emails.txt"

def get_sent_count():
    if not os.path.exists(LOG_FILE):
        return 0
    with open(LOG_FILE, 'r') as f:
        return sum(1 for line in f if line.strip())

def draw_progress_bar(current, total, bar_length=50):
    percent = float(current) / total
    arrow = '=' * int(round(percent * bar_length) - 1) + '>'
    spaces = ' ' * (bar_length - len(arrow))
    
    sys.stdout.write(f"\rProgress: [{arrow}{spaces}] {current}/{total} ({percent*100:.1f}%)")
    sys.stdout.flush()

if __name__ == "__main__":
    print("Email Campaign Monitor - Press Ctrl+C to exit")
    try:
        while True:
            count = get_sent_count()
            draw_progress_bar(count, TARGET)
            if count >= TARGET:
                print("\nCampaign complete!")
                break
            time.sleep(2)  # Update every 2 seconds
    except KeyboardInterrupt:
        print("\nMonitor stopped.")
