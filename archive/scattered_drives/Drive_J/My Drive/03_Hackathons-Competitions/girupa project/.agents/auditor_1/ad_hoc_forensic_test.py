import ast
import json
import os
import random
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid

# Force UTF-8 encoding on standard output for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = r"J:\My Drive\girupa project"
SERVER_PY = os.path.join(PROJECT_ROOT, "server.py")
TEST_BOOKING_PY = os.path.join(PROJECT_ROOT, "test_booking.py")
DB_PATH = os.path.join(PROJECT_ROOT, "booking.db")
BASE_URL = "http://127.0.0.1:8000"

def get_fresh_db():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.isolation_level = None
    return conn

print("=" * 80)
print("FORENSIC AUDITOR INDEPENDENT EMPIRICAL INTEGRITY SUITE")
print("=" * 80)

# ----------------------------------------------------------------------
# 1. AST Static Analysis & Cheating / Facade Detection
# ----------------------------------------------------------------------
print("\n[CHECK 1] Static AST Analysis of server.py and test_booking.py...")

with open(SERVER_PY, "r", encoding="utf-8") as f:
    server_code = f.read()
server_ast = ast.parse(server_code)

# Check for mock imports
suspicious_imports = ["mock", "unittest.mock", "responses", "httpretty", "freezegun"]
for node in ast.walk(server_ast):
    if isinstance(node, ast.Import):
        for n in node.names:
            assert n.name not in suspicious_imports, f"Suspicious import in server.py: {n.name}"
    elif isinstance(node, ast.ImportFrom):
        assert node.module not in suspicious_imports, f"Suspicious import from in server.py: {node.module}"

# Check for hardcoded conditional routing based on test user strings
test_user_strings = ["prof_tester", "Prof. Alan Turing", "Ada Lovelace", "Dr. Claude Shannon", "guest_fac"]
for s in test_user_strings:
    assert s not in server_code, f"Cheating detected! Specific test payload string '{s}' found in server.py"

print("  [PASS] server.py contains NO mock libraries and NO hardcoded test payload strings.")

# Check test_booking.py for live network requests
with open(TEST_BOOKING_PY, "r", encoding="utf-8") as f:
    test_code = f.read()

assert "urllib.request" in test_code, "test_booking.py does not import urllib.request"
assert "urlopen" in test_code, "test_booking.py does not call urlopen"
assert "return True" not in test_code.replace(" ", ""), "Facade pass detection in test_booking.py"
print("  [PASS] test_booking.py imports urllib.request and invokes live urlopen calls.")

# ----------------------------------------------------------------------
# 2. SQLite Database Existence & Schema Integrity
# ----------------------------------------------------------------------
print("\n[CHECK 2] SQLite Database Existence & Schema Verification...")
assert os.path.isfile(DB_PATH), f"Database file {DB_PATH} does not exist!"
print(f"  [PASS] Database file exists: {DB_PATH} (size: {os.path.getsize(DB_PATH)} bytes)")

conn = get_fresh_db()
cur = conn.cursor()

# Check tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = {row[0] for row in cur.fetchall()}
assert "resources" in tables, "Table 'resources' missing from booking.db"
assert "bookings" in tables, "Table 'bookings' missing from booking.db"
print(f"  [PASS] Verified tables present: {tables}")

# Check indexes
cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
indexes = {row[0] for row in cur.fetchall()}
assert "idx_bookings_resource_window" in indexes, "Index 'idx_bookings_resource_window' missing"
print(f"  [PASS] Verified compound conflict index present: idx_bookings_resource_window")

# Check resources table rows
cur.execute("SELECT count(*) FROM resources;")
res_count = cur.fetchone()[0]
assert res_count >= 10, f"Expected at least 10 seeded resources, found {res_count}"
print(f"  [PASS] Verified seeded resources count: {res_count}")

# ----------------------------------------------------------------------
# 3. Ad-Hoc Live Booking & Conflict Prevention with Random Nonce
# ----------------------------------------------------------------------
print("\n[CHECK 3] Ad-Hoc Live HTTP Booking with Random Timestamps & DB Verification...")

cur.execute("SELECT id FROM resources WHERE is_active = 1;")
res_ids = [row[0] for row in cur.fetchall()]
selected_resource = random.choice(res_ids)
conn.close()

