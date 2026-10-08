#!/usr/bin/env python3
"""
Real-Time WebSocket Streaming Monitor
Connects to PulseAI backend and displays live ECG classification, confidence, and FHIR reports.
Simulates patient registration and ECG streaming with real-time model predictions.
"""

import asyncio
import json
import numpy as np
import websockets
import httpx
import time
from datetime import datetime
from typing import Optional
import sys

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws"

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

def print_header(title: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(80)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")

def print_section(title: str):
    """Print formatted section"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}▶ {title}{Colors.RESET}")
    print(f"{Colors.DIM}─" * 80 + f"{Colors.RESET}")

def generate_ecg_sample(heart_rate: int = 70, duration_samples: int = 100) -> list:
    """Generate synthetic ECG sample"""
    t = np.arange(duration_samples) / 500  # 500 Hz sampling
    signal = (
        50 +
        15 * np.sin(2 * np.pi * (heart_rate / 60.0) * t) +
        5 * np.sin(2 * np.pi * (heart_rate / 60.0) * 2 * t) +
        np.random.normal(0, 1.5, duration_samples)
    )
    return signal.astype(np.float32).tolist()

async def register_patient(patient_id: str, name: str, age: int) -> bool:
    """Register patient via HTTP API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/api/patient",
                json={
                    "patient_id": patient_id,
                    "name": name,
                    "age": age
                },
                timeout=5.0
            )
            response.raise_for_status()
            
            print(f"{Colors.GREEN}✓ Patient registered:{Colors.RESET}")
            print(f"  ID: {Colors.BOLD}{patient_id}{Colors.RESET}")
            print(f"  Name: {Colors.BOLD}{name}{Colors.RESET}, Age: {Colors.BOLD}{age}{Colors.RESET}")
            return True
    except Exception as e:
        print(f"{Colors.RED}✗ Failed to register patient: {e}{Colors.RESET}")
        return False

async def stream_ecg_data(duration_seconds: int = 10, heart_rate: int = 70):
    """Stream ECG data to backend"""
    print(f"\n{Colors.BOLD}Streaming ECG data ({duration_seconds}s at {heart_rate} bpm)...{Colors.RESET}")
    
    total_samples = duration_seconds * 500  # 500 Hz
    samples_sent = 0
    
    try:
        async with httpx.AsyncClient() as client:
            while samples_sent < total_samples:
                # Generate chunk (100 samples)
                chunk = generate_ecg_sample(heart_rate, 100)
                
                # Send via API
                await client.post(
                    f"{BASE_URL}/api/ingest",
                    json=chunk,
                    timeout=2.0,
                    params={"value": chunk[0]}
                )
                
                samples_sent += 100
                progress = samples_sent / total_samples * 100
                
                # Progress bar
                bar_length = 40
                filled = int(bar_length * samples_sent / total_samples)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"\r{Colors.CYAN}[{bar}] {progress:.0f}% ({samples_sent}/{total_samples} samples){Colors.RESET}", end='', flush=True)
                
                await asyncio.sleep(0.05)  # Simulate real-time streaming
        
        print(f"\n{Colors.GREEN}✓ ECG streaming complete{Colors.RESET}")
        return True
    except Exception as e:
        print(f"\n{Colors.RED}✗ Stream failed: {e}{Colors.RESET}")
        return False

