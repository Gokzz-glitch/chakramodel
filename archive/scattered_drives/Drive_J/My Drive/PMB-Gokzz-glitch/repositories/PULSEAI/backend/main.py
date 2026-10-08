import logging
import json
import os
import asyncio
import time
from datetime import datetime
import collections
import httpx  # type: ignore
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header  # type: ignore
from pydantic import BaseModel  # type: ignore
from signal_processing import process_ecg, extract_beat_window, compute_signal_quality_index, classify_signal_quality, FS, SEGMENT_LEN  # type: ignore
from ml_model import predict_arrhythmia, get_model_status  # type: ignore
from fhir_generator import generate_fhir_diagnostic_report  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from typing import List, Optional, Deque, Dict
from ingestion import DataIngestor  # type: ignore
from firebase_service import FirebaseService  # type: ignore
from audit_log import AuditLogger, stable_client_id  # type: ignore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PulseAI Edge-Cloud Platform", version="2.1.0")

cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*").strip()
allow_origins = [o.strip() for o in cors_origins.split(",") if o.strip()] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Colab Cloud Inference Bridge ───────────────────────────────────────────────
COLAB_INFERENCE_URL: Optional[str] = os.getenv("COLAB_INFERENCE_URL", "").strip().rstrip("/") or None
if COLAB_INFERENCE_URL:
    logger.info(f"☁️  Colab inference bridge active: {COLAB_INFERENCE_URL}")
else:
    logger.info("💻 Local HCTG-Net mode active.")

DEPLOYMENT_ENV = os.getenv("PULSEAI_DEPLOYMENT_ENV", "development").strip().lower() or "development"
STRICT_SAFETY = os.getenv("PULSEAI_STRICT_SAFETY", "1").strip().lower() not in ("0", "false", "no")
ALLOW_PHI_LOGS = os.getenv("PULSEAI_ALLOW_PHI_LOGS", "0").strip().lower() in ("1", "true", "yes")
ALLOW_AUTONOMOUS_DIAGNOSIS = os.getenv("PULSEAI_ALLOW_AUTONOMOUS_DIAGNOSIS", "0").strip().lower() in ("1", "true", "yes")

REALTIME_ONLY = os.getenv("PULSEAI_REALTIME_ONLY", "1").strip().lower() not in ("0", "false", "no")
if REALTIME_ONLY:
    logger.info("🛡️ Realtime-only policy enabled: synthetic simulation is blocked by default.")

API_KEY = os.getenv("PULSEAI_API_KEY", "").strip()
if API_KEY:
    logger.info("🔐 API key protection enabled for sensitive endpoints.")
else:
    logger.warning("⚠️ PULSEAI_API_KEY not set. Sensitive endpoints are currently unprotected.")

STABILIZER_ENABLED = os.getenv("PULSEAI_STABILIZER_ENABLED", "1").strip().lower() not in ("0", "false", "no")
STABILIZER_WINDOW = max(1, int(os.getenv("PULSEAI_STABILIZER_WINDOW", "5")))
STABILIZER_MIN_VOTES = max(1, int(os.getenv("PULSEAI_STABILIZER_MIN_VOTES", "3")))
STABILIZER_MIN_CONF = float(os.getenv("PULSEAI_STABILIZER_MIN_CONF", "0.70"))
MIN_SQI_FOR_DIAGNOSIS = float(os.getenv("PULSEAI_MIN_SQI_FOR_DIAGNOSIS", "0.45"))
CRITICAL_LABELS = {
    "ventricular fibrillation (vf)",
    "ventricular tachycardia (vt)",
    "atrial fibrillation (afib)",
}

class PatientSession(BaseModel):
    patient_id: str
    name: str
    age: int

class WirelessConfig(BaseModel):
    host: str
    port: int