# Generate a unique timestamp in the far future to avoid any collision
nonce = random.randint(100000, 999999)
start_hour = random.randint(8, 14)
rand_day = random.randint(1, 28)
rand_month = random.randint(1, 12)
rand_year = 2040 + random.randint(1, 5)

start_iso = f"{rand_year:04d}-{rand_month:02d}-{rand_day:02d}T{start_hour:02d}:15:00"
end_iso = f"{rand_year:04d}-{rand_month:02d}-{rand_day:02d}T{start_hour + 2:02d}:15:00"
auditor_user_id = f"auditor_usr_{nonce}"
auditor_user_name = f"Forensic Auditor Agent {nonce}"
event_title = f"Forensic Integrity Verification Colloquium {nonce}"

payload = {
    "resource_id": selected_resource,
    "user_id": auditor_user_id,
    "user_name": auditor_user_name,
    "start_time": start_iso,
    "end_time": end_iso,
    "event_title": event_title
}

print(f"  Attempting ad-hoc booking for resource: {selected_resource}")
print(f"  Time window: {start_iso} -> {end_iso}")
print(f"  Payload User: {auditor_user_id} ({auditor_user_name})")

req_data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    f"{BASE_URL}/api/bookings",
    data=req_data,
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    method="POST"
)

with urllib.request.urlopen(req, timeout=5) as resp:
    status1 = resp.status
    body1 = json.loads(resp.read().decode())

assert status1 == 201, f"Expected 201 Created, got {status1}: {body1}"
assert "id" in body1, f"Missing id in response: {body1}"
created_booking_id = body1["id"]
print(f"  [PASS] HTTP POST returned 201 Created! Generated Booking ID: {created_booking_id}")

# Allow server thread commit to finalize to disk
time.sleep(0.1)

# Directly inspect SQLite DB using a fresh connection to confirm the row was genuinely written
db_row = None
for attempt in range(5):
    conn = get_fresh_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, resource_id, user_id, user_name, start_time, end_time, event_title, status FROM bookings WHERE id = ?;",
        (created_booking_id,)
    )
    db_row = cur.fetchone()
    conn.close()
    if db_row:
        break
    time.sleep(0.1)

assert db_row is not None, f"FATAL: Booking ID {created_booking_id} was NOT found in booking.db!"
assert db_row[1] == selected_resource, f"DB resource_id mismatch: {db_row[1]} != {selected_resource}"
assert db_row[2] == auditor_user_id, f"DB user_id mismatch: {db_row[2]} != {auditor_user_id}"
assert db_row[3] == auditor_user_name, f"DB user_name mismatch: {db_row[3]} != {auditor_user_name}"
assert db_row[4] == start_iso, f"DB start_time mismatch: {db_row[4]} != {start_iso}"
assert db_row[5] == end_iso, f"DB end_time mismatch: {db_row[5]} != {end_iso}"
assert db_row[6] == event_title, f"DB event_title mismatch: {db_row[6]} != {event_title}"
assert db_row[7] == "CONFIRMED", f"DB status mismatch: {db_row[7]} != CONFIRMED"
print(f"  [PASS] Empirically verified row in booking.db: {db_row}")

# ----------------------------------------------------------------------
# 4. Duplicate Booking Rejection (409 Conflict)
# ----------------------------------------------------------------------
print("\n[CHECK 4] Repeating Exact Same Booking -> Assert 409 Conflict Rejection...")

duplicate_payload = {
    "resource_id": selected_resource,
    "user_id": f"another_user_{nonce}",
    "user_name": "Another Challenger",
    "start_time": start_iso,
    "end_time": end_iso,
    "event_title": "Conflicting Booking Attempt"
}

req_dup = urllib.request.Request(
    f"{BASE_URL}/api/bookings",
    data=json.dumps(duplicate_payload).encode("utf-8"),
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req_dup, timeout=5) as resp:
        assert False, f"Expected 409 Conflict, but server returned HTTP {resp.status}!"
except urllib.error.HTTPError as err:
    assert err.code == 409, f"Expected HTTP 409, got {err.code}"
    err_body = json.loads(err.read().decode())
    assert "conflict_with" in err_body, f"Conflict response missing conflict_with: {err_body}"
    assert err_body["conflict_with"]["id"] == created_booking_id, f"Conflict id mismatch: {err_body}"
    print(f"  [PASS] Server correctly rejected duplicate slot with HTTP 409 Conflict!")
    print(f"  [PASS] Response conflict details identified booking: {err_body['conflict_with']['id']}")

