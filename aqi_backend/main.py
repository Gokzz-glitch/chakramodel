import math
import os
import threading
import uuid
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


class Telemetry(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    aqi: float = Field(ge=0, le=1000)
    pm25: float | None = Field(default=None, ge=0)
    pm10: float | None = Field(default=None, ge=0)
    recorded_at: datetime | None = None


class SourceSelection(BaseModel):
    source: str = Field(pattern="^(api|hardware)$")
    device_id: str | None = None


state_lock = threading.Lock()
input_source = "api"
hardware_history: dict[str, list[float]] = {}
last_telemetry: dict[str, dict[str, Any]] = {}


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


def history_for_request(request: ForecastRequest) -> tuple[list[float], str, str | None]:
    with state_lock:
        selected_source = input_source
        telemetry_devices = list(hardware_history)
        if selected_source == "hardware" and telemetry_devices:
            device_id = telemetry_devices[0]
            history = hardware_history[device_id][-336:]
            if len(history) >= 48:
                return history, "hardware", device_id
    return load_history(request.latitude, request.longitude), "api", None


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
    with state_lock:
        selected_source = input_source
        device_count = len(hardware_history)
    return {"service": "aaam-aqi", "model": MODEL_ID, "model_loaded": model_loaded, "input_source": selected_source, "hardware_devices": device_count}


@app.get("/api/source")
def get_source() -> dict[str, Any]:
    with state_lock:
        device_ids = list(hardware_history)
        return {"source": input_source, "device_id": device_ids[0] if device_ids else None, "hardware_devices": device_ids}


@app.post("/api/source")
def set_source(selection: SourceSelection) -> dict[str, Any]:
    global input_source
    with state_lock:
        if selection.source == "hardware" and selection.device_id and selection.device_id not in hardware_history:
            raise HTTPException(status_code=409, detail="No telemetry has been received from this device yet.")
        if selection.source == "hardware" and not hardware_history:
            raise HTTPException(status_code=409, detail="Hardware mode requires at least one telemetry sample.")
        input_source = selection.source
        return {"source": input_source, "device_id": selection.device_id}


@app.post("/api/telemetry")
def ingest_telemetry(telemetry: Telemetry) -> dict[str, Any]:
    timestamp = telemetry.recorded_at or datetime.now(timezone.utc)
    with state_lock:
        history = hardware_history.setdefault(telemetry.device_id, [])
        history.append(telemetry.aqi)
        del history[:-336]
        last_telemetry[telemetry.device_id] = {
            "device_id": telemetry.device_id,
            "aqi": telemetry.aqi,
            "pm25": telemetry.pm25,
            "pm10": telemetry.pm10,
            "recorded_at": timestamp.isoformat(),
        }
    return {"accepted": True, "device_id": telemetry.device_id, "samples": len(history)}


@app.post("/api/forecast")
def forecast(request: ForecastRequest) -> dict[str, Any]:
    try:
        history, source, device_id = history_for_request(request)
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
        "input_source": source,
        "device_id": device_id,
    }


@app.post("/api/devices/command")
def device_command(command: DeviceCommand) -> dict[str, Any]:
    """Command boundary for the MQTT adapter; publish is added when broker config exists."""
    if command.mode == "manual":
        return {"accepted": True, "published": False, "command": command.model_dump()}
    return {"accepted": True, "published": False, "command": command.model_dump()}
