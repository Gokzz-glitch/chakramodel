#!/usr/bin/env python3
"""
Adversarial Concurrency & Stress Testing Suite
==============================================
Challenger 1 (teamwork_preview_challenger)

Tests:
1. Simultaneous High-Concurrency Race Condition:
   - 20 threads barrier-synchronized to book the exact same resource & slot at the exact same microsecond.
   - Assert: EXACTLY 1 succeeds (201), EXACTLY 19 rejected with 409 Conflict.
2. High-Volume Rapid Sequential Bookings:
   - 20 non-overlapping slots booked consecutively in rapid succession.
   - Assert: All 20 succeed (201), database consistency verified.
3. Sub-second and Boundary Overlap Stress Testing:
   - 1-second leading overlap (assert 409)
   - 1-second trailing overlap (assert 409)
   - 1-second internal slice (assert 409)
   - 1-minute leading overlap (assert 409)
   - 1-minute trailing overlap (assert 409)
   - Exact match overlap (assert 409)
   - Enclosing slot overlap (assert 409)
   - Enclosed slot overlap (assert 409)
   - Preceding adjacent boundary touching (assert 201 success)
   - Following adjacent boundary touching (assert 201 success)
4. Concurrent Non-Overlapping Adjacent Bookings:
   - 10 threads concurrently booking adjacent contiguous non-overlapping slots.
   - Assert: All 10 succeed (201) with zero false-positive 409s.
5. Cancellation and Slot Re-claiming Under Concurrency:
   - Cancel an active slot and launch 10 threads racing to claim the freed slot.
   - Assert: Exactly 1 succeeds (201), 9 rejected with 409.
6. Direct SQLite Database Integrity & Sanity Audit:
   - PRAGMA integrity_check, PRAGMA foreign_key_check, global overlap query across all records.
7. Extreme High-Concurrency Race Condition (50 threads):
   - 50 threads barrier-synchronized on exact same slot.
   - Assert: Exactly 1 succeeds (201), 49 rejected with 409.
8. Cross-Midnight and Year-Boundary Overlap Stress:
   - Spanning Dec 31 to Jan 1 across midnight, verifying correct lexical and chronological handling.
9. Adversarial Malformed & Pathological Input Attacks:
   - Inverted time window, zero duration, unparseable dates, phantom resource, missing fields, whitespace user, invalid DELETE.
"""

import sys
import os
import json
import time
import socket
import sqlite3
import threading
from datetime import datetime, timedelta
import urllib.request
import urllib.error

# Project paths
CHALLENGER_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CHALLENGER_DIR, "..", ".."))
DB_PATH = os.path.join(PROJECT_ROOT, "booking.db")
PORT_FILE = os.path.join(PROJECT_ROOT, ".server_port")

def get_server_url() -> str:
    port = 8000
    if os.path.exists(PORT_FILE):
        try:
            with open(PORT_FILE, "r", encoding="utf-8") as pf:
                port = int(pf.read().strip())
        except Exception:
            pass
    return f"http://127.0.0.1:{port}"

BASE_URL = get_server_url()

def http_request(method: str, path: str, data: dict = None, max_retries: int = 3) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    headers = {"Accept": "application/json"}
    encoded = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        encoded = json.dumps(data).encode("utf-8")
    
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    last_err = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode("utf-8")
                return resp.status, json.loads(body) if body else {}
        except urllib.error.HTTPError as err:
            body = err.read().decode("utf-8")
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {"raw": body}
            return err.code, parsed
        except Exception as e:
            last_err = e
            # Transient TCP connection drop/refusal under high backlog
            time.sleep(0.05 * (attempt + 1))
            continue
    return 599, {"error": str(last_err)}