async def get_latest_prediction():
    """Get latest prediction from backend"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/api/diagnostic", timeout=5.0)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"{Colors.RED}Error fetching prediction: {e}{Colors.RESET}")
        return None

async def connect_websocket():
    """Connect to WebSocket for real-time updates"""
    print_section("WebSocket Live Stream (30 seconds)")
    print(f"{Colors.YELLOW}Connecting to {WS_URL}...{Colors.RESET}")
    
    prediction_count = 0
    start_time = time.time()
    timeout = 30  # seconds
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            print(f"{Colors.GREEN}✓ WebSocket connected{Colors.RESET}\n")
            
            while time.time() - start_time < timeout:
                try:
                    # Set timeout for receiving
                    msg = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(msg)
                    
                    msg_type = data.get("type", "unknown")
                    
                    if msg_type == "prediction":
                        prediction_count += 1
                        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        
                        classification = data.get("classification", "Unknown")
                        confidence = data.get("confidence", 0)
                        heart_rate = data.get("heart_rate_bpm")
                        signal_quality = data.get("signal_quality", "unknown")
                        is_arrhythmia = data.get("is_arrhythmia", False)
                        
                        # Color by result
                        color = Colors.RED if is_arrhythmia else Colors.GREEN
                        icon = "⚠️ " if is_arrhythmia else "✓ "
                        
                        print(f"{Colors.DIM}[{timestamp}]{Colors.RESET} {icon}{color}{Colors.BOLD}{classification}{Colors.RESET}")
                        print(f"          Confidence: {confidence:.1%} | Quality: {signal_quality}")
                        if heart_rate:
                            print(f"          Heart Rate: {int(heart_rate)} bpm")
                        print()
                    
                    elif msg_type == "leads_off":
                        print(f"{Colors.YELLOW}⚠️  LEADS OFF - Check electrode connection!{Colors.RESET}\n")
                    
                    elif msg_type == "leads_on":
                        print(f"{Colors.GREEN}✓ Leads reconnected{Colors.RESET}\n")
                
                except asyncio.TimeoutError:
                    # No message in timeout, continue waiting
                    elapsed = int(time.time() - start_time)
                    remaining = timeout - elapsed
                    print(f"\r{Colors.DIM}Waiting for predictions... ({remaining}s remaining){Colors.RESET}", end='', flush=True)
                    await asyncio.sleep(0.1)
            
            print(f"\n{Colors.CYAN}Stream timeout reached{Colors.RESET}")
            print(f"{Colors.BOLD}Predictions received: {prediction_count}{Colors.RESET}")
    
    except Exception as e:
        print(f"{Colors.RED}WebSocket error: {e}{Colors.RESET}")

async def demo_scenario(scenario_name: str, patient_id: str, name: str, age: int, heart_rate: int = 70):
    """Run a complete demo scenario"""
    print_header(f"SCENARIO: {scenario_name}")
    
    # 1. Register patient
    print_section("Patient Registration")
    if not await register_patient(patient_id, name, age):
        return False
    
    # 2. Set data source
    print_section("Data Source Configuration")
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{BASE_URL}/api/source",
                params={"source": "SIMULATION"},
                timeout=5.0
            )
            print(f"{Colors.GREEN}✓ Source set to: SIMULATION{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.YELLOW}⚠️  Could not set source: {e}{Colors.RESET}")
    
    # 3. Stream ECG data
    print_section("ECG Data Streaming")
    if not await stream_ecg_data(duration_seconds=5, heart_rate=heart_rate):
        return False
    
    # 4. Get prediction
    await asyncio.sleep(1)
    print_section("Model Prediction")
    prediction = await get_latest_prediction()
    
    if prediction:
        if "conclusion" in prediction:  # FHIR report
            print(f"{Colors.RED}{Colors.BOLD}⚠️  ABNORMAL FINDING - FHIR Report:{Colors.RESET}")
            print(f"  Conclusion: {Colors.BOLD}{prediction.get('conclusion', 'N/A')}{Colors.RESET}")
            if "extension" in prediction:
                for ext in prediction["extension"][:2]:  # Show first 2 extensions
                    print(f"  {ext.get('url', 'N/A')}: {ext.get('valueString', ext.get('valueDecimal', 'N/A'))}")
        else:
            print(f"{Colors.GREEN}✓ Normal - No abnormal report needed{Colors.RESET}")
            print(f"  Status: {Colors.BOLD}{prediction.get('status', 'monitoring')}{Colors.RESET}")
    
    return True

async def main():
    """Main async entry point"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔" + "═"*78 + "╗")
    print("║" + " "*15 + "PulseAI: Real-Time WebSocket Streaming Monitor" + " "*18 + "║")
    print("║" + " "*18 + "Live ECG Classification & Model Predictions" + " "*17 + "║")
    print("╚" + "═"*78 + "╝")
    print(Colors.RESET)
    
    # Check backend health
    print_section("Backend Health Check")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5.0)
            health = response.json()
            print(f"{Colors.GREEN}✓ Backend Status: {health.get('status', 'unknown')}{Colors.RESET}")
            print(f"  Version: {Colors.BOLD}{health.get('version', 'N/A')}{Colors.RESET}")
            print(f"  Model: {Colors.BOLD}{health.get('model_used', 'N/A')}{Colors.RESET}")
            print(f"  Source: {Colors.BOLD}{health.get('active_source', 'N/A')}{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}✗ Backend unavailable: {e}{Colors.RESET}")
        print(f"{Colors.YELLOW}Make sure to run: python -m uvicorn main:app --port 8000{Colors.RESET}")
        return
    
    # Run demo scenarios
    scenarios = [
        ("Young Adult - Normal Rhythm", "PA-001", "Raj Kumar", 22, 72),
        ("Middle Age - Elevated HR", "PA-002", "Priya Singh", 42, 95),
        ("Elderly - Normal", "PA-003", "Harsha Reddy", 68, 62),
    ]
    
    results = []
    for scenario_name, patient_id, name, age, hr in scenarios:
        success = await demo_scenario(scenario_name, patient_id, name, age, hr)
        results.append((scenario_name, success))
        await asyncio.sleep(1)
    
    # Summary
    print_header("REAL-TIME STREAMING DEMO - SUMMARY")
    total = len(results)
    passed = sum(1 for _, success in results if success)
    
    for scenario_name, success in results:
        icon = f"{Colors.GREEN}✓{Colors.RESET}" if success else f"{Colors.RED}✗{Colors.RESET}"
        print(f"{icon} {scenario_name}")
    
    print(f"\n{Colors.BOLD}Total: {passed}/{total} scenarios completed{Colors.RESET}\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Demo interrupted by user{Colors.RESET}\n")
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error: {e}{Colors.RESET}\n")
        sys.exit(1)
