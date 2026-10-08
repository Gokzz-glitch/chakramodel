#!/usr/bin/env python3
"""
Real-Time Model Detection Monitor
Shows live ECG classification and FHIR report generation as data streams in.
"""

import asyncio
import json
import time
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from ml_model import ArrhythmiaEngine
from signal_processing import process_ecg, extract_beat_window, FS, SEGMENT_LEN
from fhir_generator import generate_fhir_diagnostic_report

# Color codes for terminal
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BLUE = '\033[94m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

def clear_screen():
    """Clear terminal screen"""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')

def generate_test_ecg_stream(patient_profile: dict):
    """Generate continuous ECG stream for testing"""
    case_id = patient_profile["case_id"]
    age = patient_profile["age"]
    condition = patient_profile["condition"]
    
    # Generate base signal
    if "AFib" in condition or "Irregular" in condition:
        # AFib pattern - irregular intervals
        samples = int(5 * FS)
        t = np.arange(samples) / FS
        signal = 50 * np.ones(samples)
        
        beat_times = []
        current_time = 0
        while current_time < 5:
            interval = np.random.uniform(0.4, 0.8)
            beat_times.append(current_time)
            current_time += interval
        
        for beat_time in beat_times:
            beat_idx = int(beat_time * FS)
            if beat_idx < samples:
                qrs_duration = int(0.1 * FS)
                qrs_end = min(beat_idx + qrs_duration, samples)
                signal[beat_idx:qrs_end] += 20 * np.sin(
                    np.pi * np.arange(qrs_end - beat_idx) / (qrs_end - beat_idx)
                )
        signal += np.random.normal(0, 3.0, samples)
    else:
        # Normal rhythm
        samples = int(5 * FS)
        t = np.arange(samples) / FS
        hr = patient_profile.get("heart_rate", 70)
        signal = (
            50 +
            15 * np.sin(2 * np.pi * (hr / 60.0) * t) +
            5 * np.sin(2 * np.pi * (hr / 60.0) * 2 * t)
        )
        signal += np.random.normal(0, 1.5, samples)
    
    return signal.astype(np.float32)

