#!/usr/bin/env python3
"""
Independent Ad-Hoc Victory Audit Test Suite
Executed by Victory Auditor to verify R1, R2, R3, concurrency, database persistence, and API behavior.
"""

import os
import sys
import json
import time
import uuid
import sqlite3
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", ".."))
PORT_FILE = os.path.join(PROJECT_ROOT, ".server_port")
DB_PATH = os.path.join(PROJECT_ROOT, "booking.db")

# 1. Resolve Server URL
with open(PORT_FILE, "r", encoding="utf-8") as f:
    port = f.read().strip()
BASE_URL = f"http://127.0.0.1:{port}"
print(f"[AUDIT] Target URL: {BASE_URL}")
print(f"[AUDIT] DB Path: {DB_PATH}")

def request(method, path, body=None):
    url = f"{BASE_URL}{path}"
    headers = {"Accept": "application/json", "User-Agent": "VictoryAuditor/1.0"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = raw
            return resp.status, parsed
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = raw
        return e.code, parsed

passed = 0
failed = 0

def check(name, condition, details=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name}: {details}")
        failed += 1

print("\n--- PHASE 1: R1 Resource Display & Management ---")
status, resources = request("GET", "/api/resources")
check("GET /api/resources returns 200", status == 200)
check("Resources count >= 5", isinstance(resources, list) and len(resources) >= 5, f"Count: {len(resources) if isinstance(resources, list) else 'N/A'}")

# Validate categories
types = {r["type"] for r in resources}
check("Contains seminar_hall", "seminar_hall" in types)
check("Contains lab", "lab" in types)
check("Contains classroom", "classroom" in types)

# Check single resource endpoint
first_res_id = resources[0]["id"]
status, single_res = request("GET", f"/api/resources/{first_res_id}")
check("GET /api/resources/{id} returns 200", status == 200)
check("Resource id matches", single_res.get("id") == first_res_id)

# Check 404 on nonexistent resource
status, not_found_res = request("GET", "/api/resources/non_existent_99999")
check("GET /api/resources/invalid returns 404", status == 404)

print("\n--- PHASE 2: R2 & R3 Genuine Booking, Persistence & Identification ---")
# Use unique timestamp in year 2049
test_year = 2049
nonce = uuid.uuid4().hex[:6]
target_res = "hall-a"
slot_start = f"{test_year}-05-10T10:00:00"
slot_end = f"{test_year}-05-10T12:00:00"
test_user_id = f"auditor_user_{nonce}"
test_user_name = "Independent Victory Auditor"
test_title = f"Autonomous Verification Symposium {nonce}"

booking_payload = {
    "resource_id": target_res,
    "user_id": test_user_id,
    "user_name": test_user_name,
    "start_time": slot_start,
    "end_time": slot_end,
    "event_title": test_title
}

status, booking_resp = request("POST", "/api/bookings", booking_payload)
check("POST /api/bookings returns 201 Created", status == 201)
booking_id = booking_resp.get("id")
check("Booking response has generated ID", bool(booking_id))
check("Booking response preserves user_id (R3)", booking_resp.get("user_id") == test_user_id)
check("Booking response preserves user_name (R3)", booking_resp.get("user_name") == test_user_name)

# Verify direct SQLite persistence
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
db_row = cur.execute("SELECT id, resource_id, user_id, user_name, start_time, end_time, event_title, status FROM bookings WHERE id = ?", (booking_id,)).fetchone()
conn.close()

check("Database persistence check: row exists in SQLite", db_row is not None)
if db_row:
    check("Database row id matches", db_row[0] == booking_id)
    check("Database row resource_id matches", db_row[1] == target_res)
    check("Database row user_id matches (R3)", db_row[2] == test_user_id)
    check("Database row user_name matches (R3)", db_row[3] == test_user_name)
    check("Database row status is CONFIRMED", db_row[7] == "CONFIRMED")

print("\n--- PHASE 3: R2 Conflict Prevention (Half-Open Interval Check) ---")
# 1. Exact duplicate
status, dup_resp = request("POST", "/api/bookings", booking_payload)
check("Exact duplicate slot rejected with 409 Conflict", status == 409)

# 2. Overlap: Starts before, ends inside (09:00 - 11:00)
status, overlap1 = request("POST", "/api/bookings", {
    "resource_id": target_res,
    "user_id": f"u1_{nonce}",
    "user_name": "Overlap One",
    "start_time": f"{test_year}-05-10T09:00:00",
    "end_time": f"{test_year}-05-10T11:00:00",
    "event_title": "Overlap Head"
})
check("Overlap (starts before, ends inside) rejected with 409", status == 409)

# 3. Overlap: Starts inside, ends after (11:00 - 13:00)
status, overlap2 = request("POST", "/api/bookings", {
    "resource_id": target_res,
    "user_id": f"u2_{nonce}",
    "user_name": "Overlap Two",
    "start_time": f"{test_year}-05-10T11:00:00",
    "end_time": f"{test_year}-05-10T13:00:00",
    "event_title": "Overlap Tail"
})
check("Overlap (starts inside, ends after) rejected with 409", status == 409)

# 4. Overlap: Fully inside (10:30 - 11:30)
status, overlap3 = request("POST", "/api/bookings", {
    "resource_id": target_res,
    "user_id": f"u3_{nonce}",
    "user_name": "Overlap Three",
    "start_time": f"{test_year}-05-10T10:30:00",
    "end_time": f"{test_year}-05-10T11:30:00",
    "event_title": "Overlap Enclosed"
})
check("Overlap (fully inside) rejected with 409", status == 409)

# 5. Overlap: Fully enclosing (08:00 - 14:00)
status, overlap4 = request("POST", "/api/bookings", {
    "resource_id": target_res,
    "user_id": f"u4_{nonce}",
    "user_name": "Overlap Four",
    "start_time": f"{test_year}-05-10T08:00:00",
    "end_time": f"{test_year}-05-10T14:00:00",
    "event_title": "Overlap Enclosing"
})
check("Overlap (fully enclosing) rejected with 409", status == 409)

# 6. Adjacent touching prior slot (08:00 - 10:00) -> Allowed
status, adj_prior = request("POST", "/api/bookings", {
    "resource_id": target_res,
    "user_id": f"u_prior_{nonce}",
    "user_name": "Prior Adjacent",
    "start_time": f"{test_year}-05-10T08:00:00",
    "end_time": f"{test_year}-05-10T10:00:00",
    "event_title": "Touching Prior Slot"
})
check("Adjacent prior slot [08:00, 10:00) allowed (201 Created)", status == 201)

# 7. Adjacent touching subsequent slot (12:00 - 14:00) -> Allowed
status, adj_sub = request("POST", "/api/bookings", {
    "resource_id": target_res,
    "user_id": f"u_sub_{nonce}",
    "user_name": "Subsequent Adjacent",
    "start_time": f"{test_year}-05-10T12:00:00",
    "end_time": f"{test_year}-05-10T14:00:00",
    "event_title": "Touching Subsequent Slot"
})
check("Adjacent subsequent slot [12:00, 14:00) allowed (201 Created)", status == 201)

print("\n--- PHASE 4: R3 User Identity Validation ---")
# Missing user_id
status, _ = request("POST", "/api/bookings", {
    "resource_id": target_res,
    "user_name": "Missing ID User",
    "start_time": f"{test_year}-05-11T10:00:00",
    "end_time": f"{test_year}-05-11T12:00:00",
    "event_title": "Missing User ID Event"
})
check("Missing user_id rejected with 400", status == 400)

# Missing user_name
status, _ = request("POST", "/api/bookings", {
    "resource_id": target_res,
    "user_id": "missing_name_id",
    "start_time": f"{test_year}-05-11T10:00:00",
    "end_time": f"{test_year}-05-11T12:00:00",
    "event_title": "Missing User Name Event"
})
check("Missing user_name rejected with 400", status == 400)

# Inverted time window
status, _ = request("POST", "/api/bookings", {
    "resource_id": target_res,
    "user_id": "time_traveler",
    "user_name": "Doc Brown",
    "start_time": f"{test_year}-05-11T12:00:00",
    "end_time": f"{test_year}-05-11T10:00:00",
    "event_title": "Inverted Time"
})
check("Inverted time window (start >= end) rejected with 400", status == 400)

print("\n--- PHASE 5: Concurrency Race Condition Verification ---")
# 10 simultaneous threads competing for exact same unoccupied slot
concurrent_slot_start = f"{test_year}-06-01T14:00:00"
concurrent_slot_end = f"{test_year}-06-01T16:00:00"
concurrent_res = "lab-ai"

def attempt_booking(idx):
    payload = {
        "resource_id": concurrent_res,
        "user_id": f"race_user_{idx}_{nonce}",
        "user_name": f"Race Competitor {idx}",
        "start_time": concurrent_slot_start,
        "end_time": concurrent_slot_end,
        "event_title": f"Race Competition {idx}"
    }
    st, resp = request("POST", "/api/bookings", payload)
    return st

with ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(attempt_booking, range(10)))

