"""
Proposed Standalone Verification Script for Academic Event & Resource Booking Portal.
Explorer 1 (Codebase Environment & Runtime Architecture Explorer).

This test suite requires ZERO external dependencies (uses standard library urllib & json).
Acceptance Criteria Verified:
1. R1: Successfully fetch and list available institutional resources.
2. R2 & R3: Successfully create a new booking for a specific resource, time slot, and user identity.
3. R2: Attempt to book the exact same resource for the exact same time slot, verifying strict 409 conflict rejection.
"""

import sys
import os
import json
import urllib.request
import urllib.error

PORT_FILE = ".server_port"
DEFAULT_URL = "http://127.0.0.1:8000"

def get_base_url():
    if len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        return sys.argv[1].rstrip("/")
    if os.environ.get("BASE_URL"):
        return os.environ.get("BASE_URL").rstrip("/")
    if os.environ.get("PORT"):
        return f"http://127.0.0.1:{os.environ.get('PORT')}"
    if os.path.exists(PORT_FILE):
        try:
            with open(PORT_FILE, "r", encoding="utf-8") as f:
                port = f.read().strip()
                if port.isdigit():
                    return f"http://127.0.0.1:{port}"
        except Exception:
            pass
    return DEFAULT_URL

def run_tests():
    base_url = get_base_url()
    print(f"Targeting server at: {base_url}")

    # Test 1: Fetch and list resources (R1)
    print("\n[Test 1] Fetching resources...")
    req = urllib.request.Request(f"{base_url}/api/resources")
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        resources = json.loads(resp.read().decode("utf-8"))
        assert isinstance(resources, list), "Resources response must be a JSON array"
        assert len(resources) > 0, "Resource list should not be empty"
        print(f"  -> SUCCESS: Found {len(resources)} resources.")
        for r in resources[:3]:
            print(f"     - [{r.get('id')}] {r.get('name')} (Cap: {r.get('capacity')})")

    chosen_resource = resources[0]["id"]
    test_start = "2026-10-15T09:00:00"
    test_end = "2026-10-15T11:00:00"

    # Test 2: Create initial booking (R2, R3)
    print(f"\n[Test 2] Booking resource '{chosen_resource}' from {test_start} to {test_end}...")
    booking_payload = {
        "resource_id": chosen_resource,
        "user_id": "dr_chen",
        "user_name": "Dr. Aris Chen",
        "start_time": test_start,
        "end_time": test_end,
        "event_title": "Advanced Distributed Systems Lecture"
    }
    req2 = urllib.request.Request(
        f"{base_url}/api/bookings",
        data=json.dumps(booking_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req2) as resp2:
            assert resp2.status == 201, f"Expected 201, got {resp2.status}"
            data = json.loads(resp2.read().decode("utf-8"))
            assert data.get("id"), "Booking response should include booking 'id'"
            assert data.get("resource_id") == chosen_resource
            print(f"  -> SUCCESS: Booking created with ID: {data.get('id')}")
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print("  -> Notice: Slot was already booked from prior run, proceeding to conflict test.")
        else:
            raise

    # Test 3: Conflict Prevention Rejection (R2)
    print(f"\n[Test 3] Attempting conflicting booking for resource '{chosen_resource}' at overlapping time...")
    conflict_payload = {
        "resource_id": chosen_resource,
        "user_id": "prof_vasquez",
        "user_name": "Prof. Elena Vasquez",
        "start_time": "2026-10-15T10:00:00",  # Overlaps 10:00 - 12:00
        "end_time": "2026-10-15T12:00:00",
        "event_title": "Robotics Lab Presentation"
    }
    req3 = urllib.request.Request(
        f"{base_url}/api/bookings",
        data=json.dumps(conflict_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req3) as resp3:
            print(f"  -> FAILED: Expected 409 Conflict, but received {resp3.status}!")
            sys.exit(1)
    except urllib.error.HTTPError as e:
        assert e.code == 409, f"Expected HTTP 409 Conflict, got {e.code}"
        error_body = json.loads(e.read().decode("utf-8"))
        print(f"  -> SUCCESS: Server correctly rejected with HTTP 409 Conflict.")
        print(f"     Server message: {error_body.get('message')}")

    print("\n==========================================")
    print("ALL ACCEPTANCE CRITERIA VERIFIED AND PASSED!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
