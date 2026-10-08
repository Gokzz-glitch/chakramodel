import requests
import time
import math
import random
import argparse

def simulate_remote_laptop(target_url, freq=50):
    """
    Simulates a 'farhter laptop' or remote device sending ECG samples via HTTP.
    
    Args:
        target_url: URL of the PulseAI Backend (e.g. http://192.168.1.5:8000/api/ingest)
        freq: Sampling rate to simulate (Hz)
    """
    print(f"🚀 Starting Remote Sender to {target_url}...")
    t = 0
    while True:
        # Simulate a simple ECG waveform
        hr = 70
        qrs_pos = (t % (250 * 60 / hr))
        qrs = 1.3 * math.exp(-((qrs_pos - 50)**2) / 10)
        noise = random.uniform(-0.05, 0.05)
        val = (qrs + noise) * 100
        
        try:
            # Send single sample to backend
            resp = requests.post(target_url, params={"value": val}, timeout=0.5)
            if resp.status_code != 200:
                print(f"❌ Error: {resp.status_code}")
        except Exception as e:
            print(f"⚠️ Connection failed: {e}")
            time.sleep(2)
            
        t += 1
        time.sleep(1/freq) # Send at lower rate for demo to avoid flooding HTTP

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PulseAI Remote Data Sender")
    parser.add_argument("--url", default="http://localhost:8000/api/ingest", help="Backend ingestion endpoint")
    parser.add_argument("--fps", type=int, default=100, help="Samples per second")
    args = parser.parse_args()
    
    simulate_remote_laptop(args.url, args.fps)