class FilterConfig(BaseModel):
    mains_hz: int = 50
    notch_enabled: bool = True
    hp_enabled: bool = True
    lp_enabled: bool = True
    ma_enabled: bool = False
    median_enabled: bool = False
    hampel_enabled: bool = False
    clip_enabled: bool = False

BUFFER_SIZE = FS * 5
EVAL_EVERY = FS

# Global buffers and state
class State:
    def __init__(self):
        self.ecg_buffer = collections.deque(maxlen=BUFFER_SIZE)
        self._eval_counter = 0
        self.latest_prediction: Optional[dict] = None
        self.latest_diagnostic: Optional[dict] = None
        self.leads_off: bool = False
        self.active_patient: Optional[PatientSession] = None
        self.transition_until: float = 0.0  # Timestamp after which inference is re-enabled
        self.filter_config: dict = {
            "mains_hz": 50,
            "notch_enabled": True,
            "hp_enabled": True,
            "lp_enabled": True,
            "ma_enabled": False,
            "median_enabled": False,
            "hampel_enabled": False,
            "clip_enabled": False,
        }
        self.prediction_history: Deque[Dict] = collections.deque(maxlen=STABILIZER_WINDOW)
        self.audit_logger = AuditLogger(os.getenv("PULSEAI_AUDIT_LOG_PATH", "audit/pulseai_audit.log"))
        self.active_viewers: Dict[str, Dict[str, str]] = {}
        
        # Firebase Service Initialization
        self.firebase_service = FirebaseService(
            key_path=os.getenv("FIREBASE_KEY_PATH", "").strip(),
            db_url=os.getenv("FIREBASE_DB_URL", "https://pulseasi-default-rtdb.asia-southeast1.firebasedatabase.app/"),
            on_alert=self.on_firebase_alert
        )

    def on_firebase_alert(self, report: str, bpm: int):
        """Callback to broadcast Firebase BPM alerts to all connected clients."""
        logger.info(f"🔥 Firebase Alert: {report}")
        payload = {
            "type": "firebase_alert",
            "message": report,
            "bpm": bpm,
            "timestamp": datetime.now().isoformat()
        }
        manager.broadcast_from_thread(json.dumps(payload))

state = State()

# --- Data Ingestion Engine ---
def on_raw_sample(val: float):
    """Callback for every raw sample received from ANY source."""
    state.ecg_buffer.append(val)
    
    state._eval_counter += 1
    if state._eval_counter >= EVAL_EVERY and len(state.ecg_buffer) >= SEGMENT_LEN:
        state._eval_counter = 0
        # Skip inference during the 2-second transition window after a mode switch
        if time.time() < state.transition_until:
            return
        asyncio.create_task(run_inference_cycle())

def on_status_change(is_on: bool):
    """Update leads off status and broadcast to clients."""
    if state.leads_off == (not is_on): return
    state.leads_off = not is_on
    manager.broadcast_from_thread(json.dumps({
        "type": "leads_off" if state.leads_off else "leads_on"
    }))

ingestor = DataIngestor(on_data_callback=on_raw_sample, on_status_callback=on_status_change)

# WebSocket manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Active: {len(self.active_connections)}")

        peer = None
        if websocket.client is not None:
            peer = f"{websocket.client.host}:{websocket.client.port}"
        ua = websocket.headers.get("user-agent")
        viewer_id = stable_client_id(peer, ua)
        state.active_viewers[viewer_id] = {
            "peer": peer or "unknown",
            "user_agent": ua or "unknown",
        }
        websocket.state.viewer_id = viewer_id
        state.audit_logger.append("viewer_connected", {
            "viewer_id": viewer_id,
            "peer": peer or "unknown",
            "user_agent": ua or "unknown",
        })

        initial_state = {
            "type": "snapshot",
            "leads_off": state.leads_off,
            "ecg_snapshot": [*state.ecg_buffer],
            "prediction": state.latest_prediction,
            "diagnostic": state.latest_diagnostic,
        }
        await websocket.send_text(json.dumps(initial_state))

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        viewer_id = getattr(websocket.state, "viewer_id", None)
        if viewer_id:
            state.active_viewers.pop(str(viewer_id), None)
            state.audit_logger.append("viewer_disconnected", {"viewer_id": str(viewer_id)})

    async def broadcast(self, message: str):
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def broadcast_from_thread(self, message: str):
        loop = self._loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)

