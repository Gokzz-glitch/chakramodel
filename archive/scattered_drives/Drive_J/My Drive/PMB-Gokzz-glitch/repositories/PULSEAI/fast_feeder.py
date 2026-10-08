import httpx # pyre-ignore[21]
import math
import time

import itertools

print("🫀 PulseAI Live Feeder — streaming ECG data to localhost:8000...")
print("   Press Ctrl+C to stop.\n")

errors: int = 0
try:
    for i in itertools.count():
        # Realistic ECG-like shape: baseline + P-wave + QRS-complex + T-wave
        curr_i: int = i
        cycle = curr_i % 50
        if   cycle == 0:                  v = 0.0          # baseline
        elif cycle == 5:                  v = 0.15         # P-wave
        elif cycle == 10:                 v = 0.05         # PR segment
        elif cycle == 15:                 v = -0.3         # Q-dip
        elif cycle == 16:                 v = 1.8          # R-peak (tall spike)
        elif cycle == 17:                 v = -0.4         # S-wave
        elif cycle == 18:                 v = 0.0          # ST segment
        elif 25 <= cycle <= 30:           v = 0.2          # T-wave hump
        else:                             v = 0.0 + math.sin(curr_i * 0.03) * 0.02  # noise floor

        try:
            httpx.post(f"http://127.0.0.1:8000/api/ingest?value={v:.5f}", timeout=1.0)
            errors = 0
        except Exception:
            errors += 1
            if errors <= 3:
                print("  ⚠️  Backend not reachable — retrying...")
            time.sleep(0.5)
            continue

        time.sleep(0.008)  # ≈125 Hz feed rate to match AD8232 sampling

except KeyboardInterrupt:
    print("\n✅ Feeder stopped cleanly.")
