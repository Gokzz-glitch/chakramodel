import time
import sys

log_file = sys.argv[1]
target = 0.931

print(f"Monitoring {log_file} for SOTA target {target}...")

while True:
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            lines = content.split('\n')
            
            for line in lines:
                if "★ NEW BEST Dice:" in line:
                    try:
                        score = float(line.split("Dice:")[1].split(" @")[0])
                        if score >= target:
                            print(f"\n[GOAL ACHIEVED] Model outperformed SOTA! Score: {score} >= {target}")
                            sys.exit(0)
                    except Exception:
                        pass
                
                if "All combinations complete!" in line:
                    print(f"\n[FAILED] Training finished all combos but failed to reach {target}.")
                    sys.exit(2)
                
                if "Traceback" in line:
                    print(f"\n[CRASH] Training crashed! Traceback found.")
                    sys.exit(1)
    except FileNotFoundError:
        print("Log file not found yet, waiting...")
    
    time.sleep(15)
