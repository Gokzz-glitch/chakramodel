import httpx
import sys

print("🫀 PulseAI Interactive Disease Terminal 🫀\n")

modes = {
    "0": "Disconnected (Flatline)",
    "1": "Healthy Individual (Normal)",
    "2": "Atrial Fibrillation (AFib)",
    "3": "Atrial Flutter",
    "4": "Ventricular Tachycardia (VT)",
    "5": "Ventricular Fibrillation (VF)",
    "6": "Heart Block (Bradycardia)"
}

def print_menu():
    print("="*45)
    print("  SELECT CLINICAL PRESENTATION")
    print("="*45)
    for k, v in modes.items():
        print(f"  [{k}] {v}")
    print("="*45)
    print("Press Ctrl+C to exit.\n")

def run_feeder():
    print_menu()
    
    with httpx.Client() as client:
        while True:
            try:
                choice = input("\nEnter mode (0-6) > ").strip()
                if choice in modes:
                    # Instruct the backend to securely transition the stream natively
                    resp = client.post(f"http://127.0.0.1:8000/api/simulation/mode?mode={choice}", timeout=2.0)
                    if resp.status_code == 200:
                        print(f"✅ Simulation state switched to: {modes[choice]}")
                        print(f"   The UI dashboard should update immediately.")
                    else:
                        print(f"⚠️ Backend returned error: {resp.status_code}")
                else:
                    print("⚠️ Invalid parameter. Please select 0 through 6.")
            except httpx.RequestError:
                print("❌ Cannot connect to backend. Is `python backend/main.py` currently running?")
            except KeyboardInterrupt:
                print("\n✅ Terminal Offline.")
                sys.exit(0)
            except EOFError:
                break

if __name__ == "__main__":
    run_feeder()
