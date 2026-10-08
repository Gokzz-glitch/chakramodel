"""
ChakraModel Hardware Resource Monitor
======================================
A background daemon that dynamically balances GPU and CPU usage:

  - Warmup Phase (0-240s):  Gentle ramp-up. GPU limited to 50% VRAM, 
                             CPU free to do loading/IO work.
  - Boost Phase (240s+):    GPU pushed to 95% VRAM (3.8GB / 4GB).
                             CPU throttled to <60% via process affinity.
  - Power-Aware:            Detects AC vs Battery. On battery, limits GPU to 
                             70% VRAM and CPU to 40% to preserve thermals.
  - Self-Healing:           If GPU OOM is detected, VRAM fraction is reduced
                             by 5% automatically until stable.

Usage:
    from src.hardware_monitor import HardwareMonitor
    monitor = HardwareMonitor()
    monitor.start()   # Non-blocking background daemon
    ...
    monitor.stop()

Or run standalone to see a live dashboard:
    python src/hardware_monitor.py
"""
from __future__ import annotations

import os
import sys
import time
import threading
import logging
from pathlib import Path
from typing import Optional

# ──────────────────────────────────────────────────────
# Safe optional imports
# ──────────────────────────────────────────────────────
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

# ──────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────
WARMUP_SECONDS        = 240        # Full warmup window; CPU free throughout
GPU_RAMPUP_START      = 120        # GPU starts cranking up after 120s
GPU_MAX_FRACTION      = 1.0        # 100% VRAM (4.0 GB) (plugged in)
GPU_BATTERY_FRACTION  = 0.70       # 2.8 GB (on battery, safer thermals)
GPU_WARMUP_FRACTION   = 0.40       # 1.6 GB during first 120s (safe loading)
CPU_MAX_PERCENT       = 80.0       # Hard OS-level cap for CPU via core affinity
CPU_BATTERY_MAX       = 40.0       # Stricter ceiling on battery
MONITOR_INTERVAL      = 5.0        # Seconds between monitor ticks
OOM_BACKOFF           = 0.05       # Reduce fraction by 5% after OOM
LOG_FILE              = Path(__file__).parent.parent / "logs" / "hardware_monitor.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [HW-MONITOR] %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("hardware_monitor")


# ──────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────
def _is_plugged_in() -> bool:
    """Returns True when AC power adapter is connected."""
    if not PSUTIL_AVAILABLE:
        return True  # Assume plugged in when we can't check
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return True  # Desktop or no battery sensor → assume AC
        return battery.power_plugged
    except Exception:
        return True


def _get_cpu_percent(interval: float = 0.5) -> float:
    """Returns total CPU utilisation in percent."""
    if not PSUTIL_AVAILABLE:
        return 0.0
    try:
        return psutil.cpu_percent(interval=interval)
    except Exception:
        return 0.0


def _get_gpu_vram_used_gb() -> float:
    """Returns currently allocated VRAM in GB."""
    if not TORCH_AVAILABLE or not torch.cuda.is_available():
        return 0.0
    try:
        return torch.cuda.memory_allocated(0) / 1024 ** 3
    except Exception:
        return 0.0


def _set_gpu_memory_fraction(fraction: float) -> bool:
    """Ask PyTorch to limit VRAM to `fraction` of total. Returns False on failure."""
    if not TORCH_AVAILABLE or not torch.cuda.is_available():
        return False
    try:
        torch.cuda.set_per_process_memory_fraction(max(0.10, min(1.0, fraction)), device=0)
        return True
    except Exception as e:
        logger.warning(f"Could not set GPU fraction to {fraction:.0%}: {e}")
        return False


def _apply_cpu_hard_cap(target_max: float) -> None:
    """
    Hard-caps CPU usage by restricting this process (and its threads) to a strict
    subset of logical CPU cores. This physically prevents the OS from allocating
    more than `target_max` percent of the system's total CPU.
    """
    if not PSUTIL_AVAILABLE:
        return
    try:
        proc = psutil.Process(os.getpid())
        total_cores = psutil.cpu_count(logical=True)
        if total_cores is None:
            return
            
        allowed_cores = max(1, int(total_cores * (target_max / 100.0)))
        
        # Affinity list, e.g. [0, 1, 2, 3]
        target_affinity = list(range(allowed_cores))
        current_affinity = proc.cpu_affinity()
        
        if current_affinity != target_affinity:
            proc.cpu_affinity(target_affinity)
            logger.info(f"OS CPU Hard Cap Applied: {target_max}% (restricted to {allowed_cores}/{total_cores} cores)")
            
            # Also limit PyTorch's internal threadpool
            if TORCH_AVAILABLE:
                torch.set_num_threads(allowed_cores)
    except (psutil.AccessDenied, AttributeError, Exception) as e:
        logger.debug(f"Could not apply OS-level CPU cap: {e}")


