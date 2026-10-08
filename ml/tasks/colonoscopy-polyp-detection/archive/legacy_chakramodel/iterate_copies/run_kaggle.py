import requests
import json
import asyncio
import websockets
import uuid
import sys

base_url = sys.argv[1]
code_to_run = sys.argv[2]

# 1. Get Sessions to find the kernel ID
session_url = f"{base_url}/api/sessions"
resp = requests.get(session_url)
resp.raise_for_status()
sessions = resp.json()

if not sessions:
    print("No active sessions found!")
    sys.exit(1)

kernel_id = sessions[0]["kernel"]["id"]
print(f"Found kernel: {kernel_id}")

# 2. Connect to the WebSocket
ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
ws_url = f"{ws_url}/api/kernels/{kernel_id}/channels"

async def run_code():
    async with websockets.connect(ws_url) as websocket:
        # Create execution request
        msg_id = uuid.uuid4().hex
        req = {
            "header": {
                "msg_id": msg_id,
                "username": "username",
                "session": uuid.uuid4().hex,
                "msg_type": "execute_request",
                "version": "5.3"
            },
            "parent_header": {},
            "metadata": {},
            "content": {
                "code": code_to_run,
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": False
            }
        }
        await websocket.send(json.dumps(req))
        
        # Listen for output
        while True:
            response = await websocket.recv()
            msg = json.loads(response)
            msg_type = msg["header"]["msg_type"]
            parent_id = msg["parent_header"].get("msg_id")
            
            if parent_id != msg_id:
                continue
                
            if msg_type == "stream":
                print(msg["content"]["text"], end="")
            elif msg_type == "execute_result" or msg_type == "display_data":
                data = msg["content"]["data"]
                if "text/plain" in data:
                    print(data["text/plain"])
            elif msg_type == "error":
                print("\nERROR:")
                for trace in msg["content"]["traceback"]:
                    print(trace)
                break
            elif msg_type == "execute_reply":
                status = msg["content"]["status"]
                if status == "ok":
                    break
                elif status == "error":
                    break

asyncio.run(run_code())