manager = ConnectionManager()


def _enforce_api_key(x_api_key: Optional[str]) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _startup_safety_checks() -> None:
    """Fail fast on unsafe production settings."""
    if DEPLOYMENT_ENV == "production":
        if not API_KEY:
            raise RuntimeError("PULSEAI_API_KEY is required in production.")
        if "*" in allow_origins:
            raise RuntimeError("CORS wildcard is not allowed in production.")
        if COLAB_INFERENCE_URL and not COLAB_INFERENCE_URL.lower().startswith("https://"):
            raise RuntimeError("COLAB_INFERENCE_URL must use HTTPS in production.")

    if STRICT_SAFETY and MIN_SQI_FOR_DIAGNOSIS < 0.40:
        raise RuntimeError("PULSEAI_MIN_SQI_FOR_DIAGNOSIS is too low for strict safety mode.")


def _apply_clinical_advisory(result: dict) -> dict:
    out = dict(result)
    uncertainty_score = float(out.get("uncertainty_score", 0.0) or 0.0)
    conf = float(out.get("confidence", 0.0) or 0.0)
    interval_half = float(min(0.25, max(0.03, uncertainty_score * 0.20)))
    out["uncertainty_interval"] = {
        "confidence_low": float(max(0.0, round(conf - interval_half, 3))),
        "confidence_high": float(min(1.0, round(conf + interval_half, 3))),
    }

    out["clinical_decision_support_only"] = not ALLOW_AUTONOMOUS_DIAGNOSIS
    out["requires_clinician_review"] = bool(
        out.get("is_arrhythmia", False)
        or out.get("hold_still_required", False)
        or out.get("needs_manual_review", False)
        or out["clinical_decision_support_only"]
    )
    if out["clinical_decision_support_only"]:
        out["advisory"] = "Not for autonomous diagnosis. Clinician confirmation required."
    return out


def _apply_uncertainty_guard(result: dict) -> dict:
    """Make uncertainty explicit so ambiguous windows are never presented as definitive."""
    out = dict(result)
    cls_l = str(out.get("classification", "")).strip().lower()
    is_critical = cls_l in CRITICAL_LABELS
    needs_review = bool(out.get("needs_manual_review", False))
    uncertainty = float(out.get("uncertainty_score", 0.0) or 0.0)

    if is_critical:
        return out

    if needs_review or uncertainty >= 0.75:
        if bool(out.get("is_arrhythmia", False)):
            out["classification"] = f"{out.get('classification', 'Arrhythmia')} (Uncertain - Clinical Review Required)"
        else:
            out["classification"] = "Uncertain Rhythm - Clinical Review Required"
            out["is_arrhythmia"] = False

    return out


def stabilize_prediction(result: dict) -> dict:
    """Smooth noisy per-window decisions using a short rolling consensus."""
    if not STABILIZER_ENABLED:
        return result

    state.prediction_history.append({
        "is_arrhythmia": bool(result.get("is_arrhythmia", False)),
        "confidence": float(result.get("confidence", 0.0) or 0.0),
        "classification": str(result.get("classification", "Unknown")),
    })

    # Never delay critical classes.
    cls = str(result.get("classification", "")).lower()
    if cls in CRITICAL_LABELS:
        return result

    arr_votes = sum(1 for x in state.prediction_history if bool(x.get("is_arrhythmia", False)))
    avg_conf = sum(float(x.get("confidence", 0.0) or 0.0) for x in state.prediction_history) / max(1, len(state.prediction_history))
    stable_arrhythmia = arr_votes >= STABILIZER_MIN_VOTES and avg_conf >= STABILIZER_MIN_CONF

    if not stable_arrhythmia and bool(result.get("is_arrhythmia", False)):
        out = dict(result)
        out["is_arrhythmia"] = False
        out["classification"] = "Subtle Rhythm Irregularity (Review)"
        out["model_used"] = f"{out.get('model_used', 'unknown')}+stream-stabilizer"
        return out

    return result

