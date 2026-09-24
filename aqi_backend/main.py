import math
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
MODEL_ID = os.getenv("AAAM_MODEL_ID", "amazon/chronos-2")
SPIKE_THRESHOLD = float(os.getenv("AAAM_SPIKE_THRESHOLD", "150"))

app = FastAPI(title="AAAM AQI Forecast API", version="0.1.0")


class ForecastRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    horizon: int = Field(default=7, ge=1, le=14)


class DeviceCommand(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    mode: str = Field(pattern="^(auto|manual)$")
    purifier_level: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1, max_length=300)


@lru_cache(maxsize=1)
def load_pipeline() -> Any:
    """Load Chronos-2 once per worker; model download is handled by Hugging Face."""
    try:
        from chronos import Chronos2Pipeline
    except ImportError as exc:
        raise RuntimeError(
            "Chronos-2 is not installed. Install requirements-aqi.txt before starting AAAM API."
        ) from exc

    device_map = os.getenv("AAAM_DEVICE_MAP", "auto")
    return Chronos2Pipeline.from_pretrained(MODEL_ID, device_map=device_map)


def load_history(latitude: float, longitude: float) -> list[float]:
    response = requests.get(
        OPEN_METEO_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "us_aqi",
            "past_days": 14,
            "forecast_days": 1,
            "timezone": "UTC",
        },
        timeout=20,
    )
    response.raise_for_status()
    values = [
        float(value)
        for value in response.json().get("hourly", {}).get("us_aqi", [])
        if value is not None and math.isfinite(float(value))
    ]
    if len(values) < 48:
        raise RuntimeError("AQI provider returned fewer than 48 usable hourly observations.")
    return values


def infer_forecast(history: list[float], horizon: int) -> list[float]:
    pipeline = load_pipeline()
    import torch

    context = torch.tensor(history, dtype=torch.float32)
    samples = pipeline.predict(context, prediction_length=horizon, num_samples=64)
    values = samples[0] if getattr(samples, "ndim", 1) == 3 else samples
    median = values.median(dim=0).values.tolist()
    return [round(max(0, float(value)), 1) for value in median]


def spike_probability(predictions: list[float], history: list[float]) -> float:
    recent = history[-24:]
    baseline = sum(recent) / len(recent)
    exceedance = sum(max(0, value - SPIKE_THRESHOLD) for value in predictions)
    scale = max(1, len(predictions) * max(10, SPIKE_THRESHOLD - baseline))
    return round(min(0.99, max(0.01, exceedance / scale)), 2)


@app.get("/health")
def health() -> dict[str, Any]:
    model_loaded = load_pipeline.cache_info().currsize > 0
    return {"service": "aaam-aqi", "model": MODEL_ID, "model_loaded": model_loaded}


@app.post("/api/forecast")
def forecast(request: ForecastRequest) -> dict[str, Any]:
    try:
        history = load_history(request.latitude, request.longitude)
        predictions = infer_forecast(history, request.horizon)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "forecast_unavailable",
                "message": str(exc),
                "model": MODEL_ID,
            },
        ) from exc

    probability = spike_probability(predictions, history)
    return {
        "model": MODEL_ID,
        "model_status": "ready",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "forecast": predictions,
        "spike_probability": probability,
        "spike_threshold": SPIKE_THRESHOLD,
        "history_points": len(history),
    }


@app.post("/api/devices/command")
def device_command(command: DeviceCommand) -> dict[str, Any]:
    """Command boundary for the MQTT adapter; publish is added when broker config exists."""
    if command.mode == "manual":
        return {"accepted": True, "published": False, "command": command.model_dump()}
    return {"accepted": True, "published": False, "command": command.model_dump()}
