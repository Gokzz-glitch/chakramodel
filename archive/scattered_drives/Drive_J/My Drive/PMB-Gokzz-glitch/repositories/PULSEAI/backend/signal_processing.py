import numpy as np  # type: ignore
from scipy import signal as sp_signal  # type: ignore
from typing import Any

FS = 500          # AD8232 / ESP32 sample rate (configurable)
SEGMENT_LEN = 1000  # 2s context window for rhythm-aware inference

def _bandpass_coeffs(lowcut=0.5, highcut=40.0, fs=FS, order=4):
    nyq = 0.5 * fs
    return sp_signal.butter(order, [lowcut / nyq, highcut / nyq], btype='band')

def _notch_coeffs(freq=50.0, fs=FS, Q=30):
    """50Hz (India) powerline noise notch."""
    return sp_signal.iirnotch(freq / (fs / 2.0), Q)


def _median_filter(data: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    k = max(3, int(kernel_size) | 1)
    return sp_signal.medfilt(data, kernel_size=k)


def _hampel_filter(data: np.ndarray, window: int = 9, n_sigma: float = 3.0) -> np.ndarray:
    x = data.copy()
    n = len(x)
    w = max(3, int(window) | 1)
    half = w // 2
    k = 1.4826
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        seg = x[start:end]
        med = float(np.median(seg))
        mad = float(np.median(np.abs(seg - med)))
        thresh = n_sigma * k * max(mad, 1e-6)
        if abs(x[i] - med) > thresh:
            x[i] = med
    return x


def _soft_clip(data: np.ndarray, limit: float = 2.4) -> np.ndarray:
    lim = max(0.1, float(limit))
    return lim * np.tanh(data / lim)

def process_ecg(raw_signal_buffer: list, fs: int = FS, filter_config: dict[str, Any] | None = None) -> list:
    """
    Full clinical ECG preprocessing pipeline using sos to prevent NaN/numerical collapse:
      1. High-pass (0.5 Hz) — removes baseline wander / DC drift
      2. Notch (50 Hz)      — removes Indian powerline interference
      3. Bandpass (0.5–40 Hz) — retains clinically relevant ECG band
    Returns a float list of the same length as input.
    """
    if len(raw_signal_buffer) < 10:
        return raw_signal_buffer

    cfg = filter_config or {}
    notch_enabled = bool(cfg.get("notch_enabled", True))
    hp_enabled = bool(cfg.get("hp_enabled", True))
    lp_enabled = bool(cfg.get("lp_enabled", True))
    ma_enabled = bool(cfg.get("ma_enabled", False))
    median_enabled = bool(cfg.get("median_enabled", False))
    hampel_enabled = bool(cfg.get("hampel_enabled", False))
    clip_enabled = bool(cfg.get("clip_enabled", False))
    mains_hz = float(cfg.get("mains_hz", 50.0))

    data = np.array(raw_signal_buffer, dtype=np.float64)

    if hp_enabled:
        sos_hp = sp_signal.butter(4, 0.5 / (fs / 2.0), btype='high', output='sos')
        data = sp_signal.sosfiltfilt(sos_hp, data)

    if notch_enabled:
        b_n, a_n = _notch_coeffs(mains_hz, fs)
        data = sp_signal.filtfilt(b_n, a_n, data)

    if lp_enabled:
        sos_lp = sp_signal.butter(4, 40.0 / (fs / 2.0), btype='low', output='sos')
        data = sp_signal.sosfiltfilt(sos_lp, data)

    if median_enabled:
        data = _median_filter(data, kernel_size=5)

    if hampel_enabled:
        data = _hampel_filter(data, window=9, n_sigma=3.0)

    if ma_enabled:
        kernel = np.ones(7, dtype=np.float64) / 7.0
        data = np.convolve(data, kernel, mode='same')

    if clip_enabled:
        data = _soft_clip(data, limit=2.4)

    # Convert NaNs to 0 in case of an issue
    data = np.nan_to_num(data, nan=0.0)

    return data.tolist()


def compute_signal_quality_index(raw_signal: list, cleaned_signal: list) -> float:
    """Compute a lightweight SQI score in [0, 1] for runtime gating."""
    raw = np.asarray(raw_signal, dtype=np.float64)
    clean = np.asarray(cleaned_signal, dtype=np.float64)

    if clean.size < 16:
        return 0.0

    finite_ratio = float(np.mean(np.isfinite(clean)))
    if finite_ratio < 0.95:
        return max(0.0, finite_ratio - 0.2)

    amp_span = float(np.percentile(clean, 95) - np.percentile(clean, 5))
    slope_energy = float(np.mean(np.abs(np.diff(clean)))) if clean.size > 1 else 0.0
    baseline_shift = float(abs(np.mean(clean)))
    raw_clip_ratio = 0.0
    if raw.size > 8:
        raw_abs = np.abs(raw)
        clip_thr = float(np.percentile(raw_abs, 99.5))
        if clip_thr > 1e-6:
            raw_clip_ratio = float(np.mean(raw_abs >= clip_thr))

    amp_score = float(np.clip(amp_span / 1.8, 0.0, 1.0))
    slope_score = 1.0 - float(np.clip(slope_energy / 0.8, 0.0, 1.0))
    baseline_score = 1.0 - float(np.clip(baseline_shift / 0.8, 0.0, 1.0))
    clip_score = 1.0 - float(np.clip(raw_clip_ratio * 5.0, 0.0, 1.0))

    sqi = 0.45 * amp_score + 0.25 * slope_score + 0.2 * baseline_score + 0.1 * clip_score
    return float(np.clip(sqi, 0.0, 1.0))


def classify_signal_quality(sqi: float) -> str:
    if sqi >= 0.70:
        return "good"
    if sqi >= 0.45:
        return "fair"
    return "poor"

def extract_beat_window(cleaned_signal: list, r_peak_idx: int | None = None) -> list:
    """
    Extract a SEGMENT_LEN window centered on the strongest peak (R-peak),
    or centered in the signal if no peak given. Used for per-beat inference.
    """
    data = np.array(cleaned_signal, dtype=np.float32)
    if data.size == 0:
        return []

    if r_peak_idx is None:
        # Auto-center on dominant peak to improve beat alignment at inference time.
        abs_data = np.abs(data)
        if data.size >= 12:
            try:
                min_distance = max(1, int(0.12 * FS))
                height = max(0.05, float(np.percentile(abs_data, 82)))
                peaks, props = sp_signal.find_peaks(abs_data, distance=min_distance, height=height)
                if peaks.size > 0:
                    heights = props.get("peak_heights")
                    if heights is not None and len(heights) == len(peaks):
                        r_peak_idx = int(peaks[int(np.argmax(heights))])
                    else:
                        r_peak_idx = int(peaks[int(np.argmax(abs_data[peaks]))])
                else:
                    r_peak_idx = int(np.argmax(abs_data))
            except Exception:
                r_peak_idx = int(np.argmax(abs_data))
        else:
            r_peak_idx = int(np.argmax(abs_data))

    half = SEGMENT_LEN // 2
    start = max(0, r_peak_idx - half)
    end = start + SEGMENT_LEN
    if end > len(data):
        end = len(data)
        start = max(0, end - SEGMENT_LEN)

    window = data[start:end]
    # Pad if shorter than SEGMENT_LEN
    if len(window) < SEGMENT_LEN:
        window = np.pad(window, (0, SEGMENT_LEN - len(window)), mode='edge')

    # Return the raw window so models can evaluate amplitude severity.
    return window.tolist()
