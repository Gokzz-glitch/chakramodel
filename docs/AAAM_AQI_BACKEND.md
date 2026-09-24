# AAAM AQI model backend

AAAM now has a FastAPI integration point for a real pretrained AQI forecaster:

```text
device telemetry / location -> POST /api/forecast -> Open-Meteo history
                                           -> Chronos-2
                                           -> spike probability
                                           -> MQTT/TLS device command (next adapter)
```

## Run locally

From the repository root:

```powershell
pip install -r requirements-aqi.txt
python -m uvicorn aqi_backend.main:app --host 0.0.0.0 --port 8000
```

The React development server proxies `/api` to port 8000:

```powershell
Set-Location frontend
npm run dev -- --host 0.0.0.0
```

The first forecast request downloads `amazon/chronos-2` from Hugging Face and can require several GB of disk/RAM. Set `AAAM_DEVICE_MAP=cpu` for CPU-only environments. In production, run the API on Linux with a model-capable worker and keep the model cache on persistent storage.

## API contract

`POST /api/forecast`

```json
{
  "latitude": 13.0827,
  "longitude": 80.2707,
  "horizon": 7
}
```

Successful responses include `model`, `forecast`, `spike_probability`, `spike_threshold`, and `generated_at`. A `503` response with `code=forecast_unavailable` is intentional when the model cannot load; the dashboard must not turn that error into an alert.

## AWS production shape

- **AWS IoT Core:** MQTT over TLS for device telemetry, command, acknowledgement, and manual-override topics.
- **ECS/Fargate or a GPU-backed service:** host the FastAPI worker and cached Chronos-2 weights. Use Secrets Manager for broker credentials and signing material.
- **CloudWatch:** alert on forecast latency, stale telemetry, model-load failures, command acknowledgement timeouts, and device disconnects.
- **Safety:** if telemetry or model output is stale, publish a conservative purifier command; manual override always wins. Commands need an idempotent command ID and an acknowledgement timeout.

Do not put broker credentials, Hugging Face tokens, or device certificates in the React bundle.