@app.on_event("startup")
async def startup_event():
    manager.set_loop(asyncio.get_running_loop())
    try:
        _startup_safety_checks()
        await ingestor.start()
        logger.info(f"🚀 PulseAI Ingestion Engine started (Active Source: {ingestor.active_source})")
        # Start Firebase Service in a separate thread/background
        state.firebase_service.start()
    except Exception as exc:
        logger.error(f"Ingestion Engine failed to start: {exc}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 Shutting down PulseAI platform...")
    await ingestor.stop()
    state.firebase_service.stop()

async def run_inference_cycle():
    """Trigger AI processing and broadcast results."""
    if len(state.ecg_buffer) < SEGMENT_LEN: return
    
    patient = state.active_patient
    pid = patient.patient_id if patient else "pulseai-global"
    cleaned = process_ecg(list(state.ecg_buffer), filter_config=state.filter_config)
    sqi = compute_signal_quality_index(list(state.ecg_buffer), cleaned)
    window = extract_beat_window(cleaned)
    
    res = await predict_logic(window, pid, sqi=sqi)
    res = stabilize_prediction(res)
    state.latest_prediction = res
    if res.get("fhir_report"):
        state.latest_diagnostic = res["fhir_report"]
        state.audit_logger.append("critical_alert_generated", {
            "patient_id": pid,
            "classification": str(res.get("classification", "Unknown")),
            "confidence": float(res.get("confidence", 0.0) or 0.0),
            "model_used": str(res.get("model_used", "unknown")),
            "uncertainty_score": float(res.get("uncertainty_score", 0.0) or 0.0),
            "active_viewers": list(state.active_viewers.keys()),
        })

    state.firebase_service.push_prediction_event({
        "patient_id": pid,
        "classification": str(res.get("classification", "Unknown")),
        "confidence": float(res.get("confidence", 0.0) or 0.0),
        "is_arrhythmia": bool(res.get("is_arrhythmia", False)),
        "heart_rate_bpm": res.get("heart_rate_bpm"),
        "rr_cv": res.get("rr_cv"),
        "model_used": res.get("model_used"),
        "subtle_anomaly_flag": bool(res.get("subtle_anomaly_flag", False)),
        "subtle_anomaly_score": float(res.get("subtle_anomaly_score", 0.0) or 0.0),
        "timestamp": datetime.now().isoformat(),
    })
    
    manager.broadcast_from_thread(json.dumps({
        "type": "prediction",
        "patient_id": pid,
        **res,
        "ecg_snapshot": [*state.ecg_buffer]
    }))
    state.audit_logger.append("prediction_emitted", {
        "patient_id": pid,
        "classification": str(res.get("classification", "Unknown")),
        "confidence": float(res.get("confidence", 0.0) or 0.0),
        "is_arrhythmia": bool(res.get("is_arrhythmia", False)),
        "model_used": str(res.get("model_used", "unknown")),
        "active_viewers": list(state.active_viewers.keys()),
    })

def _apply_sqi_gate(result: dict, sqi: float) -> dict:
    out = dict(result)
    out["sqi"] = float(round(sqi, 3))
    out["signal_quality"] = classify_signal_quality(sqi)
    if sqi < MIN_SQI_FOR_DIAGNOSIS:
        out["is_arrhythmia"] = False
        out["classification"] = "Poor Signal Quality - Hold Still"
        out["confidence"] = float(max(float(out.get("confidence", 0.0) or 0.0), 0.85))
        out["hold_still_required"] = True
        out.pop("fhir_report", None)
    else:
        out["hold_still_required"] = False
    return out