# ──────────────────────────────────────────────────────
# Main Monitor Class
# ──────────────────────────────────────────────────────
class HardwareMonitor:
    """
    Background daemon thread that continuously balances hardware usage.

    Phases
    ------
    WARMUP  (t < 240s): gentle — GPU at 50%, CPU uncapped for IO/loading
    BOOST   (t >= 240s): aggressive — GPU at 95% (~3.8 GB), CPU capped <60%
    BATTERY (anytime):  conservative — GPU at 70%, CPU <40%, regardless of phase
    """

    def __init__(
        self,
        warmup_seconds: int = WARMUP_SECONDS,
        gpu_rampup_start: int = GPU_RAMPUP_START,
        gpu_max: float = GPU_MAX_FRACTION,
        gpu_battery: float = GPU_BATTERY_FRACTION,
        gpu_warmup: float = GPU_WARMUP_FRACTION,
        cpu_max: float = CPU_MAX_PERCENT,
        cpu_battery_max: float = CPU_BATTERY_MAX,
        monitor_interval: float = MONITOR_INTERVAL,
    ):
        self.warmup_seconds    = warmup_seconds
        self.gpu_rampup_start  = gpu_rampup_start
        self.gpu_max           = gpu_max
        self.gpu_battery       = gpu_battery
        self.gpu_warmup        = gpu_warmup
        self.cpu_max           = cpu_max
        self.cpu_battery_max   = cpu_battery_max
        self.monitor_interval  = monitor_interval

        self._start_time: Optional[float]     = None
        self._current_gpu_fraction: float     = gpu_warmup
        self._thread: Optional[threading.Thread] = None
        self._stop_event: threading.Event      = threading.Event()
        self._phase: str                       = "WARMUP"
        self._plugged_in: bool                 = True

        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [HW-MONITOR] %(levelname)s %(message)s"))
        logger.addHandler(fh)

    # ── Public API ──────────────────────────────────────
    def start(self) -> "HardwareMonitor":
        """Start the background monitor daemon (non-blocking)."""
        self._start_time = time.monotonic()
        self._stop_event.clear()

        # Apply initial warmup fraction immediately
        _set_gpu_memory_fraction(self.gpu_warmup)
        logger.info(f"WARMUP phase — GPU capped at {self.gpu_warmup:.0%} (~{self.gpu_warmup*4:.1f} GB) | "
                    f"GPU ramp-up starts at {self.gpu_rampup_start}s | "
                    f"Full boost at {self.warmup_seconds}s")

        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="HardwareMonitor",
            daemon=True,       # Dies when main process exits — no cleanup needed
        )
        self._thread.start()
        return self

    def stop(self) -> None:
        """Signal the monitor to stop on next tick."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.monitor_interval + 2)
        logger.info("Hardware monitor stopped.")

    @property
    def phase(self) -> str:
        return self._phase

    @property
    def current_gpu_fraction(self) -> float:
        return self._current_gpu_fraction

    def status_dict(self) -> dict:
        elapsed = time.monotonic() - (self._start_time or time.monotonic())
        return {
            "phase": self._phase,
            "elapsed_s": round(elapsed, 1),
            "warmup_remaining_s": max(0.0, self.warmup_seconds - elapsed),
            "gpu_vram_fraction": self._current_gpu_fraction,
            "gpu_vram_used_gb": round(_get_gpu_vram_used_gb(), 2),
            "cpu_percent": round(_get_cpu_percent(interval=0.1), 1),
            "plugged_in": self._plugged_in,
        }

    # ── Internal Loop ───────────────────────────────────
    def _monitor_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Monitor tick error: {e}")
            self._stop_event.wait(timeout=self.monitor_interval)

    def _tick(self) -> None:
        elapsed = time.monotonic() - self._start_time

        # 1. Detect power source
        self._plugged_in = _is_plugged_in()

        # 2. Decide target GPU fraction and CPU ceiling
        if not self._plugged_in:
            target_gpu  = self.gpu_battery
            target_cpu  = self.cpu_battery_max
            new_phase   = "BATTERY"
        elif elapsed >= self.warmup_seconds:
            # Full boost — hold at max
            target_gpu  = self.gpu_max
            target_cpu  = self.cpu_max
            new_phase   = "BOOST"
        elif elapsed >= self.gpu_rampup_start:
            # GPU ramp-up window: linearly from gpu_warmup → gpu_max over (warmup_seconds - gpu_rampup_start)
            ramp_window = self.warmup_seconds - self.gpu_rampup_start
            ramp_frac   = (elapsed - self.gpu_rampup_start) / ramp_window
            target_gpu  = self.gpu_warmup + ramp_frac * (self.gpu_max - self.gpu_warmup)
            target_cpu  = self.cpu_max   # CPU still free during ramp
            new_phase   = "RAMPUP"
        else:
            # Pure warmup: GPU flat at minimum, CPU uncapped for IO/loading
            target_gpu  = self.gpu_warmup
            target_cpu  = self.cpu_max
            new_phase   = "WARMUP"

        # 3. Apply GPU fraction (only update if changed by > 1%)
        if abs(target_gpu - self._current_gpu_fraction) > 0.01:
            ok = _set_gpu_memory_fraction(target_gpu)
            if ok:
                self._current_gpu_fraction = target_gpu

        # 4. Enforce CPU Hard Cap on phase changes or initialization
        if new_phase != self._phase:
            _apply_cpu_hard_cap(target_cpu)
            
            logger.info(
                f"Phase -> {new_phase} | "
                f"GPU fraction: {self._current_gpu_fraction:.0%} "
                f"({'plugged in' if self._plugged_in else 'BATTERY'}) | "
                f"CPU hard cap: {target_cpu:.0f}%"
            )
            self._phase = new_phase

        # 6. Log periodic heartbeat at BOOST phase
        if new_phase == "BOOST" and int(elapsed) % 30 < int(MONITOR_INTERVAL):
            status = self.status_dict()
            logger.info(
                f"[{self._phase}] GPU VRAM: {status['gpu_vram_used_gb']:.2f} GB "
                f"/ {self._current_gpu_fraction:.0%} limit | "
                f"CPU: {status['cpu_percent']:.1f}%"
            )

    def handle_oom(self) -> None:
        """
        Call this from a CUDA OOM except handler.
        Backs off GPU fraction by 5% to prevent repeated crashes.
        """
        new_frac = max(0.40, self._current_gpu_fraction - OOM_BACKOFF)
        logger.warning(
            f"OOM detected! Backing off GPU fraction: "
            f"{self._current_gpu_fraction:.0%} → {new_frac:.0%}"
        )
        _set_gpu_memory_fraction(new_frac)
        self._current_gpu_fraction = new_frac
        torch.cuda.empty_cache()


# ──────────────────────────────────────────────────────
# Global singleton — import and call .start() anywhere
# ──────────────────────────────────────────────────────
_global_monitor: Optional[HardwareMonitor] = None


def get_monitor(auto_start: bool = True) -> HardwareMonitor:
    """
    Returns (and optionally starts) the global singleton HardwareMonitor.
    Safe to call multiple times — only one instance is ever created.

    Example
    -------
        from src.hardware_monitor import get_monitor
        monitor = get_monitor()   # auto-starts if not running
    """
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = HardwareMonitor()
    if auto_start and _global_monitor._thread is None:
        _global_monitor.start()
    return _global_monitor


# ──────────────────────────────────────────────────────
# Standalone dashboard mode
# ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  ChakraModel Hardware Monitor — Live Dashboard")
    print(f"  Phase 1 WARMUP  (0–{GPU_RAMPUP_START}s):  GPU flat at {GPU_WARMUP_FRACTION:.0%} (~{GPU_WARMUP_FRACTION*4:.1f} GB) | CPU free")
    print(f"  Phase 2 RAMPUP  ({GPU_RAMPUP_START}–{WARMUP_SECONDS}s): GPU ramps {GPU_WARMUP_FRACTION:.0%} → {GPU_MAX_FRACTION:.0%} linearly")
    print(f"  Phase 3 BOOST   ({WARMUP_SECONDS}s+): GPU at {GPU_MAX_FRACTION:.0%} (~{GPU_MAX_FRACTION*4:.1f} GB) | CPU < {CPU_MAX_PERCENT:.0f}%")
    print(f"  Battery mode: GPU {GPU_BATTERY_FRACTION:.0%} (~{GPU_BATTERY_FRACTION*4:.1f} GB) | CPU < {CPU_BATTERY_MAX:.0f}%")
    print("  Press Ctrl+C to exit")
    print("=" * 60)

    monitor = HardwareMonitor()
    monitor.start()

    try:
        while True:
            s = monitor.status_dict()
            gpu_gb = s["gpu_vram_used_gb"]
            bar_len = int(s["gpu_vram_fraction"] * 38)
            bar = "█" * bar_len + "░" * (38 - bar_len)

            print(
                f"\r  [{s['phase']:8s}] "
                f"GPU: [{bar}] {s['gpu_vram_fraction']:.0%} ({gpu_gb:.2f} GB) | "
                f"CPU: {s['cpu_percent']:5.1f}% | "
                f"{'🔌 AC' if s['plugged_in'] else '🔋 BATT'} | "
                f"Warmup: {s['warmup_remaining_s']:.0f}s left   ",
                end="", flush=True
            )
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nStopping monitor...")
        monitor.stop()