created_count = results.count(201)
conflict_count = results.count(409)
print(f"  Concurrency results: {created_count}x 201 Created, {conflict_count}x 409 Conflict")
check("Exactly 1 concurrent request succeeded (201)", created_count == 1)
check("Exactly 9 concurrent requests rejected (409)", conflict_count == 9)

print("\n--- PHASE 6: Static Assets & Web Dashboard Delivery ---")
status, html_content = request("GET", "/")
check("GET / returns 200", status == 200)
check("Dashboard contains HTML title", "Campus Reserve" in str(html_content))

status, css_content = request("GET", "/styles.css")
check("GET /styles.css returns 200", status == 200)

status, js_content = request("GET", "/app.js")
check("GET /app.js returns 200", status == 200)

status, stats = request("GET", "/api/stats")
check("GET /api/stats returns 200", status == 200)
check("Stats includes total_resources", "total_resources" in stats and stats["total_resources"] >= 5)

print("\n" + "=" * 50)
print(f"INDEPENDENT AUDIT RESULT: {passed} PASSED, {failed} FAILED")
print("=" * 50)

if failed == 0:
    print("ALL INDEPENDENT AD-HOC VERIFICATIONS PASSED!")
    sys.exit(0)
else:
    print(f"FAILED: {failed} checks failed!")
    sys.exit(1)