async def predict_logic(window: list, pid: str, sqi: float | None = None) -> dict:
    result: dict = {}
    if COLAB_INFERENCE_URL:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{COLAB_INFERENCE_URL}/predict",
                    json={"ecg_window": window, "patient_id": pid},
                    headers={"bypass-tunnel-reminder": "true"}
                )
                resp.raise_for_status()
                json_data = resp.json()
                if isinstance(json_data, dict):
                    result = json_data
        except Exception:
            result = predict_arrhythmia(window)
    else:
        result = predict_arrhythmia(window)

    if sqi is not None:
        result = _apply_sqi_gate(result, sqi)

    result = _apply_uncertainty_guard(result)
    result = _apply_clinical_advisory(result)

    if result.get("is_arrhythmia"):
        result.update({
            "fhir_report": generate_fhir_diagnostic_report(
                patient_id=pid,
                classification=str(result.get("classification", "Unknown")),
                confidence=float(result.get("confidence", 0.90)),
                explainability_map=result.get("explainability_map")
            )
        })
    return result

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    if API_KEY:
        supplied = websocket.query_params.get("api_key")
        if supplied != API_KEY:
            await websocket.close(code=1008)
            return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/health")
async def health():
    model_status = get_model_status()
    patient = state.active_patient
    return {
        "status": "ok",
        "version": "2.1.0",
        "colab_bridge": COLAB_INFERENCE_URL or "disabled (local model)",
        "active_source": ingestor.active_source,
        "leads_off": state.leads_off,
        "buffer_samples": len(state.ecg_buffer),
        "active_patient": patient.patient_id if patient else None,
        "filter_config": state.filter_config,
        "realtime_only": REALTIME_ONLY,
        **model_status,
    }

