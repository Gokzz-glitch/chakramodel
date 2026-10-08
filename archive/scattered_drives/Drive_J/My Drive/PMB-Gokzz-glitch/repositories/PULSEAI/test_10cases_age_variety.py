#!/usr/bin/env python3
"""
Test Suite: 10 Test Cases Across Age Variety
Tests the PulseAI Model on different age groups with varied cardiac conditions.

Test Cases:
1. Young Adult (18-25): Normal sinus rhythm during light activity
2. Young Adult (18-25): Normal sinus rhythm at rest
3. Middle Age (35-45): Normal sinus rhythm with slight exercise stress
4. Middle Age (35-45): Atrial Fibrillation risk (elevated RR variation)
5. Adult (50-60): Normal sinus rhythm (baseline)
6. Adult (50-60): Possible AFib with irregular beats
7. Elderly (65-75): Normal sinus rhythm (healthy)
8. Elderly (65-75): Premature ventricular contractions (PVC)
9. Very Elderly (80+): Normal sinus rhythm (slow HR)
10. Very Elderly (80+): AFib with rapid ventricular response
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# ============================================================================
# PART 1: Setup & Imports
# ============================================================================

print("=" * 70)
print("PulseAI: 10-Case Age-Variety Test Suite")
print("=" * 70)

# Find project root
project_root = Path(__file__).parent
backend_path = project_root / 'backend'

if backend_path.exists() and (backend_path / 'ml_model.py').exists():
    sys.path.insert(0, str(backend_path))
    print(f"[OK] Backend found at {backend_path}")
else:
    print("[ERR] Backend not found. Make sure you're running from project root.")
    sys.exit(1)

try:
    from ml_model import ArrhythmiaEngine
    from signal_processing import process_ecg, extract_beat_window, FS, SEGMENT_LEN
    print("[OK] Backend modules imported successfully")
except ImportError as e:
    print(f"[ERR] Failed to import backend modules: {e}")
    sys.exit(1)

# ============================================================================
# PART 2: ECG Signal Generation (Age & Condition Based)
# ============================================================================

def generate_ecg_normal_rhythm(duration_sec: float = 5.0, heart_rate: int = 70, 
                               base_amplitude: float = 50.0) -> np.ndarray:
    """Generate a synthetic normal sinus rhythm ECG signal."""
    samples = int(duration_sec * FS)
    t = np.arange(samples) / FS
    
    # Base sinusoidal signal (fundamental ECG pattern)
    qrs_frequency = heart_rate / 60.0
    signal = (
        base_amplitude +
        15 * np.sin(2 * np.pi * qrs_frequency * t) +
        5 * np.sin(2 * np.pi * qrs_frequency * 2 * t) +
        2 * np.sin(2 * np.pi * qrs_frequency * 0.5 * t)
    )
    
    # Add physiological noise
    noise = np.random.normal(0, 1.5, samples)
    signal += noise
    
    return signal.astype(np.float32)


def generate_ecg_afib_pattern(duration_sec: float = 5.0, base_amplitude: float = 50.0) -> np.ndarray:
    """Generate AFib-like signal with irregular RR intervals."""
    samples = int(duration_sec * FS)
    t = np.arange(samples) / FS
    signal = base_amplitude * np.ones(samples)
    
    # Simulate irregular beats with random intervals (AFib characteristic)
    beat_times = []
    current_time = 0
    while current_time < duration_sec:
        interval = np.random.uniform(0.4, 0.8)  # Irregular RR intervals
        beat_times.append(current_time)
        current_time += interval
    
    # Add QRS complexes at irregular intervals
    for beat_time in beat_times:
        beat_idx = int(beat_time * FS)
        if beat_idx < samples:
            qrs_duration = int(0.1 * FS)  # 100ms QRS
            qrs_end = min(beat_idx + qrs_duration, samples)
            signal[beat_idx:qrs_end] += 20 * np.sin(np.pi * np.arange(qrs_end - beat_idx) / (qrs_end - beat_idx))
    
    # Add high-frequency noise characteristic of AFib
    noise = np.random.normal(0, 3.0, samples)
    signal += noise
    
    return signal.astype(np.float32)


def generate_ecg_pvc_pattern(duration_sec: float = 5.0, base_amplitude: float = 50.0) -> np.ndarray:
    """Generate signal with Premature Ventricular Contractions (PVC)."""
    signal = generate_ecg_normal_rhythm(duration_sec, heart_rate=65, base_amplitude=base_amplitude)
    
    # Inject 2-3 premature beats
    num_pvcs = np.random.randint(2, 4)
    samples = len(signal)
    for _ in range(num_pvcs):
        pvc_idx = np.random.randint(int(0.5 * FS), int((duration_sec - 0.5) * FS))
        pvc_duration = int(0.15 * FS)
        pvc_end = min(pvc_idx + pvc_duration, samples)
        # Make PVC more prominent
        signal[pvc_idx:pvc_end] += 25 * np.sin(np.pi * np.arange(pvc_end - pvc_idx) / (pvc_end - pvc_idx))
    
    return signal.astype(np.float32)


# ============================================================================
# PART 3: Test Case Definitions
# ============================================================================

TEST_CASES = [
    {
        "case_id": 1,
        "age": 22,
        "age_group": "Young Adult (18-25)",
        "scenario": "Light activity - resting",
        "condition": "Normal Sinus Rhythm",
        "expected_classification": "Normal Sinus Rhythm",
        "heart_rate": 72,
        "generator": lambda: generate_ecg_normal_rhythm(5.0, 72, 48),
    },
    {
        "case_id": 2,
        "age": 20,
        "age_group": "Young Adult (18-25)",
        "scenario": "Post-exercise recovery",
        "condition": "Normal Sinus Rhythm",
        "expected_classification": "Normal Sinus Rhythm",
        "heart_rate": 95,
        "generator": lambda: generate_ecg_normal_rhythm(5.0, 95, 52),
    },
    {
        "case_id": 3,
        "age": 40,
        "age_group": "Middle Age (35-45)",
        "scenario": "Moderate exercise - gym session",
        "condition": "Normal Sinus Rhythm (elevated HR)",
        "expected_classification": "Normal Sinus Rhythm",
        "heart_rate": 110,
        "generator": lambda: generate_ecg_normal_rhythm(5.0, 110, 54),
    },
    {
        "case_id": 4,
        "age": 42,
        "age_group": "Middle Age (35-45)",
        "scenario": "At rest - stress test result",
        "condition": "Atrial Fibrillation Risk",
        "expected_classification": "Atrial Fibrillation (AFib)",
        "heart_rate": None,
        "generator": lambda: generate_ecg_afib_pattern(5.0, 50),
    },
    {
        "case_id": 5,
        "age": 55,
        "age_group": "Adult (50-60)",
        "scenario": "Baseline - morning checkup",
        "condition": "Normal Sinus Rhythm",
        "expected_classification": "Normal Sinus Rhythm",
        "heart_rate": 68,
        "generator": lambda: generate_ecg_normal_rhythm(5.0, 68, 50),
    },
    {
        "case_id": 6,
        "age": 58,
        "age_group": "Adult (50-60)",
        "scenario": "Symptomatic - palpitations",
        "condition": "Possible AFib",
        "expected_classification": "Atrial Fibrillation (AFib)",
        "heart_rate": None,
        "generator": lambda: generate_ecg_afib_pattern(5.0, 48),
    },
    {
        "case_id": 7,
        "age": 68,
        "age_group": "Elderly (65-75)",
        "scenario": "Healthy - routine checkup",
        "condition": "Normal Sinus Rhythm",
        "expected_classification": "Normal Sinus Rhythm",
        "heart_rate": 62,
        "generator": lambda: generate_ecg_normal_rhythm(5.0, 62, 52),
    },
    {
        "case_id": 8,
        "age": 72,
        "age_group": "Elderly (65-75)",
        "scenario": "Symptomatic - irregular heartbeats",
        "condition": "Premature Ventricular Contractions",
        "expected_classification": "Other Arrhythmia",
        "heart_rate": 65,
        "generator": lambda: generate_ecg_pvc_pattern(5.0, 50),
    },
    {
        "case_id": 9,
        "age": 82,
        "age_group": "Very Elderly (80+)",
        "scenario": "Baseline - bradycardia normal",
        "condition": "Normal Sinus Rhythm (slow)",
        "expected_classification": "Normal Sinus Rhythm",
        "heart_rate": 55,
        "generator": lambda: generate_ecg_normal_rhythm(5.0, 55, 50),
    },
    {
        "case_id": 10,
        "age": 85,
        "age_group": "Very Elderly (80+)",
        "scenario": "Symptomatic - rapid irregular",
        "condition": "AFib with Rapid Ventricular Response",
        "expected_classification": "Atrial Fibrillation (AFib)",
        "heart_rate": None,
        "generator": lambda: generate_ecg_afib_pattern(5.0, 48),
    },
]

# ============================================================================
# PART 4: Run Inference
# ============================================================================

def run_test(test_case: Dict) -> Dict:
    """Run a single test case through the model."""
    print(f"\n[Case {test_case['case_id']}] {test_case['age_group']} | {test_case['scenario']}")
    print(f"  Condition: {test_case['condition']}")
    print(f"  Expected: {test_case['expected_classification']}")
    
    # Generate synthetic ECG signal
    raw_signal = test_case['generator']()
    
    # Process ECG (same as backend pipeline)
    cleaned = process_ecg(raw_signal.tolist())
    window = extract_beat_window(cleaned)
    
    # Initialize and run inference
    engine = ArrhythmiaEngine()
    result = engine.predict(window)
    
    # Determine if prediction matches expectation
    predicted = result.get("classification", "Unknown")
    confidence = result.get("confidence", 0.0)
    match = "PASS" if predicted == test_case["expected_classification"] else "FAIL"
    
    print(f"  Predicted: {predicted} [{confidence:.2%}] {match}")
    
    return {
        "case_id": test_case["case_id"],
        "age": test_case["age"],
        "age_group": test_case["age_group"],
        "scenario": test_case["scenario"],
        "condition": test_case["condition"],
        "expected": test_case["expected_classification"],
        "predicted": predicted,
        "confidence": confidence,
        "heart_rate_bpm": result.get("heart_rate_bpm"),
        "rr_cv": result.get("rr_cv"),
        "signal_quality": result.get("signal_quality"),
        "is_arrhythmia": result.get("is_arrhythmia", False),
        "model_used": result.get("model_used", "unknown"),
        "timestamp": datetime.now().isoformat(),
        "match": match == "PASS",
    }

# ============================================================================
# PART 5: Execute All Tests & Collect Results
# ============================================================================

print("\nRunning 10 test cases across age variety...")
print("-" * 70)

results = []
for test_case in TEST_CASES:
    try:
        result = run_test(test_case)
        results.append(result)
    except Exception as e:
        print(f"  [ERR] Error: {e}")
        results.append({
            "case_id": test_case["case_id"],
            "age": test_case["age"],
            "age_group": test_case["age_group"],
            "scenario": test_case["scenario"],
            "condition": test_case["condition"],
            "expected": test_case["expected_classification"],
            "predicted": "ERROR",
            "confidence": 0.0,
            "match": False,
            "error": str(e),
        })

# ============================================================================
# PART 6: Generate Reports
# ============================================================================

print("\n" + "=" * 70)
print("TEST RESULTS SUMMARY")
print("=" * 70)

df = pd.DataFrame(results)
print(f"\nTotal Tests: {len(results)}")
print(f"Passed: {df['match'].sum()}")
print(f"Failed: {(~df['match']).sum()}")
print(f"Accuracy: {df['match'].mean():.1%}")

print("\n" + "-" * 70)
print("Results by Age Group:")
print("-" * 70)

for age_group in df['age_group'].unique():
    subset = df[df['age_group'] == age_group]
    accuracy = subset['match'].mean()
    count = len(subset)
    print(f"{age_group:25s} | Cases: {count} | Accuracy: {accuracy:.1%}")

print("\n" + "-" * 70)
print("Detailed Results:")
print("-" * 70)

for idx, row in df.iterrows():
    match_icon = "PASS" if row['match'] else "FAIL"
    print(f"\n[Case {int(row['case_id'])}] {match_icon} {row['age_group']}")
    print(f"  Age: {int(row['age'])} | Scenario: {row['scenario']}")
    print(f"  Condition: {row['condition']}")
    print(f"  Expected → Predicted: {row['expected']} → {row['predicted']}")
    print(f"  Confidence: {row['confidence']:.2%} | Signal Quality: {row['signal_quality']}")
    hr = row.get('heart_rate_bpm')
    rr = row.get('rr_cv')
    if pd.notna(hr):
        if pd.notna(rr):
            print(f"  Heart Rate: {int(hr)} bpm | RR-CV: {float(rr):.3f}")
        else:
            print(f"  Heart Rate: {int(hr)} bpm")

# ============================================================================
# PART 7: Save Reports
# ============================================================================

output_dir = project_root / "test_results"
output_dir.mkdir(exist_ok=True)

# Save CSV
csv_path = output_dir / f"test_10cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
df.to_csv(csv_path, index=False)
print(f"\n[OK] CSV report saved: {csv_path}")

# Save JSON
json_path = output_dir / f"test_10cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(json_path, 'w') as f:
    json.dump({
        "test_suite": "10-Case Age Variety Test",
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(results),
        "accuracy": float(df['match'].mean()),
        "results": results,
    }, f, indent=2)
print(f"[OK] JSON report saved: {json_path}")

# ============================================================================
# PART 8: Visualization
# ============================================================================

print("\nGenerating visualization...")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle("PulseAI: 10-Case Age-Variety Test Results", fontsize=16, fontweight='bold')

# Plot 1: Accuracy by Age Group
ax = axes[0, 0]
age_groups = df['age_group'].unique()
accuracies = [df[df['age_group'] == ag]['match'].mean() for ag in age_groups]
colors = ['#00f5d4' if acc == 1.0 else '#f43f5e' for acc in accuracies]
ax.bar(range(len(age_groups)), accuracies, color=colors, edgecolor='white', linewidth=2)
ax.set_xticks(range(len(age_groups)))
ax.set_xticklabels([ag.split('(')[0].strip() for ag in age_groups], rotation=45, ha='right')
ax.set_ylabel('Accuracy', fontweight='bold')
ax.set_title('Accuracy by Age Group', fontweight='bold')
ax.set_ylim([0, 1.1])
ax.grid(axis='y', alpha=0.3)

# Plot 2: Confidence Distribution
ax = axes[0, 1]
ax.hist(df['confidence'], bins=10, color='#00f5d4', edgecolor='white', linewidth=2, alpha=0.7)
ax.set_xlabel('Confidence Score', fontweight='bold')
ax.set_ylabel('Frequency', fontweight='bold')
ax.set_title('Confidence Distribution', fontweight='bold')
ax.grid(axis='y', alpha=0.3)

# Plot 3: Classification Breakdown
ax = axes[1, 0]
classifications = df['predicted'].value_counts()
colors_pie = ['#00f5d4', '#f43f5e', '#a78bfa'][:len(classifications)]
ax.pie(classifications.values, labels=classifications.index, autopct='%1.1f%%',
       colors=colors_pie, startangle=90)
ax.set_title('Predicted Classifications', fontweight='bold')

# Plot 4: Age vs Confidence
ax = axes[1, 1]
colors_scatter = ['#00f5d4' if m else '#f43f5e' for m in df['match']]
ax.scatter(df['age'], df['confidence'], s=100, c=colors_scatter, edgecolor='white', linewidth=2, alpha=0.7)
ax.set_xlabel('Age (years)', fontweight='bold')
ax.set_ylabel('Confidence', fontweight='bold')
ax.set_title('Age vs Prediction Confidence', fontweight='bold')
ax.grid(alpha=0.3)

plt.tight_layout()
plot_path = output_dir / f"test_10cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
plt.savefig(plot_path, dpi=150, bbox_inches='tight', facecolor='#0f1419')
print(f"[OK] Visualization saved: {plot_path}")

print("\n" + "=" * 70)
print("TEST SUITE COMPLETE")
print("=" * 70)
