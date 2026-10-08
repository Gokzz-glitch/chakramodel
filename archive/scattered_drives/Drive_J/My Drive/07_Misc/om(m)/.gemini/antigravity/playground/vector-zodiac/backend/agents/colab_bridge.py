import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format='[Colab Bridge] %(levelname)s - %(message)s')

class ColabBridgeAgent:
    """Passes tasks strictly to the external T4 GPU on Colab API (Ngrok)."""
    def __init__(self, ngrok_url=""):
        self.ngrok_url = ngrok_url

    def set_endpoint(self, url):
        self.ngrok_url = url.rstrip('/')

    def check_health(self):
        if not self.ngrok_url:
            logging.warning("No Colab Ngrok endpoint provided.")
            return False
            
        try:
            resp = requests.get(f"{self.ngrok_url}/health", timeout=5)
            if resp.status_code == 200:
                logging.info(f"Connected to Active GPU Colab Backend: {resp.json()}")
                return True
            else:
                logging.error(f"Colab down? HTTP {resp.status_code}")
                return False
        except Exception as e:
            logging.error(f"Bridge error: {e}")
            return False

    def offload_pipeline(self, pipeline_id, data=None):
        if not self.check_health():
            return {"status": "error", "message": "Colab disconnected! Spin up the notebook."}
            
        logging.info(f"Pushing entire load ({pipeline_id}) to Colab...")
        payload = {"pipeline": pipeline_id, "data": data or {}}
        try:
            resp = requests.post(f"{self.ngrok_url}/predict", json=payload, timeout=30)
            return resp.json()
        except requests.exceptions.Timeout:
            return {"status": "error", "message": "Colab Processing Timeout."}
        
if __name__ == "__main__":
    bridge = ColabBridgeAgent()
    bridge.check_health()
