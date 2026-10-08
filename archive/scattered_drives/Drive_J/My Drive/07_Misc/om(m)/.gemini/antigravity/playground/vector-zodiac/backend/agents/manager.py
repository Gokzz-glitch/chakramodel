import os
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import psutil

from colab_bridge import ColabBridgeAgent

logging.basicConfig(level=logging.INFO, format='[Senior PM Manager] %(levelname)s - %(message)s')

app = FastAPI(title="Ulavan Senior PM Dashboard", version="1.0.0")

# Enable CORS for the frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Ulavan Agents
from colab_bridge import ColabBridgeAgent
bridge_agent = ColabBridgeAgent()

class NgrokEndpoint(BaseModel):
    url: str

def check_hardware_limits():
    """Ensure local host never exceeds 75% CPU/RAM."""
    cpu_usage = psutil.cpu_percent(interval=0.1)
    ram_usage = psutil.virtual_memory().percent
    
    if cpu_usage > 75.0 or ram_usage > 75.0:
        logging.warning(f"HARDWARE STRESS DETECTED! CPU: {cpu_usage}%, RAM: {ram_usage}%. Action Denied.")
        return False, f"System resources over 75% limit (CPU: {cpu_usage}%, RAM: {ram_usage}%)."
    return True, f"CPU: {cpu_usage}%, RAM: {ram_usage}%"


@app.get("/api/survey-agents")
def survey_agents():
    """Check health and roles of all agents."""
    can_run, hw_status = check_hardware_limits()
    health_status = {
        "manager_agent": "Online (Orchestrating)",
        "research_agent": "Online (Standing by)",
        "colab_bridge_agent": "Online (Ready)",
        "colab_ml_backend": "Offline" if not bridge_agent.check_health() else "Active (Hardware offloaded)"
    }
    
    # Get dataset size fully via external offloaded query to avoid local IO load
    dataset_size = 0
    if bridge_agent.check_health():
        try:
            resp = bridge_agent.offload_pipeline("get-dataset-size")
            if 'size' in resp:
                dataset_size = resp['size']
        except:
            pass
            
    return {
        "roles_assigned": [
            "DataResearcher -> Abstract/Dataset collection",
            "ColabBridge -> Pipeline offloading & GPU sync",
            "SeniorManager -> Survey & Orchestration"
        ],
        "hardware_usage_local": hw_status if can_run else f"REJECTED. limits exceeded: {hw_status}",
        "hardware_usage_colab": "Monitored externally",
        "agent_health": health_status,
        "current_dataset_size": dataset_size,
    }

@app.post("/api/update-colab-endpoint")
def update_colab_url(endpoint: NgrokEndpoint):
    bridge_agent.set_endpoint(endpoint.url)
    status = bridge_agent.check_health()
    return {"status": "success", "colab_connected": status, "msg": f"Endpoint set to {endpoint.url}"}

@app.post("/api/trigger-research")
def trigger_research():
    can_run, msg = check_hardware_limits()
    if not can_run:
        return {"error": msg}
        
    response = bridge_agent.offload_pipeline("poll-research")
    return {"status": "Research task pushed entirely to Colab Node.", "colab_response": response}

@app.post("/api/train-models")
def trigger_colab_training():
    """Commands Colab to train the models."""
    can_run, msg = check_hardware_limits()
    if not can_run:
        return {"error": f"Cannot launch trigger: {msg}"}
        
    response = bridge_agent.offload_pipeline("train-models-req")
    return {"colab_response": response}

if __name__ == "__main__":
    logging.info("Starting Senior Project Manager orchestrator...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
