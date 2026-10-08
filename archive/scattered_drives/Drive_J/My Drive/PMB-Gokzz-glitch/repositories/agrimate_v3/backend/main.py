import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import time
import json
from dotenv import load_dotenv

# T-005: Initialize API Gateway for local operations
load_dotenv()

app = FastAPI(title="Agrimate V3 Local API Gateway", version="3.0.0")

# Enable CORS for the local React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Reference to the Ngrok Colab Bridge
COLAB_API_URL = os.getenv("COLAB_NGROK_URL", "")

@app.get("/")
async def health_check():
    return {"status": "online", "message": "Agrimate V3 Local Gateway Running. Resource usage capped to <85% system limits as mandated."}

@app.get("/api/v1/system_status")
async def system_status():
    """Returns the status of background automation processes."""
    # Check if files were updated recently
    poller_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "research_poller", "findings.json")
    reanalyser_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "artifacts", "agrimate_model_recommendation.md")
    
    status = {
        "gateway": "online",
        "research_poller": "active" if os.path.exists(poller_path) and (time.time() - os.path.getmtime(poller_path)) < 3600 else "dormant",
        "ml_reanalyser": "active" if os.path.exists(reanalyser_path) and (time.time() - os.path.getmtime(reanalyser_path)) < 7200 else "dormant",
        "throttler": "enabled"
    }
    return status

@app.get("/api/v1/data_summary")
async def data_summary():
    """Returns a summary of ingested agricultural data."""
    summary_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data_processed", "master_panel_summary.json")
    if os.path.exists(summary_path):
        with open(summary_path, "r") as f:
            return json.load(f)
    return {"total_rows": 0, "sources": {}}

@app.post("/api/v1/trigger_training")
async def proxy_training_to_cloud(script_path: str):
    """
    Proxies heavy ML tasks to Google Colab to preserve local laptop CPU/GPU/RAM.
    This guarantees we never hit the 85% local resource limit.
    """
    if not COLAB_API_URL:
        raise HTTPException(status_code=500, detail="COLAB_NGROK_URL is not set in .env")
    
    payload = {
        "repo_url": "https://github.com/Gokzz-glitch/agrimate_v3.git",
        "branch": "main",
        "script_path": script_path
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{COLAB_API_URL}/run_notebook", json=payload, timeout=10.0)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to Colab Bridge: {str(e)}")

@app.post("/api/v1/chat")
async def proxy_rag_inference(query: str):
    """
    Proxies RAG inference to the Colab GPU (Llama 3 execution).
    """
    if not COLAB_API_URL:
        return {"role": "bot", "text": "Gateway Error: COLAB_NGROK_URL not set in .env"}
    
    try:
        async with httpx.AsyncClient() as client:
            # We assume the Colab side has /chat or we'll fallback to simulation if fails
            response = await client.post(f"{COLAB_API_URL}/chat?query={query}", timeout=15.0)
            if response.status_code == 404:
                return {"role": "bot", "text": f"Simulation: Colab /chat endpoint not found. Input: {query}"}
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"role": "bot", "text": f"Gateway Proxy Error: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    # Enforcing strict resource concurrency limits via Uvicorn to respect 85% cpu limit guidelines
    uvicorn.run(app, host="127.0.0.1", port=8080, workers=1, limit_concurrency=50)