class StressTestSuite:
    def __init__(self):
        # Generate unique run epoch offset so repeated test executions never collide on slots
        self.run_tag = int(time.time()) % 900000 + 100000
        # Unique base date in future: 2035-01-01 + run_offset days
        self.base_date = datetime(2035, 1, 1, 8, 0, 0) + timedelta(days=self.run_tag % 1000)
        self.results = {}
        self.failures = []

    def record_result(self, test_name: str, passed: bool, details: dict):
        self.results[test_name] = {"passed": passed, "details": details}
        if not passed:
            self.failures.append((test_name, details))
        status_str = "PASS" if passed else "FAIL"
        print(f"[{status_str}] {test_name}")
        for k, v in details.items():
            print(f"       {k}: {v}")

    # =========================================================================
    # Scenario 1: High-Concurrency Race Condition (Exact Same Slot, 20 Threads)
    # =========================================================================
    def test_simultaneous_race_condition(self, num_threads: int = 20):
        print(f"\n--- Running Scenario 1: High-Concurrency Race ({num_threads} threads) ---")
        resource_id = "hall-a"
        slot_start = (self.base_date + timedelta(days=1, hours=2)).isoformat()
        slot_end   = (self.base_date + timedelta(days=1, hours=4)).isoformat()
        
        barrier = threading.Barrier(num_threads)
        thread_outcomes = []
        lock = threading.Lock()

        def worker(thread_idx: int):
            booking_payload = {
                "resource_id": resource_id,
                "user_id": f"racer_s1_{self.run_tag}_{thread_idx:02d}",
                "user_name": f"Concurrent Racer {thread_idx:02d}",
                "start_time": slot_start,
                "end_time": slot_end,
                "event_title": f"Race Attempt Thread {thread_idx:02d}"
            }
            # Wait for all threads to align at barrier before releasing simultaneously
            try:
                barrier.wait(timeout=5.0)
            except threading.BrokenBarrierError:
                pass
            
            t0 = time.perf_counter()
            code, resp = http_request("POST", "/api/bookings", booking_payload)
            elapsed = time.perf_counter() - t0
            
            with lock:
                thread_outcomes.append({
                    "thread_idx": thread_idx,
                    "status_code": code,
                    "response": resp,
                    "latency_ms": round(elapsed * 1000, 2)
                })

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Tally outcomes
        status_counts = {}
        for out in thread_outcomes:
            c = out["status_code"]
            status_counts[c] = status_counts.get(c, 0) + 1

        successes = [o for o in thread_outcomes if o["status_code"] == 201]
        conflicts = [o for o in thread_outcomes if o["status_code"] == 409]
        others = [o for o in thread_outcomes if o["status_code"] not in (201, 409)]

        # DB verification
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        conn.row_factory = sqlite3.Row
        db_rows = conn.execute("""
            SELECT id, user_id, user_name, start_time, end_time, status 
            FROM bookings 
            WHERE resource_id = ? AND status = 'CONFIRMED'
              AND (start_time < ? AND end_time > ?)
        """, (resource_id, slot_end, slot_start)).fetchall()
        conn.close()

        passed = (
            len(successes) == 1 and 
            len(conflicts) == (num_threads - 1) and 
            len(others) == 0 and 
            len(db_rows) == 1
        )

        winning_user = successes[0]["response"].get("user_id") if successes else None
        db_user = db_rows[0]["user_id"] if db_rows else None

        self.record_result(
            "Simultaneous High-Concurrency Race Condition (20 threads)",
            passed,
            {
                "threads_launched": num_threads,
                "status_counts": status_counts,
                "201_success_count": len(successes),
                "409_conflict_count": len(conflicts),
                "unexpected_codes": [o["status_code"] for o in others],
                "db_confirmed_rows": len(db_rows),
                "winning_user_id": winning_user,
                "db_persisted_user_id": db_user,
                "winner_matches_db": winning_user == db_user
            }
        )
        return passed

    # =========================================================================
    # Scenario 2: High-Volume Rapid Sequential Bookings (20 Slots)
    # =========================================================================
    def test_rapid_sequential_bookings(self, count: int = 20):
        print(f"\n--- Running Scenario 2: High-Volume Rapid Sequential ({count} slots) ---")
        resource_id = "lab-ai"
        day_offset = self.base_date + timedelta(days=2)
        
        created_ids = []
        statuses = []
        latencies = []

        for i in range(count):
            start_dt = day_offset + timedelta(hours=i)
            end_dt = start_dt + timedelta(hours=1)
            payload = {
                "resource_id": resource_id,
                "user_id": f"seq_user_{self.run_tag}_{i:02d}",
                "user_name": f"Sequential Worker {i:02d}",
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
                "event_title": f"Sequential Research Batch #{i+1:02d}"
            }
            t0 = time.perf_counter()
            code, resp = http_request("POST", "/api/bookings", payload)
            elapsed = time.perf_counter() - t0
            latencies.append(round(elapsed * 1000, 2))
            statuses.append(code)
            if code == 201:
                created_ids.append(resp.get("id"))

        # Allow server thread to exit with conn: and commit
        time.sleep(0.1)

        # Direct DB audit
        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        db_count = conn.execute("""
            SELECT COUNT(*) FROM bookings 
            WHERE resource_id = ? AND user_id LIKE ? AND status = 'CONFIRMED'
        """, (resource_id, f"seq_user_{self.run_tag}_%")).fetchone()[0]
        conn.close()

        all_201 = all(s == 201 for s in statuses)
        passed = all_201 and (len(created_ids) == count) and (db_count == count)

        self.record_result(
            "High-Volume Rapid Sequential Bookings (20 slots)",
            passed,
            {
                "requested_slots": count,
                "success_201_count": len(created_ids),
                "db_persisted_count": db_count,
                "avg_latency_ms": round(sum(latencies) / len(latencies), 2),
                "max_latency_ms": max(latencies),
                "min_latency_ms": min(latencies),
                "non_201_statuses": [s for s in statuses if s != 201]
            }
        )
        return passed

    # =========================================================================
    # Scenario 3: Overlapping Boundaries & Edge Cases (1s, 1m, Abutting)
    # =========================================================================
    def test_boundary_and_subinterval_overlaps(self):
        print("\n--- Running Scenario 3: Boundary & Sub-interval Overlaps ---")
        resource_id = "conf-board"
        day_offset = self.base_date + timedelta(days=3)
        
        # Step 3.0: Seed anchor booking
        anchor_start = (day_offset.replace(hour=10, minute=0, second=0)).isoformat()
        anchor_end   = (day_offset.replace(hour=12, minute=0, second=0)).isoformat()
        anchor_payload = {
            "resource_id": resource_id,
            "user_id": f"anchor_{self.run_tag}",
            "user_name": "Anchor Chairman",
            "start_time": anchor_start,
            "end_time": anchor_end,
            "event_title": "Anchor Council Meeting"
        }
        code, resp = http_request("POST", "/api/bookings", anchor_payload)
        if code != 201:
            print(f"FAILED to seed anchor booking: HTTP {code}, {resp}")
            return False

        d = day_offset.strftime("%Y-%m-%d")

        subcases = [
            {
                "name": "1-Second Leading Overlap",
                "start": f"{d}T09:00:00",
                "end": f"{d}T10:00:01",
                "expected_code": 409,
                "desc": "Ends 1 second into the anchor window [10:00:00, 12:00:00)"
            },
            {
                "name": "1-Second Trailing Overlap",
                "start": f"{d}T11:59:59",
                "end": f"{d}T13:00:00",
                "expected_code": 409,
                "desc": "Starts 1 second before anchor window ends"
            },
            {
                "name": "1-Second Internal Slice Overlap",
                "start": f"{d}T10:30:00",
                "end": f"{d}T10:30:01",
                "expected_code": 409,
                "desc": "1-second sliver directly inside anchor window"
            },
            {
                "name": "1-Minute Leading Overlap",
                "start": f"{d}T09:30:00",
                "end": f"{d}T10:01:00",
                "expected_code": 409,
                "desc": "Ends 1 minute into anchor window"
            },
            {
                "name": "1-Minute Trailing Overlap",
                "start": f"{d}T11:59:00",
                "end": f"{d}T12:30:00",
                "expected_code": 409,
                "desc": "Starts 1 minute before anchor window ends"
            },
            {
                "name": "Exact Match Overlap",
                "start": f"{d}T10:00:00",
                "end": f"{d}T12:00:00",
                "expected_code": 409,
                "desc": "Identical start and end time"
            },
            {
                "name": "Enclosing Window Overlap",
                "start": f"{d}T09:00:00",
                "end": f"{d}T13:00:00",
                "expected_code": 409,
                "desc": "Completely encloses the anchor window"
            },
            {
                "name": "Enclosed Window Overlap",
                "start": f"{d}T10:30:00",
                "end": f"{d}T11:30:00",
                "expected_code": 409,
                "desc": "Completely enclosed inside the anchor window"
            },
            {
                "name": "Preceding Adjacent Boundary (Touching, NOT overlapping)",
                "start": f"{d}T08:00:00",
                "end": f"{d}T10:00:00",
                "expected_code": 201,
                "desc": "Abutting slot ending exactly at anchor start 10:00:00"
            },
            {
                "name": "Following Adjacent Boundary (Touching, NOT overlapping)",
                "start": f"{d}T12:00:00",
                "end": f"{d}T14:00:00",
                "expected_code": 201,
                "desc": "Abutting slot starting exactly at anchor end 12:00:00"
            }
        ]

        all_passed = True
        sub_details = {}

        for sc in subcases:
            payload = {
                "resource_id": resource_id,
                "user_id": f"edge_{self.run_tag}_{sc['name'].replace(' ', '_')[:8]}",
                "user_name": "Edge Case Tester",
                "start_time": sc["start"],
                "end_time": sc["end"],
                "event_title": f"Edge Test: {sc['name']}"
            }
            code, resp = http_request("POST", "/api/bookings", payload)
            ok = (code == sc["expected_code"])
            if not ok:
                all_passed = False
            sub_details[sc["name"]] = {
                "expected": sc["expected_code"],
                "actual": code,
                "passed": ok,
                "desc": sc["desc"],
                "response_error": resp.get("error") if code != 201 else None
            }

        self.record_result(
            "Overlapping Boundaries & Edge Cases (1s, 1m, abutting)",
            all_passed,
            sub_details
        )
        return all_passed

    # =========================================================================
    # Scenario 4: Concurrent Non-Overlapping Adjacent Bookings
    # =========================================================================
    def test_concurrent_non_overlapping_adjacent(self, num_threads: int = 10):
        print(f"\n--- Running Scenario 4: Concurrent Non-Overlapping Adjacent Slots ({num_threads} threads) ---")
        resource_id = "amphi-indoor"
        day_offset = self.base_date + timedelta(days=4)
        barrier = threading.Barrier(num_threads)
        thread_outcomes = []
        lock = threading.Lock()

        def worker(idx: int):
            slot_start = (day_offset + timedelta(hours=idx)).isoformat()
            slot_end = (day_offset + timedelta(hours=idx+1)).isoformat()
            payload = {
                "resource_id": resource_id,
                "user_id": f"adj_{self.run_tag}_{idx:02d}",
                "user_name": f"Adjacent Racer {idx:02d}",
                "start_time": slot_start,
                "end_time": slot_end,
                "event_title": f"Adjacent Slot #{idx:02d}"
            }
            try:
                barrier.wait(timeout=5.0)
            except threading.BrokenBarrierError:
                pass
            
            code, resp = http_request("POST", "/api/bookings", payload)
            with lock:
                thread_outcomes.append({"idx": idx, "code": code, "resp": resp})

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [o for o in thread_outcomes if o["code"] == 201]
        passed = (len(successes) == num_threads)

        self.record_result(
            "Concurrent Non-Overlapping Adjacent Slots (10 threads)",
            passed,
            {
                "threads": num_threads,
                "201_success_count": len(successes),
                "non_201_codes": [o["code"] for o in thread_outcomes if o["code"] != 201]
            }
        )
        return passed

    # =========================================================================
    # Scenario 5: Slot Cancellation & Concurrent Re-claiming
    # =========================================================================
    def test_cancellation_and_concurrent_reclaim(self, racers: int = 10):
        print(f"\n--- Running Scenario 5: Cancellation & Concurrent Re-claim ({racers} threads) ---")
        resource_id = "lab-robotics"
        day_offset = self.base_date + timedelta(days=5)
        slot_start = (day_offset.replace(hour=14, minute=0, second=0)).isoformat()
        slot_end   = (day_offset.replace(hour=16, minute=0, second=0)).isoformat()

        # Step 5.1: Create initial booking
        init_payload = {
            "resource_id": resource_id,
            "user_id": f"initial_holder_{self.run_tag}",
            "user_name": "Initial Slot Holder",
            "start_time": slot_start,
            "end_time": slot_end,
            "event_title": "Initial Lab Session"
        }
        code, resp = http_request("POST", "/api/bookings", init_payload)
        if code != 201:
            self.record_result("Cancellation Reclaim Pre-booking", False, {"code": code, "resp": resp})
            return False
        
        booking_id = resp["id"]

        # Step 5.2: Cancel booking
        code, resp = http_request("DELETE", f"/api/bookings/{booking_id}")
        if code != 200:
            self.record_result("Cancellation DELETE", False, {"code": code, "resp": resp})
            return False

        # Step 5.3: 10 threads race to reclaim the newly freed slot
        barrier = threading.Barrier(racers)
        reclaim_outcomes = []
        lock = threading.Lock()

        def reclaimer(idx: int):
            payload = {
                "resource_id": resource_id,
                "user_id": f"reclaimer_{self.run_tag}_{idx:02d}",
                "user_name": f"Reclaim Racer {idx:02d}",
                "start_time": slot_start,
                "end_time": slot_end,
                "event_title": f"Reclaim Attempt #{idx:02d}"
            }
            try:
                barrier.wait(timeout=5.0)
            except threading.BrokenBarrierError:
                pass
            
            c, r = http_request("POST", "/api/bookings", payload)
            with lock:
                reclaim_outcomes.append({"idx": idx, "code": c, "resp": r})

        threads = [threading.Thread(target=reclaimer, args=(i,)) for i in range(racers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [o for o in reclaim_outcomes if o["code"] == 201]
        conflicts = [o for o in reclaim_outcomes if o["code"] == 409]

        passed = (len(successes) == 1 and len(conflicts) == (racers - 1))

        self.record_result(
            "Cancellation & Concurrent Slot Re-claiming",
            passed,
            {
                "cancelled_booking_id": booking_id,
                "racers_competing": racers,
                "201_success_count": len(successes),
                "409_conflict_count": len(conflicts),
                "winning_reclaimer": successes[0]["resp"].get("user_id") if successes else None
            }
        )
        return passed

    # =========================================================================
    # Scenario 6: Database Direct Sanity & Integrity Check
    # =========================================================================
    def test_database_integrity_and_isolation(self):
        print("\n--- Running Scenario 6: SQLite Direct Integrity Audit ---")
        time.sleep(0.3)  # Brief grace period for connection pooling / wal flushing

        conn = None
        for attempt in range(5):
            try:
                conn = sqlite3.connect(DB_PATH, timeout=20.0)
                conn.row_factory = sqlite3.Row
                # 1. PRAGMA integrity_check
                integrity = conn.execute("PRAGMA integrity_check").fetchall()
                break
            except sqlite3.OperationalError:
                time.sleep(0.5)
        else:
            self.record_result("Direct Database Integrity & Sanity Audit", False, {"error": "Failed to connect to SQLite"})
            return False

        integrity_ok = len(integrity) == 1 and integrity[0][0] == "ok"

        # 2. PRAGMA foreign_key_check
        fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        fk_ok = (len(fk_violations) == 0)

        # 3. Check for any overlapping confirmed bookings across the entire database!
        overlap_violations = conn.execute("""
            SELECT b1.id as id1, b2.id as id2, b1.resource_id, b1.start_time, b1.end_time, b2.start_time, b2.end_time
            FROM bookings b1
            JOIN bookings b2 ON b1.resource_id = b2.resource_id 
                            AND b1.id < b2.id
                            AND b1.status = 'CONFIRMED' 
                            AND b2.status = 'CONFIRMED'
            WHERE b1.start_time < b2.end_time 
              AND b1.end_time > b2.start_time
        """).fetchall()
        no_overlaps = (len(overlap_violations) == 0)

        total_bookings = conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
        confirmed_bookings = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'CONFIRMED'").fetchone()[0]
        cancelled_bookings = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'CANCELLED'").fetchone()[0]
        conn.close()

        passed = integrity_ok and fk_ok and no_overlaps

        self.record_result(
            "Direct Database Integrity & Sanity Audit",
            passed,
            {
                "sqlite_integrity_check": integrity[0][0] if integrity else "EMPTY",
                "foreign_key_violations": len(fk_violations),
                "global_overlap_violations": len(overlap_violations),
                "total_bookings_in_db": total_bookings,
                "confirmed_bookings": confirmed_bookings,
                "cancelled_bookings": cancelled_bookings
            }
        )
        return passed

    # =========================================================================
    # Scenario 7: Extreme Race Condition (50 Threads)
    # =========================================================================
    def test_extreme_race_condition(self, num_threads: int = 50):
        print(f"\n--- Running Scenario 7: Extreme High-Concurrency Race ({num_threads} threads) ---")
        resource_id = "hall-b"
        day_offset = self.base_date + timedelta(days=6)
        slot_start = (day_offset.replace(hour=14, minute=0, second=0)).isoformat()
        slot_end   = (day_offset.replace(hour=16, minute=0, second=0)).isoformat()

        barrier = threading.Barrier(num_threads)
        thread_outcomes = []
        lock = threading.Lock()

        def worker(thread_idx: int):
            payload = {
                "resource_id": resource_id,
                "user_id": f"extreme_{self.run_tag}_{thread_idx:02d}",
                "user_name": f"Extreme Racer {thread_idx:02d}",
                "start_time": slot_start,
                "end_time": slot_end,
                "event_title": f"Extreme Race Thread {thread_idx:02d}"
            }
            try:
                barrier.wait(timeout=10.0)
            except threading.BrokenBarrierError:
                pass

            t0 = time.perf_counter()
            code, resp = http_request("POST", "/api/bookings", payload)
            elapsed = time.perf_counter() - t0

            with lock:
                thread_outcomes.append({
                    "thread_idx": thread_idx,
                    "code": code,
                    "resp": resp,
                    "latency_ms": round(elapsed * 1000, 2)
                })

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = [o for o in thread_outcomes if o["code"] == 201]
        conflicts = [o for o in thread_outcomes if o["code"] == 409]
        others = [o for o in thread_outcomes if o["code"] not in (201, 409)]

        conn = sqlite3.connect(DB_PATH, timeout=15.0)
        db_rows = conn.execute("""
            SELECT id, user_id FROM bookings 
            WHERE resource_id = ? AND status = 'CONFIRMED'
              AND (start_time < ? AND end_time > ?)
        """, (resource_id, slot_end, slot_start)).fetchall()
        conn.close()

        passed = (len(successes) == 1 and len(conflicts) == (num_threads - 1) and len(others) == 0 and len(db_rows) == 1)

        self.record_result(
            "Extreme High-Concurrency Race Condition (50 threads)",
            passed,
            {
                "threads_launched": num_threads,
                "201_success_count": len(successes),
                "409_conflict_count": len(conflicts),
                "unexpected_codes": [o["code"] for o in others],
                "db_confirmed_rows": len(db_rows),
                "winner": successes[0]["resp"].get("user_id") if successes else None
            }
        )
        return passed

    # =========================================================================
    # Scenario 8: Cross-Midnight and Year-Boundary Overlap Stress Test
    # =========================================================================
    def test_midnight_and_year_boundary(self):
        print("\n--- Running Scenario 8: Cross-Midnight & Year-Boundary Overlaps ---")
        resource_id = "conf-faculty"
        # Anchor booking spanning across New Year's Eve: 2040-12-31T23:00:00 to 2041-01-01T01:00:00 + offset
        year = 2040 + (self.run_tag % 10)
        anchor_start = f"{year}-12-31T23:00:00"
        anchor_end   = f"{year+1}-01-01T01:00:00"
        anchor_payload = {
            "resource_id": resource_id,
            "user_id": f"nye_{self.run_tag}",
            "user_name": "New Year Host",
            "start_time": anchor_start,
            "end_time": anchor_end,
            "event_title": "Faculty New Year Midnight Vigil"
        }
        code, resp = http_request("POST", "/api/bookings", anchor_payload)
        if code != 201:
            print(f"Failed to seed New Year anchor booking: {code}, {resp}")
            return False

        cases = [
            {
                "name": "Overlapping across midnight (23:30 to 00:30)",
                "start": f"{year}-12-31T23:30:00",
                "end": f"{year+1}-01-01T00:30:00",
                "expected": 409
            },
            {
                "name": "Overlapping before midnight (22:30 to 23:30)",
                "start": f"{year}-12-31T22:30:00",
                "end": f"{year}-12-31T23:30:00",
                "expected": 409
            },
            {
                "name": "Overlapping after midnight (00:30 to 01:30)",
                "start": f"{year+1}-01-01T00:30:00",
                "end": f"{year+1}-01-01T01:30:00",
                "expected": 409
            },
            {
                "name": "Preceding touching boundary before NYE (21:00 to 23:00)",
                "start": f"{year}-12-31T21:00:00",
                "end": f"{year}-12-31T23:00:00",
                "expected": 201
            },
            {
                "name": "Following touching boundary in New Year (01:00 to 03:00)",
                "start": f"{year+1}-01-01T01:00:00",
                "end": f"{year+1}-01-01T03:00:00",
                "expected": 201
            }
        ]

        all_ok = True
        case_results = {}
        for c in cases:
            payload = {
                "resource_id": resource_id,
                "user_id": f"nye_test_{self.run_tag}",
                "user_name": "NYE Tester",
                "start_time": c["start"],
                "end_time": c["end"],
                "event_title": f"NYE Test: {c['name']}"
            }
            res_code, res_resp = http_request("POST", "/api/bookings", payload)
            ok = (res_code == c["expected"])
            if not ok:
                all_ok = False
            case_results[c["name"]] = {
                "expected": c["expected"],
                "actual": res_code,
                "passed": ok
            }

        self.record_result(
            "Cross-Midnight and Year-Boundary Overlap Stress",
            all_ok,
            case_results
        )
        return all_ok

    # =========================================================================
    # Scenario 9: Adversarial Malformed & Pathological Input Attacks
    # =========================================================================
    def test_pathological_input_attacks(self):
        print("\n--- Running Scenario 9: Adversarial Malformed & Pathological Input Attacks ---")
        attack_cases = [
            {
                "name": "Inverted Time Window (start > end)",
                "method": "POST",
                "path": "/api/bookings",
                "data": {
                    "resource_id": "class-101",
                    "user_id": f"bad_{self.run_tag}",
                    "user_name": "Bad Actor",
                    "start_time": "2039-10-01T15:00:00",
                    "end_time": "2039-10-01T12:00:00",
                    "event_title": "Time Traveler Meeting"
                },
                "expected": 400
            },
            {
                "name": "Zero Duration Booking (start == end)",
                "method": "POST",
                "path": "/api/bookings",
                "data": {
                    "resource_id": "class-101",
                    "user_id": f"bad_{self.run_tag}",
                    "user_name": "Bad Actor",
                    "start_time": "2039-10-01T12:00:00",
                    "end_time": "2039-10-01T12:00:00",
                    "event_title": "Zero Duration Flash"
                },
                "expected": 400
            },
            {
                "name": "Unparseable Datetime String",
                "method": "POST",
                "path": "/api/bookings",
                "data": {
                    "resource_id": "class-101",
                    "user_id": f"bad_{self.run_tag}",
                    "user_name": "Bad Actor",
                    "start_time": "not-a-datetime",
                    "end_time": "2039-10-01T14:00:00",
                    "event_title": "Garbage Datetime Test"
                },
                "expected": 400
            },
            {
                "name": "Non-Existent Resource ID",
                "method": "POST",
                "path": "/api/bookings",
                "data": {
                    "resource_id": "phantom-hall-999",
                    "user_id": f"bad_{self.run_tag}",
                    "user_name": "Bad Actor",
                    "start_time": "2039-10-01T12:00:00",
                    "end_time": "2039-10-01T14:00:00",
                    "event_title": "Phantom Hall Booking"
                },
                "expected": 404
            },
            {
                "name": "Missing Required Field (missing event_title)",
                "method": "POST",
                "path": "/api/bookings",
                "data": {
                    "resource_id": "class-101",
                    "user_id": f"bad_{self.run_tag}",
                    "user_name": "Bad Actor",
                    "start_time": "2039-10-01T12:00:00",
                    "end_time": "2039-10-01T14:00:00"
                },
                "expected": 400
            },
            {
                "name": "Whitespace-only User ID",
                "method": "POST",
                "path": "/api/bookings",
                "data": {
                    "resource_id": "class-101",
                    "user_id": "   ",
                    "user_name": "Ghost",
                    "start_time": "2039-10-01T12:00:00",
                    "end_time": "2039-10-01T14:00:00",
                    "event_title": "Empty User Space"
                },
                "expected": 400
            },
            {
                "name": "DELETE Non-existent Booking ID",
                "method": "DELETE",
                "path": "/api/bookings/bkg_does_not_exist_9999",
                "data": None,
                "expected": 404
            }
        ]

        all_passed = True
        attack_results = {}
        for ac in attack_cases:
            code, resp = http_request(ac["method"], ac["path"], ac["data"])
            ok = (code == ac["expected"])
            if not ok:
                all_passed = False
            attack_results[ac["name"]] = {
                "expected": ac["expected"],
                "actual": code,
                "passed": ok,
                "error_message": resp.get("message")
            }

        self.record_result(
            "Adversarial Pathological Input Attacks",
            all_passed,
            attack_results
        )
        return all_passed

    def run_all(self):
        print(f"================================================================")
        print(f"   STARTING EMPIRICAL ADVERSARIAL STRESS TEST SUITE")
        print(f"   Target: {BASE_URL}")
        print(f"   Database: {DB_PATH}")
        print(f"   Run Tag: {self.run_tag}")
        print(f"   Base Date: {self.base_date.isoformat()}")
        print(f"================================================================")

        t_start = time.perf_counter()
        
        s1 = self.test_simultaneous_race_condition(20)
        s2 = self.test_rapid_sequential_bookings(20)
        s3 = self.test_boundary_and_subinterval_overlaps()
        s4 = self.test_concurrent_non_overlapping_adjacent(10)
        s5 = self.test_cancellation_and_concurrent_reclaim(10)
        s7 = self.test_extreme_race_condition(50)
        s8 = self.test_midnight_and_year_boundary()
        s9 = self.test_pathological_input_attacks()
        s6 = self.test_database_integrity_and_isolation()

        t_total = time.perf_counter() - t_start

        print(f"\n================================================================")
        print(f"   SUMMARY OF RESULTS")
        print(f"   Total Execution Time: {t_total:.2f}s")
        print(f"   Total Scenarios: {len(self.results)}")
        print(f"   Passed: {sum(1 for r in self.results.values() if r['passed'])}")
        print(f"   Failed: {len(self.failures)}")
        print(f"================================================================")

        if self.failures:
            print("\nFAILURES DETECTED:")
            for name, details in self.failures:
                print(f" - {name}: {details}")
            return 1
        else:
            print("\nALL ADVERSARIAL STRESS TESTS PASSED EMPIRICALLY.")
            return 0


if __name__ == "__main__":
    suite = StressTestSuite()
    code = suite.run_all()
    sys.exit(code)
