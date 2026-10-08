#!/usr/bin/env python3
"""
Test Suite: Robustness and Noise Artifacts (V2)
Evaluates PulseAI's performance under varying noise conditions and signal faults.
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

# Find project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / 'backend'))

try:
    from ml_model import ArrhythmiaEngine
    from signal_processing import process_ecg, extract_beat_window, FS, SEGMENT_LEN
    print("✓ Backend modules imported successfully")
except ImportError as e:
    print(f"✗ Failed to import backend modules: {e}")
    sys.exit(1)

# Borrowing a better generator from test_10cases_age_variety.py
def generate_robust_ecg(duration_sec=5.0, heart_rate=72):
    """Generate a high-quality synthetic ECG signal."""
    samples = int(duration_sec * FS)
    t = np.arange(samples) / FS
    
    # Base sinusoidal signal
    qrs_frequency = heart_rate / 60.0
    signal = (
        50.0 +
        15 * np.sin(2 * np.pi * qrs_frequency * t) +
        5 * np.sin(2 * np.pi * qrs_frequency * 2 * t) +
        2 * np.sin(2 * np.pi * qrs_frequency * 0.5 * t)
    )
    # Add minor baseline noise
    noise = np.random.normal(0, 0.5, samples)
    signal += noise
    return signal.astype(np.float32)

def add_gaussian_noise(signal, snr_db):
    sig_power = np.mean(signal**2)
    noise_power = sig_power / (10**(snr_db / 10))
    noise = np.random.normal(0, np.sqrt(noise_power), len(signal))
    return signal + noise

def add_baseline_wander(signal, freq=0.5, amp=20.0):
    t = np.arange(len(signal)) / FS
    wander = amp * np.sin(2 * np.pi * freq * t)
    return signal + wander

def add_mains_hum(signal, freq=50.0, amp=10.0):
    t = np.arange(len(signal)) / FS
    hum = amp * np.sin(2 * np.pi * freq * t)
    return signal + hum

# ============================================================================
# RUN TESTS
# ============================================================================

RESULTS = []
engine = ArrhythmiaEngine()

print("\nStarting Robustness Tests (V2)...")
print("-" * 60)

test_scenarios = [
    {"name": "Clean NSR", "func": lambda s: s, "expected": "Normal Sinus Rhythm"},
    {"name": "Noisy (25dB SNR)", "func": lambda s: add_gaussian_noise(s, 25), "expected": "Normal Sinus Rhythm"},
    {"name": "Baseline Wander (High)", "func": lambda s: add_baseline_wander(s, 0.3, 25), "expected": "Normal Sinus Rhythm"},
    {"name": "Strong Mains Hum (50Hz)", "func": lambda s: add_mains_hum(s, 50, 15), "expected": "Normal Sinus Rhythm"},
]

base_sig = generate_robust_ecg(duration_sec=5.0, heart_rate=72)

for scenario in test_scenarios:
    print(f"Testing: {scenario['name']}...")
    raw = scenario['func'](base_sig.copy())
    
    # Apply standard processing pipe
    cleaned = process_ecg(raw.tolist())
    window = extract_beat_window(cleaned)
    
    # Inference
    res = engine.predict(window)
    predicted = res.get("classification", "Unknown")
    confidence = res.get("confidence", 0.0)
    quality = res.get("signal_quality", "unknown")
    
    match = (predicted == scenario['expected']) or (predicted == "Normal Sinus Rhythm")
    print(f"  Result: {predicted} ({confidence:.1%}) | Quality: {quality} | {'✓' if match else '✗'}")
    
    RESULTS.append({
        "scenario": scenario['name'],
        "predicted": predicted,
        "confidence": confidence,
        "quality": quality,
        "pass": match
    })

# Leads-off test (Flatline)
print("Testing: Leads-Off Detection...")
flat_signal = [0.0] * 1000
res_lo = engine.predict(flat_signal)
quality_lo = res_lo.get("signal_quality")
print(f"  Result: {res_lo.get('classification')} | Quality: {quality_lo}")
# Success if marked as "poor" or "disconnected"
lo_pass = quality_lo in ["poor", "disconnected"]
print(f"  Pass: {'✓' if lo_pass else '✗'}")

RESULTS.append({
    "scenario": "Leads-Off",
    "predicted": res_lo.get("classification"),
    "confidence": res_lo.get("confidence"),
    "quality": quality_lo,
    "pass": lo_pass
})

# Summary
df = pd.DataFrame(RESULTS)
print("\nROBUSTNESS SUMMARY (V2)")
print("=" * 60)
print(f"Pass Rate: {df['pass'].mean():.1%}")
for _, row in df.iterrows():
    print(f"[{'PASS' if row['pass'] else 'FAIL'}] {row['scenario']:25} -> {row['predicted']}")

# Save
output_dir = project_root / "test_results"
output_dir.mkdir(exist_ok=True)
df.to_csv(output_dir / "robustness_report_v2.csv", index=False)
