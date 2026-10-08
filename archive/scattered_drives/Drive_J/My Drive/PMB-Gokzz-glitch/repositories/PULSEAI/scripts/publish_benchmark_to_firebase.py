#!/usr/bin/env python3
"""Publish latest benchmark report to Firebase using backend service credentials."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_PATH = PROJECT_ROOT / "backend"
REPORT_PATH = PROJECT_ROOT / "test_results" / "global_benchmark_report.json"

if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from firebase_service import FirebaseService  # type: ignore


def main() -> int:
    if not REPORT_PATH.exists():
        print(f"Benchmark report not found: {REPORT_PATH}")
        return 1

    key_path = os.getenv("FIREBASE_KEY_PATH", str(PROJECT_ROOT / "frontend" / "pulseasi-firebase-adminsdk-fbsvc-6dfddc1a68.json"))
    db_url = os.getenv("FIREBASE_DB_URL", "https://pulseasi-default-rtdb.asia-southeast1.firebasedatabase.app/")

    svc = FirebaseService(key_path=key_path, db_url=db_url)
    svc.start()

    try:
      report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
      svc.push_benchmark_report(report)
      print("Published benchmark report to Firebase path: pulseai/backend/latest_benchmark")
      return 0
    finally:
      svc.stop()


if __name__ == "__main__":
    raise SystemExit(main())
