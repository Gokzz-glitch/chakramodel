import requests
import time
import sys

print("==================================================")
print("ULAVAN COLAB MONITORING SERVICE STARTED")
print("Waiting for Colab Cloud Bridge to connect...")
print("==================================================")

API_URL = 'http://127.0.0.1:8000/api/survey-agents'

colab_was_offline = True
last_size = 0

while True:
    try:
        response = requests.get(API_URL)
        if response.status_code == 200:
            data = response.json()
            colab_status = data.get('agent_health', {}).get('colab_ml_backend', 'Unknown')
            dataset_size = data.get('current_dataset_size', 0)
            local_hw = data.get('hardware_usage_local', 'Unknown')
            
            # Print status update
            status_line = f"\r[Local Stats: {local_hw}] | Colab Bridge: {colab_status} | Docs Scraped: {dataset_size}   "
            sys.stdout.write(status_line)
            sys.stdout.flush()
            
            # Detect changes:
            if "Active" in colab_status and colab_was_offline:
                print("\n\n>>> 🟢 COLAB BRIDGE SECURED! Google T4 GPU is now ONLINE and ready for offloading.")
                colab_was_offline = False
                
            if dataset_size > last_size:
                print(f"\n>>> 📈 DATASET INCREASED! The Colab Scraper successfully found {dataset_size - last_size} new documents! Total: {dataset_size}")
                last_size = dataset_size
                
    except requests.exceptions.ConnectionError:
        sys.stdout.write("\r[Dashboard Offline] Waiting for Senior PM Manager Server...   ")
        sys.stdout.flush()
    except Exception as e:
        print(f"\nError: {e}")
        
    time.sleep(3)
