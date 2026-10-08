import json
import copy

new_cell_content = """import nest_asyncio
from pyngrok import ngrok
import uvicorn
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import uuid
import git
import asyncio
import os

app = FastAPI(title="Agrimate V3 Colab Bridge")

# In-memory job status store
jobs = {}

class GitHubTask(BaseModel):
    repo_url: str                # e.g., 'https://github.com/Gokzz-glitch/agrimate_v3.git'
    branch: str = "main"
    script_path: str             # e.g., 'scripts/train_yolo.py'
    requirements_path: str = "requirements.txt"

def execute_notebook_task(job_id: str, task: GitHubTask):
    jobs[job_id] = {"status": "running", "log": ""}
    try:
        repo_name = task.repo_url.split('/')[-1].replace('.git', '')
        repo_dir = os.path.join(WORKSPACE_DIR, repo_name)

        # Clone or pull from GitHub
        if not os.path.exists(repo_dir):
            print(f"Cloning {task.repo_url} into {repo_dir}...")
            git.Repo.clone_from(task.repo_url, repo_dir, branch=task.branch)
        else:
            print(f"Pulling latest changes for {repo_name}...")
            repo = git.Repo(repo_dir)
            repo.remotes.origin.pull()

        # Install dependencies
        req_path = os.path.join(repo_dir, task.requirements_path)
        if os.path.exists(req_path):
            print("Installing requirements...")
            subprocess.run(["pip", "install", "-r", req_path], check=True, cwd=repo_dir, capture_output=True, text=True)

        # Execute the script
        script_full_path = os.path.join(repo_dir, task.script_path)
        print(f"Executing script: {script_full_path}")
        result = subprocess.run(["python", script_full_path], check=True, cwd=repo_dir, capture_output=True, text=True)

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["log"] = result.stdout
    except subprocess.CalledProcessError as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["log"] = e.stderr or e.stdout
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["log"] = str(e)

@app.post("/run_notebook")
async def run_notebook(task: GitHubTask, background_tasks: BackgroundTasks):
    \"\"\"Allows the local agent to push code from GitHub to the remote GPU.\"\"\"
    job_id = str(uuid.uuid4())
    background_tasks.add_task(execute_notebook_task, job_id, task)
    return {
        "job_id": job_id,
        "message": "Task started remotely.",
        "status_endpoint": f"/job_status/{job_id}"
    }

@app.get("/job_status/{job_id}")
async def job_status(job_id: str):
    \"\"\"Enables the Ralph Loop to poll for task completion signals.\"\"\"
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/download_output")
async def download_output(file_path: str):
    \"\"\"Automatically streams trained models and vector indices back to local storage.\"\"\"
    # file_path is expected to be relative to the Workspace Dir
    full_path = os.path.join(WORKSPACE_DIR, file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(full_path, filename=os.path.basename(full_path))

# --- NEW: Periodic Git Sync ---
async def periodic_git_sync():
    \"\"\"Periodically commits and pushes the workspace back to GitHub every 2 minutes.\"\"\"
    while True:
        try:
            print("Running periodic git sync (commit and push)...")
            repo_dir = os.path.join(WORKSPACE_DIR, 'agrimate_v3')
            if os.path.exists(repo_dir):
                repo = git.Repo(repo_dir)
                if repo.is_dirty(untracked_files=True):
                    repo.git.add('.')
                    repo.index.commit("Auto-commit from Colab: syncing outputs/params")
                    origin = repo.remote(name='origin')
                    origin.push()
                    print("Periodic git sync complete.")
                else:
                    print("No changes to sync.")
            else:
                print(f"Repository not found at {repo_dir}. Skipping sync.")
        except Exception as e:
            print(f"Git sync error: {e}")
        await asyncio.sleep(120)

nest_asyncio.apply()

# --- NGROK CONFIGURATION ---
# IMPORTANT: Set your specific ngrok authtoken here. Get it from https://dashboard.ngrok.com/get-started/your-authtoken
NGROK_AUTH_TOKEN = "3AkyCcPqqi5r2xkaQeImQ5SmihU_2BAvPSijE4aUG9Gg7EnMY"

if NGROK_AUTH_TOKEN:
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
else:
    print("WARNING: NGROK_AUTH_TOKEN is not set. The tunnel may expire quickly or be restricted.")
    print("Sign up at ngrok.com to get a free auth token and paste it above.")

# Terminate open tunnels if restarting the cell to avoid errors
ngrok.kill()

ngrok_tunnel = ngrok.connect(8000)
print('\\n' + '='*50)
print('🚀 PUBLIC URL (copy this for Ralph Loop): ', ngrok_tunnel.public_url)
print('='*50 + '\\n')

# Start the uvicorn server on port 8000
config = uvicorn.Config(app, host="0.0.0.0", port=8000)
server = uvicorn.Server(config)

# Run the server in a separate task so the cell doesn't block
asyncio.create_task(server.serve())

# Run the git sync in a separate background task
asyncio.create_task(periodic_git_sync())"""

def format_source(content):
    lines = content.split('\\n')
    return [line + '\\n' for line in lines[:-1]] + [lines[-1]]

with open("colab.ipynb", "r") as f:
    data = json.load(f)

# The last cell is the server block
data["cells"][-1]["source"] = format_source(new_cell_content)

with open("colab.ipynb", "w") as f:
    json.dump(data, f, indent=2)

print("Updated colab.ipynb successfully.")
