"""
resource_monitor.py
===================
Aggressive hardware maximizer thread.

Philosophy: NEVER throttle. Always push batch size and worker count to the
absolute ceiling the hardware can sustain. Log readings for provenance, but
never reduce throughput to "protect" the GPU or CPU.

INTEGRITY: Zero hardcoded dataset paths, names, or URLs.
Compliant with ml-integrity-standards.md Rule 6 (Zero Hardcoding).
"""

from __future__ import annotations

import csv
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psutil

try:
    import pynvml
    pynvml.nvmlInit()
    NVML_AVAILABLE = True
    N_GPUS = pynvml.nvmlDeviceGetCount()
except Exception:
    NVML_AVAILABLE = False
    N_GPUS = 0

POLL_INTERVAL_S   = 0.5   # poll every 500ms for telemetry
MAX_BATCH         = 128   # hard ceiling — will push up to this aggressively
MAX_WORKERS       = 16    # max DataLoader workers — saturate all CPU cores
VRAM_OOM_THRESH   = 0.98  # ONLY back off if literally about to OOM (>98%)


class ResourceMonitor:
    """
    Background thread that monitors GPU + CPU every POLL_INTERVAL_S seconds.
    Strategy: always ramp batch size UP to MAX_BATCH as fast as possible.
    Only backs off batch by 1 if VRAM > 98% (imminent OOM, not throttling).
    Workers are always pegged at MAX_WORKERS unless the OS refuses forks.

    Usage:
        monitor = ResourceMonitor(log_dir="eval_harness/logs")
        monitor.start()
        ...
        batch_size  = monitor.recommended_batch_size   # always growing
        num_workers = monitor.recommended_num_workers  # always maxed
        ...
        monitor.stop()
    """

    def __init__(self, log_dir: str | Path = "logs", initial_batch: int = 4):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.log_path = self.log_dir / f"resource_log_{ts}.csv"

        self._lock = threading.Lock()
        self._batch_size: int = initial_batch  # start at 4, ramp to 128
        self._num_workers: int = MAX_WORKERS   # always maxed from the start
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._latest: dict = {}

    # ------------------------------------------------------------------
    # Public interface (thread-safe reads)
    # ------------------------------------------------------------------

    @property
    def recommended_batch_size(self) -> int:
        with self._lock:
            return self._batch_size

    @property
    def recommended_num_workers(self) -> int:
        return MAX_WORKERS  # always max, no CPU throttling

    @property
    def latest_readings(self) -> dict:
        with self._lock:
            return dict(self._latest)

    # ------------------------------------------------------------------
    # Thread lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ResourceMonitor"
        )
        self._thread.start()
        print(f"[ResourceMonitor] AGGRESSIVE MODE — always pushing to ceiling.")
        print(f"[ResourceMonitor] Logging to {self.log_path}")

    def stop(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        print("[ResourceMonitor] Stopped.")

    # ------------------------------------------------------------------
    # Internal aggressive polling loop
    # ------------------------------------------------------------------

    def _run(self):
        with open(self.log_path, "w", newline="") as f:
            csv.writer(f).writerow([
                "utc_timestamp",
                "gpu_idx", "gpu_vram_used_mb", "gpu_vram_total_mb",
                "gpu_vram_pct", "gpu_util_pct", "gpu_temp_c",
                "cpu_util_pct", "ram_used_gb", "ram_total_gb",
                "active_batch", "active_workers",
            ])

        while not self._stop_event.is_set():
            now_utc = datetime.now(timezone.utc).isoformat()
            rows = []
            gpu_vram_pcts: list[float] = []

            # --- GPU readings ---
            for gpu_idx in range(N_GPUS if NVML_AVAILABLE else 0):
                try:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_idx)
                    mem    = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    util   = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    temp   = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                    vram_pct = mem.used / mem.total
                    gpu_vram_pcts.append(vram_pct)
                    rows.append({
                        "gpu_idx":          gpu_idx,
                        "gpu_vram_used_mb": round(mem.used / 1024 ** 2, 1),
                        "gpu_vram_total_mb":round(mem.total / 1024 ** 2, 1),
                        "gpu_vram_pct":     round(vram_pct * 100, 2),
                        "gpu_util_pct":     util.gpu,
                        "gpu_temp_c":       temp,
                    })
                except Exception:
                    gpu_vram_pcts.append(0.0)
                    rows.append({
                        "gpu_idx": gpu_idx,
                        "gpu_vram_used_mb": 0, "gpu_vram_total_mb": 0,
                        "gpu_vram_pct": 0, "gpu_util_pct": 0, "gpu_temp_c": 0,
                    })

            if not rows:
                gpu_vram_pcts = [0.0]
                rows.append({
                    "gpu_idx": -1, "gpu_vram_used_mb": 0, "gpu_vram_total_mb": 0,
                    "gpu_vram_pct": 0, "gpu_util_pct": 0, "gpu_temp_c": 0,
                })

            # --- CPU readings ---
            cpu_pct    = psutil.cpu_percent(interval=None)
            ram        = psutil.virtual_memory()
            ram_used   = round(ram.used / 1024 ** 3, 2)
            ram_total  = round(ram.total / 1024 ** 3, 2)

            # --- AGGRESSIVE BATCH SCALING ---
            # Ramp UP every tick until we hit MAX_BATCH.
            # ONLY back off 1 step if we're at imminent OOM (>98% VRAM).
            max_vram_pct = max(gpu_vram_pcts)
            with self._lock:
                if max_vram_pct > VRAM_OOM_THRESH:
                    # Absolute last resort — 1 step back from OOM
                    self._batch_size = max(self._batch_size - 1, 1)
                elif self._batch_size < MAX_BATCH:
                    # Always ramp up — no ceiling unless OOM
                    self._batch_size += 1

                batch_snap   = self._batch_size
                workers_snap = MAX_WORKERS

                self._latest = {
                    "utc_timestamp":   now_utc,
                    "max_gpu_vram_pct": round(max_vram_pct * 100, 2),
                    "cpu_pct":          cpu_pct,
                    "ram_used_gb":      ram_used,
                    "batch_size":       batch_snap,
                    "num_workers":      workers_snap,
                }

            # --- Write CSV ---
            with open(self.log_path, "a", newline="") as f:
                writer = csv.writer(f)
                for row in rows:
                    writer.writerow([
                        now_utc,
                        row["gpu_idx"],
                        row["gpu_vram_used_mb"],
                        row["gpu_vram_total_mb"],
                        row["gpu_vram_pct"],
                        row["gpu_util_pct"],
                        row["gpu_temp_c"],
                        cpu_pct, ram_used, ram_total,
                        batch_snap, workers_snap,
                    ])

            time.sleep(POLL_INTERVAL_S)
