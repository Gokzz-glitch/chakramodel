import httpx
import asyncio
import time

COLAB_URL = "https://unfagged-emerie-swampy.ngrok-free.dev"

scripts_to_run = [
    "ml/training/t202_crop_recommender.py",
    "ml/training/t203_yield_lstm.py",
    "ml/training/t204_price_forecast.py",
    "ml/training/t206_yolov8_disease.py"
]

async def trigger_and_wait(script_path):
    print(f"\n==============================================")
    print(f"Triggering {script_path} on Colab...")
    payload = {
        "repo_url": "https://github.com/Gokzz-glitch/agrimate_v3.git",
        "branch": "main",
        "script_path": script_path,
        "requirements_path": "ml/training/requirements.txt"
    }
    
    headers = {
        "ngrok-skip-browser-warning": "1",
        "User-Agent": "Agrimate-Pipeline"
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{COLAB_URL}/run_notebook", json=payload, headers=headers)
            print(f"Status Code: {resp.status_code}")
            if resp.status_code == 404:
                 print(f"Response: {resp.text}")
            resp.raise_for_status()
            data = resp.json()
            job_id = data["job_id"]
            print(f"Job started. ID: {job_id}")
            
            while True:
                await asyncio.sleep(5)
                status_resp = await client.get(f"{COLAB_URL}/job_status/{job_id}", headers=headers)
                status_data = status_resp.json()
                status = status_data["status"]
                
                if status in ["completed", "failed"]:
                    print(f"Job {status.upper()}:")
                    print(status_data["log"])
                    return status == "completed"
                else:
                    print(f"Status: {status}...")
        except Exception as e:
            print(f"Error triggering {script_path}: {e}")
            return False

async def main():
    for script in scripts_to_run:
        success = await trigger_and_wait(script)
        if not success:
            print(f"Stopping pipeline due to failure in {script}")
            break
        await asyncio.sleep(2)
        
if __name__ == "__main__":
    asyncio.run(main())
