import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


class AuditLogger:
    """Append-only audit log with hash chaining for tamper-evidence."""

    def __init__(self, path: str = "audit/pulseai_audit.log") -> None:
        root = Path(path)
        if not root.is_absolute():
            root = Path(__file__).resolve().parent.parent / root
        self.path = root
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._last_hash = self._load_last_hash()

    def _load_last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        try:
            last_line = ""
            with self.path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        last_line = line
            if not last_line:
                return "0" * 64
            payload = json.loads(last_line)
            return str(payload.get("hash", "0" * 64))
        except Exception:
            return "0" * 64

    def append(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        body = {
            "ts": now,
            "event_type": event_type,
            "payload": payload,
            "prev_hash": self._last_hash,
        }
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        body["hash"] = digest

        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(body, ensure_ascii=True) + "\n")
            self._last_hash = digest
        return body

    def recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        if limit <= 0:
            return []
        if not self.path.exists():
            return []

        rows: List[Dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows[-limit:]


def stable_client_id(peer: str | None, ua: str | None) -> str:
    raw = f"{peer or 'unknown'}|{ua or 'unknown'}|{int(time.time()) // 300}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
