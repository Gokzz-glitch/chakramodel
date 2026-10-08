#!/usr/bin/env python3
"""
Academic Event & Resource Booking Portal - Automated Verification Suite
========================================================================
Standalone acceptance and conflict-prevention test runner.
Pure Python standard library (no pip dependencies required).

Acceptance Criteria Verified:
- [x] Fetch and list available resources (R1)
- [x] Create a new booking for specific resource and time slot (R2 & R3)
- [x] Attempt duplicate slot booking -> Assert 409 Conflict rejection (R2)
- [x] Edge-case overlap variations (starts before, ends after, enclosing, enclosed)
- [x] Boundary conditions (adjacent back-to-back slots allowed)
- [x] Resource isolation (different resource at same time allowed)
- [x] Validation (inverted time window, missing user identity)
- [x] Query & filtering endpoints (/api/bookings)

Usage:
  python test_booking.py
  python test_booking.py --url http://127.0.0.1:8000
"""

import sys
import os
import json
import time
import argparse
from datetime import datetime, timedelta
import urllib.request
import urllib.error

# ANSI Color Codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class PortalTestClient:
    """HTTP Client wrapper using urllib.request with JSON decoding."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, data: dict = None) -> tuple[int, dict, dict]:
        """
        Executes HTTP request.
        Returns: (status_code, response_json, response_headers)
        """
        url = f"{self.base_url}{path}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "AcademicPortal-VerificationSuite/1.0"
        }
        encoded_data = None

        if data is not None:
            encoded_data = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                headers_dict = dict(resp.headers)
                try:
                    json_data = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    json_data = {"raw": body}
                return status, json_data, headers_dict
        except urllib.error.HTTPError as err:
            status = err.code
            body = err.read().decode("utf-8")
            headers_dict = dict(err.headers)
            try:
                json_data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                json_data = {"raw": body}
            return status, json_data, headers_dict
        except urllib.error.URLError as err:
            raise ConnectionError(f"Failed to connect to portal at {url}: {err.reason}")


class TestRunner:
    """Executes test cases, records outcomes, and prints colored reports."""

    def __init__(self, base_url: str):
        self.client = PortalTestClient(base_url)
        self.base_url = base_url
        self.passed = 0
        self.failed = 0
        self.test_log = []

    def assert_true(self, condition: bool, message: str):
        if not condition:
            raise AssertionError(message)

    def assert_equal(self, actual, expected, message: str = ""):
        if actual != expected:
            raise AssertionError(f"{message} (Expected: {expected!r}, Got: {actual!r})")

    def run_test(self, test_num: int, title: str, test_fn):
        """Executes an individual test function and reports status."""
        start_time = time.time()
        print(f"[{test_num:02d}] {BOLD}{title}{RESET} ... ", end="", flush=True)
        try:
            test_fn()
            duration_ms = (time.time() - start_time) * 1000
            print(f"{GREEN}PASS{RESET} ({duration_ms:.1f}ms)")
            self.passed += 1
            self.test_log.append((test_num, title, True, None))
        except AssertionError as err:
            duration_ms = (time.time() - start_time) * 1000
            print(f"{RED}FAIL{RESET} ({duration_ms:.1f}ms)")
            print(f"     {RED}AssertionError: {err}{RESET}")
            self.failed += 1
            self.test_log.append((test_num, title, False, str(err)))
        except Exception as err:
            duration_ms = (time.time() - start_time) * 1000
            print(f"{RED}ERROR{RESET} ({duration_ms:.1f}ms)")
            print(f"     {RED}{type(err).__name__}: {err}{RESET}")
            self.failed += 1
            self.test_log.append((test_num, title, False, f"{type(err).__name__}: {err}"))

    def execute_all(self):
        print("\n" + "=" * 75)
        print(f"{BOLD}{CYAN}Academic Event & Resource Booking Portal - Verification Suite{RESET}")
        print(f"Target Server URL: {BOLD}{self.base_url}{RESET}")
        print(f"Execution Time:    {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 75 + "\n")

        # Unique timestamp base to prevent clashes across runs
        run_ts = int(time.time())
        test_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

        shared_state = {
            "resources": [],
            "target_resource_id": None,
            "alt_resource_id": None,
            "base_booking_id": None,
            "slot_start": f"{test_date}T10:00:00",
            "slot_end": f"{test_date}T12:00:00",
        }

        # -------------------------------------------------------------
        # Test 1: Server Reachability & Health
        # -------------------------------------------------------------
        def test_1_server_reachability():
            status, data, _ = self.client.request("GET", "/api/resources")
            self.assert_equal(status, 200, "Server must respond with HTTP 200 on /api/resources")

        self.run_test(1, "Server Reachability (/api/resources responds 200)", test_1_server_reachability)

        # -------------------------------------------------------------
        # Test 2: R1 - Resource Listing & Schema Validation
        # -------------------------------------------------------------
        def test_2_resource_listing():
            status, resources, _ = self.client.request("GET", "/api/resources")
            self.assert_equal(status, 200, "Expected HTTP 200 OK")
            self.assert_true(isinstance(resources, list), "Response must be a JSON array")
            self.assert_true(len(resources) >= 3, f"Expected at least 3 seeded resources, got {len(resources)}")

            # Validate each resource item schema
            required_keys = {"id", "name", "type", "capacity", "location"}
            types_found = set()

            for res in resources:
                missing = required_keys - set(res.keys())
                self.assert_true(len(missing) == 0, f"Resource {res.get('id')} missing required fields: {missing}")
                self.assert_true(isinstance(res["capacity"], int) and res["capacity"] > 0, "Capacity must be a positive integer")
                types_found.add(res["type"])

            # Verify resource types include institutional taxonomy
            for expected_type in ["seminar_hall", "lab", "classroom"]:
                self.assert_true(expected_type in types_found, f"Resource type taxonomy missing: {expected_type}")

            shared_state["resources"] = resources
            shared_state["target_resource_id"] = resources[0]["id"]
            # Find an alternative resource of different ID for isolation test
            for r in resources:
                if r["id"] != shared_state["target_resource_id"]:
                    shared_state["alt_resource_id"] = r["id"]
                    break

        self.run_test(2, "R1: Resource Listing & Institutional Schema Validation", test_2_resource_listing)

        # -------------------------------------------------------------
        # Test 3: R2 & R3 - Create Valid Booking
        # -------------------------------------------------------------
        def test_3_create_booking():
            payload = {
                "resource_id": shared_state["target_resource_id"],
                "user_id": f"prof_tester_{run_ts}",
                "user_name": "Prof. Alan Turing",
                "start_time": shared_state["slot_start"],
                "end_time": shared_state["slot_end"],
                "event_title": "Colloquium on Computational Foundations"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", payload)
            self.assert_equal(status, 201, f"Expected 201 Created for valid booking, got {status}: {data}")
            self.assert_true("id" in data, "Created booking must return a booking ID")
            self.assert_equal(data["resource_id"], payload["resource_id"], "Booking resource_id must match")
            self.assert_equal(data["user_id"], payload["user_id"], "Booking user_id must match")
            self.assert_equal(data["start_time"], payload["start_time"], "Booking start_time must match")
            self.assert_equal(data["end_time"], payload["end_time"], "Booking end_time must match")

            shared_state["base_booking_id"] = data["id"]

        self.run_test(3, "R2 & R3: Create Valid Initial Reservation (201 Created)", test_3_create_booking)

        # -------------------------------------------------------------
        # Test 4: R2 Acceptance Criteria - Exact Duplicate Slot Rejection
        # -------------------------------------------------------------
        def test_4_exact_conflict_rejection():
            conflict_payload = {
                "resource_id": shared_state["target_resource_id"],
                "user_id": f"student_lead_{run_ts}",
                "user_name": "Ada Lovelace",
                "start_time": shared_state["slot_start"],
                "end_time": shared_state["slot_end"],
                "event_title": "Conflicting Robotics Session"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", conflict_payload)
            self.assert_equal(status, 409, f"Expected 409 Conflict for duplicate slot booking, got {status}: {data}")
            # Ensure error response explains the conflict
            has_error_message = ("error" in data) or ("message" in data) or ("conflict" in str(data).lower())
            self.assert_true(has_error_message, "Conflict response should contain informative error message")

        self.run_test(4, "R2: Exact Duplicate Slot Rejection (409 Conflict)", test_4_exact_conflict_rejection)

        # -------------------------------------------------------------
        # Test 5: Overlap Case A - Starts Before, Ends Inside Slot
        # -------------------------------------------------------------
        def test_5_overlap_starts_before_ends_inside():
            payload = {
                "resource_id": shared_state["target_resource_id"],
                "user_id": f"guest_fac_{run_ts}",
                "user_name": "Dr. Claude Shannon",
                "start_time": f"{test_date}T09:00:00",
                "end_time": f"{test_date}T11:00:00",  # Overlaps 10:00 - 11:00
                "event_title": "Information Theory Seminar"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", payload)
            self.assert_equal(status, 409, f"Expected 409 Conflict for overlap (09:00-11:00), got {status}: {data}")

        self.run_test(5, "Conflict Edge Case: Starts Before & Ends Inside (09:00-11:00)", test_5_overlap_starts_before_ends_inside)

        # -------------------------------------------------------------
        # Test 6: Overlap Case B - Starts Inside, Ends After Slot
        # -------------------------------------------------------------
        def test_6_overlap_starts_inside_ends_after():
            payload = {
                "resource_id": shared_state["target_resource_id"],
                "user_id": f"researcher_{run_ts}",
                "user_name": "Dr. Grace Hopper",
                "start_time": f"{test_date}T11:00:00",  # Overlaps 11:00 - 12:00
                "end_time": f"{test_date}T13:00:00",
                "event_title": "Compiler Architecture Panel"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", payload)
            self.assert_equal(status, 409, f"Expected 409 Conflict for overlap (11:00-13:00), got {status}: {data}")

        self.run_test(6, "Conflict Edge Case: Starts Inside & Ends After (11:00-13:00)", test_6_overlap_starts_inside_ends_after)

        # -------------------------------------------------------------
        # Test 7: Overlap Case C - Fully Enclosing Slot
        # -------------------------------------------------------------
        def test_7_overlap_fully_enclosing():
            payload = {
                "resource_id": shared_state["target_resource_id"],
                "user_id": f"dean_{run_ts}",
                "user_name": "Dean John von Neumann",
                "start_time": f"{test_date}T08:00:00",
                "end_time": f"{test_date}T14:00:00",  # Completely encloses 10:00-12:00
                "event_title": "All-Day Academic Symposium"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", payload)
            self.assert_equal(status, 409, f"Expected 409 Conflict for enclosing slot (08:00-14:00), got {status}: {data}")

        self.run_test(7, "Conflict Edge Case: Fully Enclosing Existing Slot (08:00-14:00)", test_7_overlap_fully_enclosing)

        # -------------------------------------------------------------
        # Test 8: Overlap Case D - Fully Enclosed Within Slot
        # -------------------------------------------------------------
        def test_8_overlap_fully_enclosed():
            payload = {
                "resource_id": shared_state["target_resource_id"],
                "user_id": f"ta_{run_ts}",
                "user_name": "TA Margaret Hamilton",
                "start_time": f"{test_date}T10:30:00",
                "end_time": f"{test_date}T11:30:00",  # Completely inside 10:00-12:00
                "event_title": "Short Quiz Slot"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", payload)
            self.assert_equal(status, 409, f"Expected 409 Conflict for enclosed slot (10:30-11:30), got {status}: {data}")

        self.run_test(8, "Conflict Edge Case: Fully Enclosed Inside Slot (10:30-11:30)", test_8_overlap_fully_enclosed)

        # -------------------------------------------------------------
        # Test 9: Boundary Condition - Adjacent Back-to-Back Slots Allowed
        # -------------------------------------------------------------
        def test_9_adjacent_slots_allowed():
            # Slot A: Immediately before (08:00 to 10:00) -> End matches existing start
            payload_before = {
                "resource_id": shared_state["target_resource_id"],
                "user_id": f"early_prof_{run_ts}",
                "user_name": "Prof. Donald Knuth",
                "start_time": f"{test_date}T08:00:00",
                "end_time": f"{test_date}T10:00:00",
                "event_title": "Early Morning Algorithms"
            }
            status_before, data_before, _ = self.client.request("POST", "/api/bookings", payload_before)
            self.assert_equal(status_before, 201, f"Adjacent prior slot (08:00-10:00) must be accepted, got {status_before}: {data_before}")

            # Slot B: Immediately after (12:00 to 14:00) -> Start matches existing end
            payload_after = {
                "resource_id": shared_state["target_resource_id"],
                "user_id": f"afternoon_prof_{run_ts}",
                "user_name": "Prof. Edsger Dijkstra",
                "start_time": f"{test_date}T12:00:00",
                "end_time": f"{test_date}T14:00:00",
                "event_title": "Afternoon Formal Verification"
            }
            status_after, data_after, _ = self.client.request("POST", "/api/bookings", payload_after)
            self.assert_equal(status_after, 201, f"Adjacent subsequent slot (12:00-14:00) must be accepted, got {status_after}: {data_after}")

        self.run_test(9, "Boundary Condition: Adjacent Back-to-Back Slots Allowed (201 Created)", test_9_adjacent_slots_allowed)

        # -------------------------------------------------------------
        # Test 10: Resource Isolation - Different Resource at Same Time Allowed
        # -------------------------------------------------------------
        def test_10_different_resource_isolation():
            alt_res = shared_state["alt_resource_id"]
            self.assert_true(alt_res is not None, "Alternative resource required for isolation test")

            payload = {
                "resource_id": alt_res,
                "user_id": f"concurrent_prof_{run_ts}",
                "user_name": "Prof. Tim Berners-Lee",
                "start_time": shared_state["slot_start"],  # Same time as Test 3
                "end_time": shared_state["slot_end"],
                "event_title": "Web Architecture Lab"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", payload)
            self.assert_equal(status, 201, f"Concurrent booking for different resource must succeed, got {status}: {data}")

        self.run_test(10, "Resource Isolation: Concurrent Booking on Different Resource Allowed", test_10_different_resource_isolation)

        # -------------------------------------------------------------
        # Test 11: Validation - Inverted Time Window (End <= Start)
        # -------------------------------------------------------------
        def test_11_invalid_time_window():
            payload = {
                "resource_id": shared_state["target_resource_id"],
                "user_id": f"invalid_user_{run_ts}",
                "user_name": "Inversion Tester",
                "start_time": f"{test_date}T16:00:00",
                "end_time": f"{test_date}T15:00:00",  # End time before start time
                "event_title": "Impossible Time Machine Event"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", payload)
            self.assert_equal(status, 400, f"Inverted time window must return 400 Bad Request, got {status}: {data}")

        self.run_test(11, "Validation: Inverted Time Window (end <= start) Rejected (400)", test_11_invalid_time_window)

        # -------------------------------------------------------------
        # Test 12: Validation - Missing Required Identity Fields (R3)
        # -------------------------------------------------------------
        def test_12_missing_identity():
            payload = {
                "resource_id": shared_state["target_resource_id"],
                # Missing user_id and user_name
                "start_time": f"{test_date}T16:00:00",
                "end_time": f"{test_date}T17:00:00",
                "event_title": "Anonymous Event"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", payload)
            self.assert_equal(status, 400, f"Missing user identity must return 400 Bad Request, got {status}: {data}")

        self.run_test(12, "Validation: Missing User Identity Fields Rejected (400)", test_12_missing_identity)

        # -------------------------------------------------------------
        # Test 13: Query API - List & Filter Bookings
        # -------------------------------------------------------------
        def test_13_query_bookings():
            # List all bookings
            status, all_bookings, _ = self.client.request("GET", "/api/bookings")
            self.assert_equal(status, 200, "GET /api/bookings must return 200 OK")
            self.assert_true(isinstance(all_bookings, list), "Bookings must be a list")

            # Verify base booking is present
            found = any(b.get("id") == shared_state["base_booking_id"] for b in all_bookings)
            self.assert_true(found, f"Created booking {shared_state['base_booking_id']} not found in GET /api/bookings")

            # Filter by resource_id
            target_id = shared_state["target_resource_id"]
            status, filtered_bookings, _ = self.client.request("GET", f"/api/bookings?resource_id={target_id}")
            self.assert_equal(status, 200, f"GET /api/bookings?resource_id={target_id} must return 200 OK")
            for b in filtered_bookings:
                self.assert_equal(b.get("resource_id"), target_id, "Filtered bookings must all match queried resource_id")

        self.run_test(13, "Query API: Active Bookings Listing & Resource Filtering", test_13_query_bookings)

        # -------------------------------------------------------------
        # Test 14: Validation - Non-Existent Resource ID
        # -------------------------------------------------------------
        def test_14_nonexistent_resource():
            payload = {
                "resource_id": "nonexistent-hall-xyz-999",
                "user_id": f"user_{run_ts}",
                "user_name": "Ghost User",
                "start_time": f"{test_date}T18:00:00",
                "end_time": f"{test_date}T19:00:00",
                "event_title": "Phantom Lecture"
            }
            status, data, _ = self.client.request("POST", "/api/bookings", payload)
            self.assert_true(status in (404, 400), f"Non-existent resource must return 404 or 400, got {status}: {data}")

        self.run_test(14, "Validation: Non-Existent Resource ID Rejected (400/404)", test_14_nonexistent_resource)

        # -------------------------------------------------------------
        # Report Summary
        # -------------------------------------------------------------
        total = self.passed + self.failed
        success_pct = (self.passed / total * 100) if total > 0 else 0

        print("\n" + "=" * 75)
        print(f"{BOLD}VERIFICATION SUMMARY:{RESET}")
        print(f"Total Tests Executed: {total}")
        print(f"Passed:               {GREEN}{self.passed}{RESET}")
        print(f"Failed:               {RED if self.failed > 0 else GREEN}{self.failed}{RESET}")
        print(f"Success Rate:         {GREEN if self.failed == 0 else RED}{success_pct:.1f}%{RESET}")

        if self.failed == 0:
            print("\n" + f"{GREEN}{BOLD}ALL ACCEPTANCE CRITERIA SATISFIED (R1, R2, R3).{RESET}")
            print(f"{GREEN}Ready for Sentinel Verification & Forensic Audit.{RESET}")
            print("=" * 75 + "\n")
            return 0
        else:
            print("\n" + f"{RED}{BOLD}VERIFICATION FAILED: {self.failed} test(s) did not pass.{RESET}")
            print("=" * 75 + "\n")
            return 1


def resolve_default_url() -> str:
    """Resolves target URL via PORTAL_URL env, .server_port file, or default 8000."""
    if "PORTAL_URL" in os.environ:
        return os.environ["PORTAL_URL"]

    # Search for .server_port in current dir and parent directories
    search_dirs = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
    parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    search_dirs.append(parent)

    for directory in search_dirs:
        port_file = os.path.join(directory, ".server_port")
        if os.path.isfile(port_file):
            try:
                with open(port_file, "r", encoding="utf-8") as f:
                    port = f.read().strip()
                    if port.isdigit():
                        return f"http://127.0.0.1:{port}"
            except Exception:
                pass

    return "http://127.0.0.1:8000"


def main():
    parser = argparse.ArgumentParser(description="Academic Event & Resource Booking Portal - Verification Suite")
    default_url = resolve_default_url()
    parser.add_argument("--url", default=default_url, help=f"Base URL of running portal (default: {default_url})")
    args = parser.parse_args()

    runner = TestRunner(args.url)
    try:
        exit_code = runner.execute_all()
        sys.exit(exit_code)
    except ConnectionError as err:
        print(f"\n{RED}{BOLD}FATAL: Connection Error{RESET}")
        print(f"{RED}{err}{RESET}")
        print(f"\n{YELLOW}Please ensure the backend server is running before executing this suite.{RESET}")
        print(f"Example: python server.py\n")
        sys.exit(2)
    except KeyboardInterrupt:
        print("\n\nTest execution aborted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