@app.post("/api/source")
async def set_source(source: str, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Switch the data source (SIMULATION, MQTT, SERIAL, BLUETOOTH, HTTP, RECORDED_REAL)."""
    _enforce_api_key(x_api_key)
    if REALTIME_ONLY and source.upper() == "SIMULATION":
        raise HTTPException(status_code=403, detail="Realtime-only policy is enabled. SIMULATION source is blocked.")
    ingestor.set_source(source)
    return {"status": "success", "new_source": ingestor.active_source}

@app.post("/api/config/wireless")
async def set_wireless_config(config: WirelessConfig, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Set the IP and Port for the wireless bridge."""
    _enforce_api_key(x_api_key)
    ingestor.socket_remote_host = config.host
    ingestor.socket_remote_port = config.port
    logger.info(f"📶 Wireless config updated: {config.host}:{config.port}")
    return {"status": "success", "config": {"host": config.host, "port": config.port}}

@app.get("/api/config/filters")
async def get_filter_config(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_api_key(x_api_key)
    return {"status": "success", "filter_config": state.filter_config}

@app.post("/api/config/filters")
async def set_filter_config(config: FilterConfig, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_api_key(x_api_key)
    mains = 60 if int(config.mains_hz) == 60 else 50
    state.filter_config = {
        "mains_hz": mains,
        "notch_enabled": bool(config.notch_enabled),
        "hp_enabled": bool(config.hp_enabled),
        "lp_enabled": bool(config.lp_enabled),
        "ma_enabled": bool(config.ma_enabled),
        "median_enabled": bool(config.median_enabled),
        "hampel_enabled": bool(config.hampel_enabled),
        "clip_enabled": bool(config.clip_enabled),
    }
    logger.info(f"🧪 Filter config synchronized: {state.filter_config}")
    return {"status": "success", "filter_config": state.filter_config}

@app.post("/api/simulation/mode")
async def set_simulation_mode(mode: str, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Set the disease simulation mode (0-7)."""
    _enforce_api_key(x_api_key)
    if REALTIME_ONLY:
        raise HTTPException(status_code=403, detail="Realtime-only policy is enabled. Simulation mode is blocked.")
    ingestor.simulation_mode = mode
    # Trigger pristine simulation or live sensor mapping
    if mode == "7":
        ingestor.set_source("SERIAL")
    else:
        ingestor.set_source("SIMULATION")
    
    # Flush buffer + block inference for 2s so stale disease samples don't
    # produce false positives right after switching to Normal / another mode
    state.ecg_buffer.clear()
    state._eval_counter = 0
    state.transition_until = time.time() + 2.0  # 2 second transition grace period
    return {"status": "success", "mode": mode}

@app.post("/api/ingest")
async def ingest_data(value: float, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    """Manual data entry for 'farhter laptop' or direct connection."""
    _enforce_api_key(x_api_key)
    await ingestor.ingest_http(value)
    return {"status": "data_received"}

@app.post("/api/patient")
async def register_patient(patient: PatientSession, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_api_key(x_api_key)
    state.active_patient = patient
    if ALLOW_PHI_LOGS:
        logger.info(f"Patient registered: {patient.patient_id} — {patient.name}, age {patient.age}")
    else:
        logger.info(f"Patient registered: {patient.patient_id} (PHI-redacted logging)")
    return {"status": "registered", "patient_id": patient.patient_id}

@app.get("/api/ecg")
async def get_ecg(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_api_key(x_api_key)
    return {"data": [*state.ecg_buffer], "leads_off": state.leads_off, "buffer_size": len(state.ecg_buffer)}

@app.get("/api/diagnostic")
async def get_latest_diagnostic(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_api_key(x_api_key)
    if state.latest_diagnostic:
        return state.latest_diagnostic
    if state.latest_prediction:
        return {"status": "monitoring", "last_prediction": state.latest_prediction}
    return {"status": "No data yet — waiting for ECG stream."}

@app.post("/api/predict")
async def predict_ecg_window(payload: dict, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_api_key(x_api_key)
    ecg_window = payload.get("ecg_window")
    if not ecg_window or len(ecg_window) < 10:
        raise HTTPException(status_code=400, detail="'ecg_window' must have at least 10 samples.")

    pid     = str(payload.get("patient_id", "pulseai-api"))
    request_filter_cfg = payload.get("filter_config") if isinstance(payload, dict) else None
    active_cfg = request_filter_cfg if isinstance(request_filter_cfg, dict) else state.filter_config
    cleaned = process_ecg(ecg_window, filter_config=active_cfg)
    sqi = compute_signal_quality_index(ecg_window, cleaned)
    window  = extract_beat_window(cleaned)
    result = await predict_logic(window, pid, sqi=sqi)
    state.audit_logger.append("api_predict_call", {
        "patient_id": pid,
        "classification": str(result.get("classification", "Unknown")),
        "confidence": float(result.get("confidence", 0.0) or 0.0),
        "is_arrhythmia": bool(result.get("is_arrhythmia", False)),
        "uncertainty_score": float(result.get("uncertainty_score", 0.0) or 0.0),
    })
    return result


@app.post("/api/firebase/publish-benchmark")
async def publish_benchmark(payload: dict, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_api_key(x_api_key)
    report = payload.get("report") if isinstance(payload, dict) else None
    if not isinstance(report, dict):
        raise HTTPException(status_code=400, detail="'report' object is required.")
    state.firebase_service.push_benchmark_report(report)
    return {"status": "success", "published": True}


@app.get("/api/audit/recent")
async def get_recent_audit(limit: int = 100, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    _enforce_api_key(x_api_key)
    safe_limit = max(1, min(int(limit), 1000))
    rows = state.audit_logger.recent(safe_limit)
    return {
        "status": "success",
        "count": len(rows),
        "records": rows,
    }
if __name__ == "__main__":
    import uvicorn  # type: ignore
    uvicorn.run(app, host="127.0.0.1", port=8000)
