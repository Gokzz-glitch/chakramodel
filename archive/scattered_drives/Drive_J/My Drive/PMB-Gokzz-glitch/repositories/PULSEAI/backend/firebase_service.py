import logging
import os
from datetime import datetime
from typing import Optional, Callable

try:
    import firebase_admin # pyre-ignore[21]
    from firebase_admin import credentials, db # pyre-ignore[21]
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

logger = logging.getLogger(__name__)

class FirebaseService:
    def __init__(self, key_path: str, db_url: str, on_alert: Optional[Callable[[str, int], None]] = None):
        self.key_path = key_path
        self.db_url = db_url
        self.on_alert = on_alert
        self.app = None
        self._listener = None

    def start(self):
        """Initializes and starts the Firebase Realtime Database listener."""
        if not FIREBASE_AVAILABLE:
            logger.warning("⚠️ Firebase Admin SDK not installed. Skipping Firebase integration.")
            return

        if not os.path.exists(self.key_path):
            logger.error(f"❌ AUTH ERROR: Firebase key not found at {self.key_path}")
            return

        try:
            cred = credentials.Certificate(self.key_path)
            self.app = firebase_admin.initialize_app(cred, {
                'databaseURL': self.db_url
            })
            logger.info("✅ Secure Firebase Cloud Connection Established!")
            
            # Start listening
            ref = db.reference('sensors/esp32/bpm')
            self._listener = ref.listen(self._bpm_stream_handler)
            logger.info("📡 Listening for live BPM data stream from Firebase...")
            
        except Exception as e:
            logger.error(f"❌ Firebase Auth/Init Error: {e}")

    def _bpm_stream_handler(self, event):
        """Triggered automatically when Firebase data updates."""
        new_bpm = event.data
        if new_bpm is not None:
            analysis_report = self.analyze_vitals(new_bpm)
            logger.info(analysis_report)
            alert_cb = self.on_alert
            if alert_cb is not None:
                alert_cb(analysis_report, new_bpm)

    def analyze_vitals(self, bpm: int) -> str:
        """The core AI logic for analyzing heart rate vitals."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        if bpm == 0:
            return f"[{timestamp}] ⚠️ WARNING: Sensor Error or Finger Removed!"
        elif bpm < 60:
            return f"[{timestamp}] 🔵 Heart Rate: {bpm} BPM (Low/Resting). Monitor for Bradycardia."
        elif 60 <= bpm <= 100:
            return f"[{timestamp}] 🟢 Heart Rate: {bpm} BPM (Normal). Vitals are stable."
        else:
            return f"[{timestamp}] 🔴 Heart Rate: {bpm} BPM (Elevated). Tachycardia/Stress detected! Triggering alert protocol."

    def stop(self):
        """Releases the listener and closes the Firebase connection."""
        if not FIREBASE_AVAILABLE:
            return
        listener = self._listener
        if listener is not None:
            listener.close()  # type: ignore
        if self.app:
            firebase_admin.delete_app(self.app)
        logger.info("🛑 Firebase Service offline.")

    def push_prediction_event(self, payload: dict):
        """Push latest backend prediction summary to Firebase for dashboarding."""
        if not FIREBASE_AVAILABLE or not self.app:
            return
        try:
            ref = db.reference("pulseai/backend/latest_prediction")
            ref.set(payload)

            hist_ref = db.reference("pulseai/backend/prediction_history")
            hist_ref.push(payload)
        except Exception as exc:
            logger.warning(f"Firebase prediction publish failed: {exc}")

    def push_benchmark_report(self, report: dict):
        """Publish benchmark report snapshot to Firebase."""
        if not FIREBASE_AVAILABLE or not self.app:
            return
        try:
            ref = db.reference("pulseai/backend/latest_benchmark")
            ref.set(report)
        except Exception as exc:
            logger.warning(f"Firebase benchmark publish failed: {exc}")