def run_live_detection(patient_profile: dict):
    """Run real-time detection for a single patient"""
    case_id = patient_profile["case_id"]
    age = patient_profile["age"]
    name = patient_profile["name"]
    scenario = patient_profile["scenario"]
    condition = patient_profile["condition"]
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.GREEN}▶ REAL-TIME ECG DETECTION - CASE #{case_id}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    
    print(f"\n{Colors.BOLD}Patient Profile:{Colors.RESET}")
    print(f"  {Colors.MAGENTA}Name:{Colors.RESET}      {name}")
    print(f"  {Colors.MAGENTA}Age:{Colors.RESET}       {age} years")
    print(f"  {Colors.MAGENTA}Scenario:{Colors.RESET}  {scenario}")
    print(f"  {Colors.MAGENTA}Condition:{Colors.RESET} {condition}")
    
    # Initialize engine
    engine = ArrhythmiaEngine()
    
    # Generate and stream ECG data
    print(f"\n{Colors.BOLD}Generating ECG Stream...{Colors.RESET}")
    raw_signal = generate_test_ecg_stream(patient_profile)
    
    # Process in chunks (simulating real-time streaming)
    chunk_size = 500  # 1 second of data
    inference_count = 0
    
    print(f"{Colors.BOLD}\nStreaming ECG Data:{Colors.RESET}")
    print(f"{Colors.DIM}(Processing {chunk_size} samples per inference = 1 second...){Colors.RESET}\n")
    
    for i in range(0, len(raw_signal) - SEGMENT_LEN, chunk_size):
        chunk = raw_signal[i:i + chunk_size].tolist()
        
        # Progress indicator
        progress = (i + chunk_size) / len(raw_signal) * 100
        bar_length = 40
        filled = int(bar_length * (i + chunk_size) / len(raw_signal))
        bar = '█' * filled + '░' * (bar_length - filled)
        
        print(f"\r{Colors.CYAN}[{bar}] {progress:.0f}% {Colors.RESET}", end='', flush=True)
        
        # Simulate streaming (shorter so demo is fast)
        time.sleep(0.1)
    
    print(f"\n\n{Colors.BOLD}{Colors.YELLOW}🔄 Running Model Inference...{Colors.RESET}")
    time.sleep(0.5)
    
    # Process final window for inference
    cleaned = process_ecg(raw_signal.tolist())
    window = extract_beat_window(cleaned)
    
    # Run inference
    result = engine.predict(window)
    
    # Display results
    classification = result.get("classification", "Unknown")
    confidence = result.get("confidence", 0.0)
    is_arrhythmia = result.get("is_arrhythmia", False)
    heart_rate = result.get("heart_rate_bpm")
    rr_cv = result.get("rr_cv")
    signal_quality = result.get("signal_quality", "unknown")
    model_used = result.get("model_used", "unknown")
    
    # Color coding for results
    if is_arrhythmia:
        status_color = Colors.RED
        status_icon = "⚠️ "
    else:
        status_color = Colors.GREEN
        status_icon = "✓ "
    
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}INFERENCE RESULTS:{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")
    
    print(f"  {status_icon}{status_color}{Colors.BOLD}Classification:{Colors.RESET}")
    print(f"    → {Colors.BOLD}{classification}{Colors.RESET}")
    
    print(f"\n  {Colors.MAGENTA}Confidence:{Colors.RESET}        {Colors.BOLD}{confidence:.1%}{Colors.RESET}")
    print(f"  {Colors.MAGENTA}Is Arrhythmia:{Colors.RESET}      {Colors.BOLD}{is_arrhythmia}{Colors.RESET}")
    print(f"  {Colors.MAGENTA}Signal Quality:{Colors.RESET}    {Colors.BOLD}{signal_quality}{Colors.RESET}")
    
    if heart_rate:
        print(f"  {Colors.MAGENTA}Heart Rate:{Colors.RESET}       {Colors.BOLD}{int(heart_rate)} bpm{Colors.RESET}")
    if rr_cv:
        print(f"  {Colors.MAGENTA}RR-CV:{Colors.RESET}            {Colors.BOLD}{rr_cv:.3f}{Colors.RESET}")
    
    print(f"  {Colors.MAGENTA}Model Used:{Colors.RESET}        {Colors.BOLD}{model_used}{Colors.RESET}")
    
    # Generate FHIR Report if abnormal
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}FHIR DIAGNOSTIC REPORT:{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")
    
    if is_arrhythmia:
        print(f"{Colors.RED}{Colors.BOLD}⚠️  ABNORMAL REPORT GENERATED{Colors.RESET}\n")
        
        fhir_report = generate_fhir_diagnostic_report(
            patient_id=f"patient-{case_id:03d}",
            classification=classification,
            confidence=confidence,
            explainability_map=result.get("explainability_map")
        )
        
        # Display FHIR report
        print(f"{Colors.BOLD}FHIR Resource (DiagnosticReport):{Colors.RESET}")
        print(f"{Colors.DIM}{'-'*80}{Colors.RESET}")
        fhir_json = json.dumps(fhir_report, indent=2)
        # Limit output for readability
        lines = fhir_json.split('\n')[:20]
        print('\n'.join(lines))
        if len(fhir_json.split('\n')) > 20:
            print(f"{Colors.DIM}... ({len(fhir_json.split('\n')) - 20} more lines){Colors.RESET}")
        print(f"{Colors.DIM}{'-'*80}{Colors.RESET}")
    else:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ NORMAL - NO REPORT NEEDED{Colors.RESET}\n")
    
    # Verdict
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    expected = patient_profile.get("expected_classification", "Unknown")
    match = classification == expected
    verdict_color = Colors.GREEN if match else Colors.RED
    verdict_icon = "✓" if match else "✗"
    
    print(f"{Colors.BOLD}VERDICT:{Colors.RESET}")
    print(f"  Expected:  {Colors.BOLD}{expected}{Colors.RESET}")
    print(f"  Predicted: {Colors.BOLD}{classification}{Colors.RESET}")
    print(f"  Result:    {verdict_color}{Colors.BOLD}{verdict_icon} {'PASS' if match else 'FAIL'}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")
    
    return {
        "case_id": case_id,
        "classification": classification,
        "confidence": confidence,
        "is_arrhythmia": is_arrhythmia,
        "match": match
    }

# Test cases
TEST_PATIENTS = [
    {
        "case_id": 1,
        "name": "Raj Kumar",
        "age": 22,
        "scenario": "Light activity - resting",
        "condition": "Normal Sinus Rhythm",
        "expected_classification": "Normal Sinus Rhythm",
        "heart_rate": 72,
    },
    {
        "case_id": 2,
        "name": "Priya Singh",
        "age": 42,
        "scenario": "At rest - stress test",
        "condition": "Atrial Fibrillation Risk",  
        "expected_classification": "Atrial Fibrillation (AFib)",
        "heart_rate": None,
    },
    {
        "case_id": 3,
        "name": "Harsha Reddy",
        "age": 68,
        "scenario": "Healthy - routine checkup",
        "condition": "Normal Sinus Rhythm",
        "expected_classification": "Normal Sinus Rhythm",
        "heart_rate": 62,
    },
]

def main():
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔" + "═"*78 + "╗")
    print("║" + " "*20 + "PulseAI: REAL-TIME MODEL DETECTION DEMO" + " "*20 + "║")
    print("║" + " "*15 + "Live Cardiac Arrhythmia Classification & FHIR Report" + " "*13 + "║")
    print("╚" + "═"*78 + "╝")
    print(Colors.RESET)
    
    results = []
    
    for patient in TEST_PATIENTS:
        try:
            result = run_live_detection(patient)
            results.append(result)
        except Exception as e:
            print(f"\n{Colors.RED}{Colors.BOLD}✗ Error in case {patient['case_id']}: {e}{Colors.RESET}\n")
            results.append({
                "case_id": patient["case_id"],
                "error": str(e),
                "match": False
            })
        
        # Pause between cases
        time.sleep(1)
    
    # Summary
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔" + "═"*78 + "╗")
    print("║" + " "*25 + "REAL-TIME TEST SUMMARY" + " "*31 + "║")
    print("╚" + "═"*78 + "╝")
    print(Colors.RESET)
    
    passed = sum(1 for r in results if r.get("match", False))
    total = len(results)
    accuracy = passed / total * 100 if total > 0 else 0
    
    print(f"\n{Colors.BOLD}Results:{Colors.RESET}")
    print(f"  Total Cases:  {Colors.BOLD}{total}{Colors.RESET}")
    print(f"  Passed:       {Colors.GREEN}{Colors.BOLD}{passed}{Colors.RESET}")
    print(f"  Failed:       {Colors.RED}{Colors.BOLD}{total - passed}{Colors.RESET}")
    print(f"  Accuracy:     {Colors.BOLD}{accuracy:.0f}%{Colors.RESET}\n")
    
    print(f"{Colors.BOLD}{Colors.GREEN}✓ Real-time detection demo complete!{Colors.RESET}\n")

if __name__ == "__main__":
    main()
