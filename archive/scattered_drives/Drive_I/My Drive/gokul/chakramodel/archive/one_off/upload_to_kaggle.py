import requests
import json
import base64
import sys
import os

base_url = sys.argv[1]
local_path = sys.argv[2]
remote_path = sys.argv[3] # e.g. 'working/best.pt'

with open(local_path, "rb") as f:
    content = f.read()

content_b64 = base64.b64encode(content).decode("utf-8")

payload = {
    "content": content_b64,
    "format": "base64",
    "type": "file"
}

url = f"{base_url}/api/contents/{remote_path}"
print(f"Uploading {local_path} to {url}...")
resp = requests.put(url, json=payload)
if resp.status_code in [200, 201]:
    print("Upload successful!")
else:
    print(f"Failed: {resp.status_code}")
    print(resp.text)