# ----------------------------------------------------------------------
# 5. Overlapping Booking Rejection (Partial Overlap: Starts Inside)
# ----------------------------------------------------------------------
print("\n[CHECK 5] Testing Partial Overlapping Booking (Starts Inside) -> Assert 409 Conflict...")

overlap_start = f"{rand_year:04d}-{rand_month:02d}-{rand_day:02d}T{start_hour + 1:02d}:00:00"
overlap_end = f"{rand_year:04d}-{rand_month:02d}-{rand_day:02d}T{start_hour + 3:02d}:00:00"

req_overlap = urllib.request.Request(
    f"{BASE_URL}/api/bookings",
    data=json.dumps({
        "resource_id": selected_resource,
        "user_id": f"overlap_usr_{nonce}",
        "user_name": "Overlap Requester",
        "start_time": overlap_start,
        "end_time": overlap_end,
        "event_title": "Overlapping Event Attempt"
    }).encode("utf-8"),
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req_overlap, timeout=5) as resp:
        assert False, f"Expected 409 Conflict for partial overlap, but got {resp.status}!"
except urllib.error.HTTPError as err:
    assert err.code == 409, f"Expected HTTP 409, got {err.code}"
    err_body = json.loads(err.read().decode())
    assert err_body["conflict_with"]["id"] == created_booking_id, "Overlap did not identify conflict target"
    print(f"  [PASS] Server correctly rejected overlapping slot ({overlap_start} -> {overlap_end}) with HTTP 409 Conflict!")

# ----------------------------------------------------------------------
# 6. Lifecycle & Cancellation Verification (DELETE /api/bookings/{id})
# ----------------------------------------------------------------------
print("\n[CHECK 6] Testing Booking Cancellation & Slot Release...")

req_del = urllib.request.Request(
    f"{BASE_URL}/api/bookings/{created_booking_id}",
    headers={"Accept": "application/json"},
    method="DELETE"
)

with urllib.request.urlopen(req_del, timeout=5) as resp:
    status_del = resp.status
    body_del = json.loads(resp.read().decode())

assert status_del == 200, f"Expected 200 OK for DELETE, got {status_del}: {body_del}"
assert body_del.get("status") == "CANCELLED", f"Expected CANCELLED status, got {body_del}"
print(f"  [PASS] DELETE /api/bookings/{created_booking_id} returned HTTP 200 CANCELLED.")

time.sleep(0.1)

# Check DB to confirm status updated to CANCELLED
conn = get_fresh_db()
cur = conn.cursor()
cur.execute("SELECT status FROM bookings WHERE id = ?;", (created_booking_id,))
cancelled_status = cur.fetchone()[0]
conn.close()

assert cancelled_status == "CANCELLED", f"DB status not updated to CANCELLED, got {cancelled_status}"
print("  [PASS] Empirically verified in SQLite that booking status is CANCELLED.")

# Now verify the same time slot can be booked again now that previous booking is cancelled
print("\n[CHECK 7] Re-booking Slot After Cancellation -> Assert 201 Created...")
req_rebook = urllib.request.Request(
    f"{BASE_URL}/api/bookings",
    data=json.dumps({
        "resource_id": selected_resource,
        "user_id": f"rebook_usr_{nonce}",
        "user_name": "Rebooking User",
        "start_time": start_iso,
        "end_time": end_iso,
        "event_title": "Slot Reclaimed Event"
    }).encode("utf-8"),
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    method="POST"
)

with urllib.request.urlopen(req_rebook, timeout=5) as resp:
    status_rebook = resp.status
    body_rebook = json.loads(resp.read().decode())

assert status_rebook == 201, f"Expected 201 for slot rebooking after cancellation, got {status_rebook}"
rebooked_id = body_rebook["id"]
print(f"  [PASS] Slot successfully rebooked (Booking ID: {rebooked_id}) after cancellation!")

# Clean up rebooked record
req_del2 = urllib.request.Request(
    f"{BASE_URL}/api/bookings/{rebooked_id}",
    headers={"Accept": "application/json"},
    method="DELETE"
)
with urllib.request.urlopen(req_del2, timeout=5) as resp:
    assert resp.status == 200

print("\n" + "=" * 80)
print("ALL FORENSIC INTEGRITY CHECKS PASSED EMPIRICALLY!")
print("Verdict: CLEAN (No cheating, no facades, genuine SQLite persistence & network execution)")
print("=" * 80)
