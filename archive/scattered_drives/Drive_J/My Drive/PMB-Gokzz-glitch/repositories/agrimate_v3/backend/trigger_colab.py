import urllib.request
import json
import ssl

url = "http://127.0.0.1:8080/api/v1/trigger_training?script_path=ml/data_ingestion/pipeline_runner.py"
# Bypass SSL just in case
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, method="POST")

try:
    with urllib.request.urlopen(req, context=ctx) as response:
        content = response.read().decode('utf-8')
        print(\"Successfully triggered Colab data ingestion!\")
        print(\"Colab response:\", json.dumps(json.loads(content), indent=2))
except Exception as e:
    print(f\"Failed to trigger Colab bridge: {e}\")
