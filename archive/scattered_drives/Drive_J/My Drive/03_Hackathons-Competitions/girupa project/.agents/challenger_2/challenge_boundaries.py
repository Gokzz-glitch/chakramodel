#!/usr/bin/env python3
"""
Adversarial Boundary & Edge-Case Challenge Suite
Challenger 2 (teamwork_preview_challenger)
Target: Academic Event & Resource Booking Portal (http://127.0.0.1:8000)
"""

import sys
import os
import json
import time
import socket
import concurrent.futures
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


class EmpiricalChallengeRunner:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.results = []
        self.passed_count = 0
        self.failed_count = 0
        self.vulnerabilities = []

    def request(self, method: str, path: str, data=None, raw_body: bytes = None, headers: dict = None) -> tuple[int, dict, dict, str]:
        """
        Executes HTTP request with full diagnostic capture.
        Returns: (status_code, json_body_or_empty, headers_dict, raw_body_str)
        """
        url = f"{self.base_url}{path}"
        req_headers = {
            "Accept": "application/json",
            "User-Agent": "Challenger2-AdversarialSuite/1.0"
        }
        if headers:
            req_headers.update(headers)

        payload_bytes = None
        if raw_body is not None:
            payload_bytes = raw_body
        elif data is not None:
            payload_bytes = json.dumps(data).encode("utf-8")
            if "Content-Type" not in req_headers:
                req_headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=payload_bytes, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                body_bytes = resp.read()
                body_str = body_bytes.decode("utf-8", errors="replace")
                headers_dict = dict(resp.headers)
                try:
                    json_data = json.loads(body_str) if body_str else {}
                except json.JSONDecodeError:
                    json_data = {}
                return status, json_data, headers_dict, body_str
        except urllib.error.HTTPError as err:
            status = err.code
            body_bytes = err.read()
            body_str = body_bytes.decode("utf-8", errors="replace")
            headers_dict = dict(err.headers)
            try:
                json_data = json.loads(body_str) if body_str else {}
            except json.JSONDecodeError:
                json_data = {}
            return status, json_data, headers_dict, body_str
        except (urllib.error.URLError, ConnectionResetError, Exception) as err:
            # Captures unhandled server worker crashes (e.g. RemoteDisconnected)
            return 500, {"error": "ServerAbortedConnection", "details": str(err)}, {}, f"CRASH_OR_ABORT: {type(err).__name__}: {str(err)}"

    def record_test(self, suite: str, test_id: str, title: str, passed: bool, details: dict):
        status_text = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"[{suite}] [{test_id}] {title} ... {status_text}")
        if not passed:
            print(f"       {YELLOW}Observation: {details.get('observation')}{RESET}")
            print(f"       {YELLOW}Expected:    {details.get('expected')}{RESET}")
            print(f"       {YELLOW}Actual:      {details.get('actual')}{RESET}")
            self.vulnerabilities.append({
                "suite": suite,
                "test_id": test_id,
                "title": title,
                "details": details
            })
            self.failed_count += 1
        else:
            self.passed_count += 1

        self.results.append({
            "suite": suite,
            "test_id": test_id,
            "title": title,
            "passed": passed,
            "details": details
        })

    def run_all(self):
        print("\n" + "=" * 80)
        print(f"{BOLD}{CYAN}Adversarial Boundary & Edge-Case Challenge Suite{RESET}")
        print(f"Target Server: {BOLD}{self.base_url}{RESET}")
        print(f"Timestamp:     {datetime.now().isoformat()}")
        print("=" * 80 + "\n")

        # 1. Fetch catalog to obtain active resource
        status, resources, _, _ = self.request("GET", "/api/resources")
        if status != 200 or not resources:
            print(f"{RED}FATAL: Could not fetch resources from {self.base_url}{RESET}")
            sys.exit(1)

        res_id = resources[0]["id"]
        alt_res_id = resources[1]["id"] if len(resources) > 1 else resources[0]["id"]
        print(f"Using Primary Target Resource: {BOLD}{res_id}{RESET}")
        print(f"Using Secondary Resource:      {BOLD}{alt_res_id}{RESET}\n")

        # Base timestamp using run_id and high future year to avoid collision with any existing DB rows
        base_future_year = 2060 + (int(time.time()) % 20)
        run_id = int(time.time() * 1000) % 1000000

        # =========================================================================
        # SUITE A: Date-Time Format & Temporal Boundary Stress Tests
        # =========================================================================
        print(f"{BOLD}--- SUITE A: Date-Time Format & Temporal Boundary Stress Tests ---{RESET}")

        # A1: Malformed date-time strings (Random garbage string)
        payload = {
            "resource_id": res_id,
            "user_id": f"u_a1_{run_id}",
            "user_name": "Garbage Date Tester",
            "start_time": "invalid-garbage-date-time-string",
            "end_time": f"{base_future_year}-01-01T12:00:00",
            "event_title": "Garbage Date Event"
        }
        st, data, _, body = self.request("POST", "/api/bookings", payload)
        passed = (st == 400 and data.get("error") == "BadRequest")
        self.record_test("SuiteA", "A1.1", "Malformed date-time: Random garbage string rejected with 400", passed, {
            "payload": payload,
            "expected": "HTTP 400 with BadRequest",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # A1.2: Invalid calendar date (Feb 30th)
        payload = {
            "resource_id": res_id,
            "user_id": f"u_a12_{run_id}",
            "user_name": "Calendar Date Tester",
            "start_time": f"{base_future_year}-02-30T10:00:00",
            "end_time": f"{base_future_year}-02-30T12:00:00",
            "event_title": "Impossible Date Event"
        }
        st, data, _, body = self.request("POST", "/api/bookings", payload)
        passed = (st == 400 and data.get("error") == "BadRequest")
        self.record_test("SuiteA", "A1.2", "Malformed date-time: Impossible calendar date (Feb 30) rejected with 400", passed, {
            "payload": payload,
            "expected": "HTTP 400 with BadRequest",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # A2: Zero duration booking (start_time == end_time)
        zero_slot = f"{base_future_year}-03-10T14:00:00"
        payload = {
            "resource_id": res_id,
            "user_id": f"u_a2_{run_id}",
            "user_name": "Zero Duration Tester",
            "start_time": zero_slot,
            "end_time": zero_slot,
            "event_title": "Zero Duration Singularity"
        }
        st, data, _, body = self.request("POST", "/api/bookings", payload)
        passed = (st == 400 and "earlier" in data.get("message", "").lower())
        self.record_test("SuiteA", "A2", "Zero duration interval (start_time == end_time) strictly rejected with 400", passed, {
            "payload": payload,
            "expected": "HTTP 400 with start_time must be strictly earlier than end_time",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # A3: Inverted time range (start_time > end_time)
        payload = {
            "resource_id": res_id,
            "user_id": f"u_a3_{run_id}",
            "user_name": "Time Reversal Tester",
            "start_time": f"{base_future_year}-03-10T15:00:00",
            "end_time": f"{base_future_year}-03-10T14:00:00",
            "event_title": "Back to the Future Seminar"
        }
        st, data, _, body = self.request("POST", "/api/bookings", payload)
        passed = (st == 400 and "earlier" in data.get("message", "").lower())
        self.record_test("SuiteA", "A3", "Inverted time range (start_time > end_time) rejected with 400", passed, {
            "payload": payload,
            "expected": "HTTP 400 with start_time must be strictly earlier than end_time",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # A4: Negative year ("-0001-01-01T10:00:00")
        payload = {
            "resource_id": res_id,
            "user_id": f"u_a4_{run_id}",
            "user_name": "Antiquity Tester",
            "start_time": "-0001-01-01T10:00:00",
            "end_time": "-0001-01-01T12:00:00",
            "event_title": "Ancient Philosophy Symposium"
        }
        st, data, _, body = self.request("POST", "/api/bookings", payload)
        passed = (st == 400)
        self.record_test("SuiteA", "A4", "Negative year (-0001) datetime rejected with 400", passed, {
            "payload": payload,
            "expected": "HTTP 400 (unsupported or invalid datetime)",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # A5: Out-of-bounds year (Year 10000)
        payload = {
            "resource_id": res_id,
            "user_id": f"u_a5_{run_id}",
            "user_name": "Distant Future Tester",
            "start_time": "10000-01-01T10:00:00",
            "end_time": "10000-01-01T12:00:00",
            "event_title": "Milky Way Colonization"
        }
        st, data, _, body = self.request("POST", "/api/bookings", payload)
        passed = (st == 400)
        self.record_test("SuiteA", "A5", "Out-of-bounds year (10000+) rejected with 400", passed, {
            "payload": payload,
            "expected": "HTTP 400 (year exceeds 9999 limit)",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # A6.1: Timezone-aware ISO with UTC 'Z'
        payload_tz = {
            "resource_id": res_id,
            "user_id": f"u_a6_{run_id}",
            "user_name": "UTC Tester",
            "start_time": f"{base_future_year}-04-01T10:00:00Z",
            "end_time": f"{base_future_year}-04-01T12:00:00Z",
            "event_title": "UTC Timezone Colloquium"
        }
        st_tz, data_tz, _, body_tz = self.request("POST", "/api/bookings", payload_tz)
        booking_tz_id = data_tz.get("id")
        passed_tz = (st_tz in (201, 400))
        self.record_test("SuiteA", "A6.1", "Timezone ISO (with 'Z' suffix): check response status", passed_tz, {
            "payload": payload_tz,
            "expected": "HTTP 201 (if supported) or HTTP 400 (if strict naive format required)",
            "actual": f"HTTP {st_tz} -> {body_tz}",
            "observation": f"Server responded {st_tz}, booking ID: {booking_tz_id}"
        })

        # A6.2: Timezone representation conflict bypass test
        # When a slot is booked as UTC 'Z', test whether an equivalent slot with offset +05:30 is detected as conflict
        if st_tz == 201 and booking_tz_id:
            payload_tz_offset = {
                "resource_id": res_id,
                "user_id": f"u_a6_offset_{run_id}",
                "user_name": "Offset Overlap Tester",
                "start_time": f"{base_future_year}-04-01T15:30:00+05:30",
                "end_time": f"{base_future_year}-04-01T17:30:00+05:30",
                "event_title": "Offset Overlap Event (+05:30 is exact same instant as 10:00Z)"
            }
            st_off, data_off, _, body_off = self.request("POST", "/api/bookings", payload_tz_offset)
            # In proper temporal conflict detection, this MUST be rejected as 409 Conflict!
            # If server does naive string comparison in SQLite, this returns 201 Created (VULNERABILITY: Double Booking Bypass!)
            passed_tz_conflict = (st_off == 409)
            self.record_test("SuiteA", "A6.2", "Timezone offset conflict detection: same instant in +05:30 detected as conflict against UTC (409)", passed_tz_conflict, {
                "initial_utc_booking": payload_tz,
                "offset_booking": payload_tz_offset,
                "expected": "HTTP 409 Conflict (identical physical instant in time)",
                "actual": f"HTTP {st_off} -> {body_off}",
                "observation": f"Server responded {st_off}. Note: If 201 Created, SQLite string comparison bypassed conflict check!"
            })
            if data_off.get("id"):
                self.request("DELETE", f"/api/bookings/{data_off['id']}")
            self.request("DELETE", f"/api/bookings/{booking_tz_id}")

        # A7.1: Mixed naive start and timezone-aware end (naive vs aware)
        payload_mixed1 = {
            "resource_id": res_id,
            "user_id": f"u_a7_1_{run_id}",
            "user_name": "Mixed TZ Tester 1",
            "start_time": f"{base_future_year}-04-02T10:00:00",
            "end_time": f"{base_future_year}-04-02T12:00:00Z",
            "event_title": "Mixed Timezone Seminar (Naive Start, Aware End)"
        }
        st_m1, data_m1, _, body_m1 = self.request("POST", "/api/bookings", payload_mixed1)
        # Server should return 400 Bad Request, NOT crash (500 / RemoteDisconnected)
        passed_m1 = (st_m1 == 400)
        self.record_test("SuiteA", "A7.1", "Mixed naive start & aware end: handled with 400 (no unhandled 500 crash)", passed_m1, {
            "payload": payload_mixed1,
            "expected": "HTTP 400 Bad Request",
            "actual": f"HTTP {st_m1} -> {body_m1}",
            "observation": f"Server responded {st_m1}. Unhandled TypeError drops connection if not caught."
        })

        # A7.2: Mixed aware start and naive end (aware vs naive)
        payload_mixed2 = {
            "resource_id": res_id,
            "user_id": f"u_a7_2_{run_id}",
            "user_name": "Mixed TZ Tester 2",
            "start_time": f"{base_future_year}-04-02T10:00:00Z",
            "end_time": f"{base_future_year}-04-02T12:00:00",
            "event_title": "Mixed Timezone Seminar (Aware Start, Naive End)"
        }
        st_m2, data_m2, _, body_m2 = self.request("POST", "/api/bookings", payload_mixed2)
        passed_m2 = (st_m2 == 400)
        self.record_test("SuiteA", "A7.2", "Mixed aware start & naive end: handled with 400 (no unhandled 500 crash)", passed_m2, {
            "payload": payload_mixed2,
            "expected": "HTTP 400 Bad Request",
            "actual": f"HTTP {st_m2} -> {body_m2}",
            "observation": f"Server responded {st_m2}. Unhandled TypeError drops connection if not caught."
        })

        # A8: Multi-year booking (e.g. 5-year duration in conflict-free window)
        my_start = f"{base_future_year + 5}-01-01T00:00:00"
        my_end = f"{base_future_year + 10}-01-01T00:00:00"
        payload_multiyear = {
            "resource_id": res_id,
            "user_id": f"u_a8_{run_id}",
            "user_name": "Multi-Year Research Project",
            "start_time": my_start,
            "end_time": my_end,
            "event_title": "Long-Term AI Institute Grant"
        }
        st_my, data_my, _, body_my = self.request("POST", "/api/bookings", payload_multiyear)
        passed_my = (st_my in (201, 400))
        self.record_test("SuiteA", "A8", "Extreme boundary interval: Multi-year booking (5 years)", passed_my, {
            "payload": payload_multiyear,
            "expected": "HTTP 201 (created) or HTTP 400 (if max duration policy)",
            "actual": f"HTTP {st_my} -> {body_my}",
            "observation": f"Server responded {st_my}"
        })
        my_id = data_my.get("id")

        # Verify that an internal overlapping slot is correctly blocked during the 5-year span
        if st_my == 201 and my_id:
            payload_overlap_my = {
                "resource_id": res_id,
                "user_id": f"u_a8_overlap_{run_id}",
                "user_name": "Mid-Grant Interruption",
                "start_time": f"{base_future_year + 7}-06-01T10:00:00",
                "end_time": f"{base_future_year + 7}-06-01T12:00:00",
                "event_title": "Conflicting Mid-Grant Event"
            }
            st_my_ov, data_my_ov, _, body_my_ov = self.request("POST", "/api/bookings", payload_overlap_my)
            passed_my_ov = (st_my_ov == 409)
            self.record_test("SuiteA", "A8.1", "Multi-year booking prevents internal conflict across entire 5-year interval", passed_my_ov, {
                "payload": payload_overlap_my,
                "expected": "HTTP 409 Conflict",
                "actual": f"HTTP {st_my_ov} -> {body_my_ov}",
                "observation": f"Conflict detection inside multi-year booking returned {st_my_ov}"
            })
            self.request("DELETE", f"/api/bookings/{my_id}")

        # A9: Micro-interval bookings (1 millisecond / 1 microsecond interval)
        micro_start = f"{base_future_year}-06-01T10:00:00.000001"
        micro_end = f"{base_future_year}-06-01T10:00:00.000002"
        payload_micro = {
            "resource_id": res_id,
            "user_id": f"u_a9_{run_id}",
            "user_name": "High-Frequency Booking Tester",
            "start_time": micro_start,
            "end_time": micro_end,
            "event_title": "Microsecond Quantum Laser Pulse"
        }
        st_micro, data_micro, _, body_micro = self.request("POST", "/api/bookings", payload_micro)
        # Should either create (201) or reject if minimum duration required (400)
        passed_micro = (st_micro in (201, 400))
        self.record_test("SuiteA", "A9.1", "Micro-interval booking (1 microsecond duration)", passed_micro, {
            "payload": payload_micro,
            "expected": "HTTP 201 or HTTP 400 (if min duration enforced)",
            "actual": f"HTTP {st_micro} -> {body_micro}",
            "observation": f"Server responded {st_micro}"
        })
        micro_id = data_micro.get("id")
        if micro_id:
            self.request("DELETE", f"/api/bookings/{micro_id}")

        # A10: Midnight boundary transition (crossing from 23:55 to 00:05 next day)
        midnight_start = f"{base_future_year}-07-15T23:55:00"
        midnight_end = f"{base_future_year}-07-16T00:05:00"
        payload_midnight = {
            "resource_id": res_id,
            "user_id": f"u_a10_{run_id}",
            "user_name": "Nocturnal Astronomer",
            "start_time": midnight_start,
            "end_time": midnight_end,
            "event_title": "Midnight Stargazing Session"
        }
        st_mid, data_mid, _, body_mid = self.request("POST", "/api/bookings", payload_midnight)
        passed_mid = (st_mid == 201)
        self.record_test("SuiteA", "A10.1", "Midnight boundary transition (23:55 to 00:05 next day) accepted (201)", passed_mid, {
            "payload": payload_midnight,
            "expected": "HTTP 201 Created",
            "actual": f"HTTP {st_mid} -> {body_mid}",
            "observation": f"Server responded {st_mid}"
        })
        mid_id = data_mid.get("id")

        # Conflict check crossing midnight
        payload_mid_conflict = {
            "resource_id": res_id,
            "user_id": f"u_a10_c_{run_id}",
            "user_name": "Overlapping Nocturnal",
            "start_time": f"{base_future_year}-07-16T00:00:00",
            "end_time": f"{base_future_year}-07-16T01:00:00",
            "event_title": "Conflicting Post-Midnight Session"
        }
        st_mc, data_mc, _, body_mc = self.request("POST", "/api/bookings", payload_mid_conflict)
        passed_mc = (st_mc == 409)
        self.record_test("SuiteA", "A10.2", "Conflict check crossing midnight correctly rejected with 409", passed_mc, {
            "payload": payload_mid_conflict,
            "expected": "HTTP 409 Conflict",
            "actual": f"HTTP {st_mc} -> {body_mc}",
            "observation": f"Server responded {st_mc}"
        })
        if mid_id:
            self.request("DELETE", f"/api/bookings/{mid_id}")

        # A11: Adjacent bookings touching exactly at midnight boundary
        # Slot 1: 22:00 to 00:00 (ends exactly midnight)
        # Slot 2: 00:00 to 02:00 (starts exactly midnight)
        p_touch1 = {
            "resource_id": res_id,
            "user_id": f"u_a11_1_{run_id}",
            "user_name": "Pre-Midnight Prof",
            "start_time": f"{base_future_year}-08-01T22:00:00",
            "end_time": f"{base_future_year}-08-02T00:00:00",
            "event_title": "Pre-Midnight Study"
        }
        st_t1, data_t1, _, body_t1 = self.request("POST", "/api/bookings", p_touch1)
        p_touch2 = {
            "resource_id": res_id,
            "user_id": f"u_a11_2_{run_id}",
            "user_name": "Post-Midnight Prof",
            "start_time": f"{base_future_year}-08-02T00:00:00",
            "end_time": f"{base_future_year}-08-02T02:00:00",
            "event_title": "Post-Midnight Study"
        }
        st_t2, data_t2, _, body_t2 = self.request("POST", "/api/bookings", p_touch2)
        passed_touch = (st_t1 == 201 and st_t2 == 201)
        self.record_test("SuiteA", "A11", "Adjacent slots touching exactly at midnight allowed back-to-back (201)", passed_touch, {
            "expected": "Both slots return HTTP 201",
            "actual": f"Slot 1: HTTP {st_t1}, Slot 2: HTTP {st_t2}",
            "observation": f"Slot 1: {body_t1}, Slot 2: {body_t2}"
        })
        if data_t1.get("id"):
            self.request("DELETE", f"/api/bookings/{data_t1['id']}")
        if data_t2.get("id"):
            self.request("DELETE", f"/api/bookings/{data_t2['id']}")

        # A12: Year-end boundary transition (Dec 31 to Jan 1)
        p_yearend = {
            "resource_id": res_id,
            "user_id": f"u_a12_{run_id}",
            "user_name": "New Year Gala Organizer",
            "start_time": f"{base_future_year}-12-31T23:30:00",
            "end_time": f"{base_future_year + 1}-01-01T01:00:00",
            "event_title": "University New Year Countdown"
        }
        st_ye, data_ye, _, body_ye = self.request("POST", "/api/bookings", p_yearend)
        passed_ye = (st_ye == 201)
        self.record_test("SuiteA", "A12", "Year-end boundary transition (Dec 31 -> Jan 1) accepted (201)", passed_ye, {
            "payload": p_yearend,
            "expected": "HTTP 201 Created",
            "actual": f"HTTP {st_ye} -> {body_ye}",
            "observation": f"Server responded {st_ye}"
        })
        if data_ye.get("id"):
            self.request("DELETE", f"/api/bookings/{data_ye['id']}")

        # =========================================================================
        # SUITE B: Identification & Payload Integrity Stress Tests
        # =========================================================================
        print(f"\n{BOLD}--- SUITE B: Identification & Payload Integrity Stress Tests ---{RESET}")

        valid_time_start = f"{base_future_year}-09-01T10:00:00"
        valid_time_end = f"{base_future_year}-09-01T12:00:00"

        # B1: Missing user_id entirely
        p_no_uid = {
            "resource_id": res_id,
            "user_name": "No ID User",
            "start_time": valid_time_start,
            "end_time": valid_time_end,
            "event_title": "Missing User ID Event"
        }
        st, data, _, body = self.request("POST", "/api/bookings", p_no_uid)
        passed = (st == 400 and "user_id" in data.get("message", "").lower())
        self.record_test("SuiteB", "B1", "Missing user_id field entirely rejected with 400", passed, {
            "payload": p_no_uid,
            "expected": "HTTP 400 mentioning missing user_id",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # B2: Empty string user_id ""
        p_empty_uid = {
            "resource_id": res_id,
            "user_id": "",
            "user_name": "Empty ID User",
            "start_time": valid_time_start,
            "end_time": valid_time_end,
            "event_title": "Empty User ID Event"
        }
        st, data, _, body = self.request("POST", "/api/bookings", p_empty_uid)
        passed = (st == 400 and "user_id" in data.get("message", "").lower())
        self.record_test("SuiteB", "B2", "Empty string user_id rejected with 400", passed, {
            "payload": p_empty_uid,
            "expected": "HTTP 400 mentioning missing user_id",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # B3: Whitespace-only user_id "   "
        p_ws_uid = {
            "resource_id": res_id,
            "user_id": "    \t  \n  ",
            "user_name": "Whitespace ID User",
            "start_time": valid_time_start,
            "end_time": valid_time_end,
            "event_title": "Whitespace User ID Event"
        }
        st, data, _, body = self.request("POST", "/api/bookings", p_ws_uid)
        passed = (st == 400 and "user_id" in data.get("message", "").lower())
        self.record_test("SuiteB", "B3", "Whitespace-only user_id rejected with 400", passed, {
            "payload": p_ws_uid,
            "expected": "HTTP 400 mentioning missing user_id",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # B4: Null user_id (null in JSON)
        p_null_uid = {
            "resource_id": res_id,
            "user_id": None,
            "user_name": "Null ID User",
            "start_time": valid_time_start,
            "end_time": valid_time_end,
            "event_title": "Null User ID Event"
        }
        st, data, _, body = self.request("POST", "/api/bookings", p_null_uid)
        passed = (st == 400 and "user_id" in data.get("message", "").lower())
        self.record_test("SuiteB", "B4", "Null user_id rejected with 400", passed, {
            "payload": p_null_uid,
            "expected": "HTTP 400 mentioning missing user_id",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # B5: Missing user_name entirely
        p_no_uname = {
            "resource_id": res_id,
            "user_id": f"u_b5_{run_id}",
            "start_time": valid_time_start,
            "end_time": valid_time_end,
            "event_title": "Missing User Name Event"
        }
        st, data, _, body = self.request("POST", "/api/bookings", p_no_uname)
        passed = (st == 400 and "user_name" in data.get("message", "").lower())
        self.record_test("SuiteB", "B5", "Missing user_name entirely rejected with 400", passed, {
            "payload": p_no_uname,
            "expected": "HTTP 400 mentioning missing user_name",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # B6: Empty string user_name ""
        p_empty_uname = {
            "resource_id": res_id,
            "user_id": f"u_b6_{run_id}",
            "user_name": "",
            "start_time": valid_time_start,
            "end_time": valid_time_end,
            "event_title": "Empty User Name Event"
        }
        st, data, _, body = self.request("POST", "/api/bookings", p_empty_uname)
        passed = (st == 400 and "user_name" in data.get("message", "").lower())
        self.record_test("SuiteB", "B6", "Empty string user_name rejected with 400", passed, {
            "payload": p_empty_uname,
            "expected": "HTTP 400 mentioning missing user_name",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # B7: Null user_name
        p_null_uname = {
            "resource_id": res_id,
            "user_id": f"u_b7_{run_id}",
            "user_name": None,
            "start_time": valid_time_start,
            "end_time": valid_time_end,
            "event_title": "Null User Name Event"
        }
        st, data, _, body = self.request("POST", "/api/bookings", p_null_uname)
        passed = (st == 400 and "user_name" in data.get("message", "").lower())
        self.record_test("SuiteB", "B7", "Null user_name rejected with 400", passed, {
            "payload": p_null_uname,
            "expected": "HTTP 400 mentioning missing user_name",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # B8: Special characters in user_name: SQL Injection payload
        sql_injection_name = "Prof. Robert'); DROP TABLE bookings;--"
        p_sqli = {
            "resource_id": res_id,
            "user_id": f"u_b8_{run_id}",
            "user_name": sql_injection_name,
            "start_time": f"{base_future_year}-09-02T10:00:00",
            "end_time": f"{base_future_year}-09-02T12:00:00",
            "event_title": "Database Security Lecture"
        }
        st_sqli, data_sqli, _, body_sqli = self.request("POST", "/api/bookings", p_sqli)
        # Should be safely accepted with 201 (without executing SQL injection)
        passed_sqli = (st_sqli == 201 and data_sqli.get("user_name") == sql_injection_name)
        # Verify table bookings still exists by querying GET /api/bookings
        st_chk, bkgs_chk, _, _ = self.request("GET", "/api/bookings")
        table_intact = (st_chk == 200 and isinstance(bkgs_chk, list))
        self.record_test("SuiteB", "B8", "SQL Injection in user_name neutralized safely (parameterized query)", (passed_sqli and table_intact), {
            "payload": p_sqli,
            "expected": "HTTP 201 with literal user_name preserved and DB table bookings intact",
            "actual": f"HTTP {st_sqli}, DB Query status: {st_chk}",
            "observation": f"Booking ID: {data_sqli.get('id')}"
        })
        if data_sqli.get("id"):
            self.request("DELETE", f"/api/bookings/{data_sqli['id']}")

        # B9: Special characters in user_name & event_title: XSS script tags
        xss_string = "<script>alert('XSS Attack!')</script>"
        p_xss = {
            "resource_id": res_id,
            "user_id": f"u_b9_{run_id}",
            "user_name": f"Dr. {xss_string}",
            "start_time": f"{base_future_year}-09-03T10:00:00",
            "end_time": f"{base_future_year}-09-03T12:00:00",
            "event_title": f"Workshop on Web Security {xss_string}"
        }
        st_xss, data_xss, _, body_xss = self.request("POST", "/api/bookings", p_xss)
        passed_xss = (st_xss == 201)
        self.record_test("SuiteB", "B9", "XSS payload stored as literal text in API (201)", passed_xss, {
            "payload": p_xss,
            "expected": "HTTP 201 with text stored literally without server failure",
            "actual": f"HTTP {st_xss} -> {body_xss}",
            "observation": f"Booking ID: {data_xss.get('id')}"
        })
        if data_xss.get("id"):
            self.request("DELETE", f"/api/bookings/{data_xss['id']}")

        # B10: Unicode & Emojis in user_name and event_title
        unicode_name = "Prof. 🎓 Hélène Müller-Årström 👩‍🔬"
        unicode_title = "Quantum Entanglement & Space-Time 🚀 ✨ ⚛️"
        p_unicode = {
            "resource_id": res_id,
            "user_id": f"u_b10_{run_id}",
            "user_name": unicode_name,
            "start_time": f"{base_future_year}-09-04T10:00:00",
            "end_time": f"{base_future_year}-09-04T12:00:00",
            "event_title": unicode_title
        }
        st_uni, data_uni, _, body_uni = self.request("POST", "/api/bookings", p_unicode)
        passed_uni = (st_uni == 201 and data_uni.get("user_name") == unicode_name and data_uni.get("event_title") == unicode_title)
        self.record_test("SuiteB", "B10", "Unicode & multi-byte UTF-8 emoji strings stored and retrieved faithfully", passed_uni, {
            "payload": p_unicode,
            "expected": "HTTP 201 with exact UTF-8 preservation",
            "actual": f"HTTP {st_uni} -> user_name: {data_uni.get('user_name')}",
            "observation": f"Response: {body_uni}"
        })
        if data_uni.get("id"):
            self.request("DELETE", f"/api/bookings/{data_uni['id']}")

        # B11: Very long text in user_name and event_title (10,000 characters)
        long_title = "Extended Academic Colloquium " + ("A" * 10000)
        p_long = {
            "resource_id": res_id,
            "user_id": f"u_b11_{run_id}",
            "user_name": "Very Long Title User",
            "start_time": f"{base_future_year}-09-05T10:00:00",
            "end_time": f"{base_future_year}-09-05T12:00:00",
            "event_title": long_title
        }
        st_long, data_long, _, body_long = self.request("POST", "/api/bookings", p_long)
        # Check how server handles 10KB string (accepted or 400, but definitely not 500)
        passed_long = (st_long in (201, 400))
        self.record_test("SuiteB", "B11", "Large payload field (10,000 characters) handled without crash", passed_long, {
            "expected": "HTTP 201 or 400 (no 500 crash or memory exhaustion)",
            "actual": f"HTTP {st_long}",
            "observation": f"Status: {st_long}, booking ID: {data_long.get('id')}"
        })
        if data_long.get("id"):
            self.request("DELETE", f"/api/bookings/{data_long['id']}")

        # B12: Empty JSON payload {}
        st, data, _, body = self.request("POST", "/api/bookings", {})
        passed = (st == 400 and data.get("error") == "BadRequest")
        self.record_test("SuiteB", "B12", "Empty JSON payload {} rejected with 400", passed, {
            "payload": {},
            "expected": "HTTP 400 BadRequest",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # B13: Empty body (Content-Length: 0)
        st, data, _, body = self.request("POST", "/api/bookings", raw_body=b"", headers={"Content-Type": "application/json"})
        passed = (st == 400 and data.get("error") == "BadRequest")
        self.record_test("SuiteB", "B13", "Empty body (0 bytes) rejected with 400", passed, {
            "expected": "HTTP 400 BadRequest (Request body must not be empty)",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # B14: Malformed non-JSON body
        broken_json = b"{'invalid_json': unquoted_string, missing_brace:"
        st, data, _, body = self.request("POST", "/api/bookings", raw_body=broken_json, headers={"Content-Type": "application/json"})
        passed = (st == 400 and "malformed" in data.get("message", "").lower())
        self.record_test("SuiteB", "B14", "Malformed JSON syntax rejected with 400", passed, {
            "expected": "HTTP 400 Malformed JSON request",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # =========================================================================
        # SUITE C: Resource & Route Boundary Stress Tests
        # =========================================================================
        print(f"\n{BOLD}--- SUITE C: Resource & Route Boundary Stress Tests ---{RESET}")

        # C1: Non-existent resource booking
        p_ghost_res = {
            "resource_id": "ghost-hall-nonexistent-404",
            "user_id": f"u_c1_{run_id}",
            "user_name": "Ghost Hunter",
            "start_time": f"{base_future_year}-10-01T10:00:00",
            "end_time": f"{base_future_year}-10-01T12:00:00",
            "event_title": "Phantom Booking"
        }
        st, data, _, body = self.request("POST", "/api/bookings", p_ghost_res)
        passed = (st == 404 and data.get("error") == "NotFound")
        self.record_test("SuiteC", "C1", "Booking non-existent resource_id returns 404 NotFound", passed, {
            "payload": p_ghost_res,
            "expected": "HTTP 404 NotFound",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # C2: Empty string resource_id
        p_empty_res = {
            "resource_id": "",
            "user_id": f"u_c2_{run_id}",
            "user_name": "No Resource User",
            "start_time": f"{base_future_year}-10-01T10:00:00",
            "end_time": f"{base_future_year}-10-01T12:00:00",
            "event_title": "No Resource Booking"
        }
        st, data, _, body = self.request("POST", "/api/bookings", p_empty_res)
        passed = (st == 400 and "resource_id" in data.get("message", "").lower())
        self.record_test("SuiteC", "C2", "Empty resource_id rejected with 400", passed, {
            "payload": p_empty_res,
            "expected": "HTTP 400 mentioning missing resource_id",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # C3: GET non-existent resource details
        st, data, _, body = self.request("GET", "/api/resources/nonexistent-resource-id-999")
        passed = (st == 404 and data.get("error") == "NotFound")
        self.record_test("SuiteC", "C3", "GET non-existent resource returns 404 NotFound", passed, {
            "expected": "HTTP 404 NotFound",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # C4: DELETE non-existent booking ID
        st, data, _, body = self.request("DELETE", "/api/bookings/bkg_nonexistent_999999")
        passed = (st == 404 and data.get("error") == "NotFound")
        self.record_test("SuiteC", "C4", "DELETE non-existent booking returns 404 NotFound", passed, {
            "expected": "HTTP 404 NotFound",
            "actual": f"HTTP {st} -> {body}",
            "observation": f"Server responded {st}"
        })

        # C5: Double DELETE on valid booking (Idempotency / State inspection)
        # Create temporary booking
        p_del = {
            "resource_id": res_id,
            "user_id": f"u_c5_{run_id}",
            "user_name": "Delete Tester",
            "start_time": f"{base_future_year}-10-05T10:00:00",
            "end_time": f"{base_future_year}-10-05T12:00:00",
            "event_title": "Temporary Deletion Booking"
        }
        st_cr, data_cr, _, _ = self.request("POST", "/api/bookings", p_del)
        temp_id = data_cr.get("id")
        st_d1, data_d1, _, body_d1 = self.request("DELETE", f"/api/bookings/{temp_id}")
        st_d2, data_d2, _, body_d2 = self.request("DELETE", f"/api/bookings/{temp_id}")
        # Does the second delete return 200 (idempotent cancel) or 404/410/409?
        self.record_test("SuiteC", "C5", f"Double DELETE on booking {temp_id}: 1st={st_d1}, 2nd={st_d2}", (st_d1 == 200 and st_d2 in (200, 404)), {
            "expected": "1st DELETE: 200, 2nd DELETE: 200 (idempotent) or 404",
            "actual": f"1st: HTTP {st_d1}, 2nd: HTTP {st_d2}",
            "observation": f"2nd DELETE body: {body_d2}"
        })

        # C6: Invalid HTTP Methods
        # PUT /api/bookings
        st_put, data_put, _, body_put = self.request("PUT", "/api/bookings", p_del)
        passed_put = (st_put in (405, 501))
        self.record_test("SuiteC", "C6.1", "Invalid HTTP Method: PUT /api/bookings returns 405/501", passed_put, {
            "expected": "HTTP 405 Method Not Allowed or 501 Unsupported Method",
            "actual": f"HTTP {st_put} -> {body_put}",
            "observation": f"Server responded {st_put}"
        })

        # PATCH /api/resources
        st_patch, data_patch, _, body_patch = self.request("PATCH", "/api/resources", {"test": "val"})
        passed_patch = (st_patch in (405, 501))
        self.record_test("SuiteC", "C6.2", "Invalid HTTP Method: PATCH /api/resources returns 405/501", passed_patch, {
            "expected": "HTTP 405 Method Not Allowed or 501 Unsupported Method",
            "actual": f"HTTP {st_patch} -> {body_patch}",
            "observation": f"Server responded {st_patch}"
        })

        # POST /api/resources (Read-only collection)
        st_post_res, data_post_res, _, body_post_res = self.request("POST", "/api/resources", {"name": "Unauthorized Hall"})
        passed_post_res = (st_post_res in (404, 405))
        self.record_test("SuiteC", "C6.3", "Invalid POST to read-only /api/resources returns 404/405", passed_post_res, {
            "expected": "HTTP 404 or 405",
            "actual": f"HTTP {st_post_res} -> {body_post_res}",
            "observation": f"Server responded {st_post_res}"
        })

        # DELETE /api/resources
        st_del_res, data_del_res, _, body_del_res = self.request("DELETE", "/api/resources")
        passed_del_res = (st_del_res in (404, 405))
        self.record_test("SuiteC", "C6.4", "Invalid DELETE on collection /api/resources returns 404/405", passed_del_res, {
            "expected": "HTTP 404 or 405",
            "actual": f"HTTP {st_del_res} -> {body_del_res}",
            "observation": f"Server responded {st_del_res}"
        })

        # C7: Non-existent API Endpoints
        st_unknown, data_unknown, _, body_unknown = self.request("GET", "/api/unknown_endpoint_xyz")
        # Should not crash, should return 404
        passed_unknown = (st_unknown == 404)
        self.record_test("SuiteC", "C7.1", "GET non-existent API endpoint returns 404", passed_unknown, {
            "expected": "HTTP 404",
            "actual": f"HTTP {st_unknown}",
            "observation": f"Response: {body_unknown}"
        })

        st_unknown_p, data_unknown_p, _, body_unknown_p = self.request("POST", "/api/unknown_endpoint_xyz", {"dummy": 1})
        passed_unknown_p = (st_unknown_p == 404)
        self.record_test("SuiteC", "C7.2", "POST non-existent API endpoint returns 404", passed_unknown_p, {
            "expected": "HTTP 404",
            "actual": f"HTTP {st_unknown_p}",
            "observation": f"Response: {body_unknown_p}"
        })

        # C8: Path traversal probe (e.g. /../server.py)
        st_trav, _, _, body_trav = self.request("GET", "/../server.py")
        # SimpleHTTPRequestHandler maps paths within PUBLIC_DIR. It should NOT leak server.py or should return 404
        passed_trav = (st_trav in (400, 403, 404)) or ("AcademicBookingHandler" not in body_trav)
        self.record_test("SuiteC", "C8", "Directory traversal attempt blocked (no source leak)", passed_trav, {
            "expected": "HTTP 400/403/404 or sanitized path without leaking server.py source code",
            "actual": f"HTTP {st_trav}",
            "observation": f"Body leaked server.py: {'AcademicBookingHandler' in body_trav}"
        })

        # =========================================================================
        # SUITE D: Concurrency & Duplicate Submission Stress Tests
        # =========================================================================
        print(f"\n{BOLD}--- SUITE D: Concurrency & Duplicate Submission Stress Tests ---{RESET}")

        # D1: Rapid sequential duplicate submission
        seq_slot_start = f"{base_future_year}-11-01T10:00:00"
        seq_slot_end = f"{base_future_year}-11-01T12:00:00"
        p_seq = {
            "resource_id": res_id,
            "user_id": f"u_d1_{run_id}",
            "user_name": "Sequential Submitter",
            "start_time": seq_slot_start,
            "end_time": seq_slot_end,
            "event_title": "Sequential Duplicate Test"
        }
        st_seq1, data_seq1, _, body_seq1 = self.request("POST", "/api/bookings", p_seq)
        st_seq2, data_seq2, _, body_seq2 = self.request("POST", "/api/bookings", p_seq)
        passed_seq = (st_seq1 == 201 and st_seq2 == 409 and data_seq2.get("error") == "Conflict")
        self.record_test("SuiteD", "D1", "Rapid sequential duplicate submission: 1st=201, 2nd=409 Conflict", passed_seq, {
            "expected": "1st request: 201 Created, 2nd request: 409 Conflict",
            "actual": f"1st: HTTP {st_seq1}, 2nd: HTTP {st_seq2}",
            "observation": f"2nd body: {body_seq2}"
        })
        if data_seq1.get("id"):
            self.request("DELETE", f"/api/bookings/{data_seq1['id']}")

        # D2: Concurrent burst race condition test (15 parallel requests for identical slot)
        concur_slot_start = f"{base_future_year}-11-02T14:00:00"
        concur_slot_end = f"{base_future_year}-11-02T16:00:00"
        burst_size = 15

        def submit_burst_request(worker_idx: int):
            burst_payload = {
                "resource_id": res_id,
                "user_id": f"racer_{worker_idx}_{run_id}",
                "user_name": f"Concurrent Racer #{worker_idx}",
                "start_time": concur_slot_start,
                "end_time": concur_slot_end,
                "event_title": f"High Concurrency Contention #{worker_idx}"
            }
            s_code, resp_d, _, _ = self.request("POST", "/api/bookings", burst_payload)
            return s_code, resp_d

        print(f"       Dispatching {burst_size} parallel threads for identical time slot...")
        start_burst = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=burst_size) as executor:
            futures = [executor.submit(submit_burst_request, i) for i in range(burst_size)]
            burst_results = [f.result() for f in concurrent.futures.as_completed(futures)]
        burst_duration = time.time() - start_burst

        status_counts = {}
        created_booking_ids = []
        for code, resp in burst_results:
            status_counts[code] = status_counts.get(code, 0) + 1
            if code == 201 and "id" in resp:
                created_booking_ids.append(resp["id"])

        # In strict atomic conflict prevention:
        # EXACTLY 1 request must receive 201 Created.
        # EXACTLY (burst_size - 1) requests must receive 409 Conflict.
        # ZERO 500 errors, ZERO unhandled race conditions.
        passed_concur = (status_counts.get(201) == 1 and status_counts.get(409) == (burst_size - 1) and len(status_counts) == 2)
        self.record_test("SuiteD", "D2", f"Atomic concurrency contention: 1x 201 Created, {burst_size - 1}x 409 Conflict (0 race hazards)", passed_concur, {
            "burst_size": burst_size,
            "duration_sec": round(burst_duration, 3),
            "status_counts": status_counts,
            "created_ids": created_booking_ids,
            "expected": f"{{201: 1, 409: {burst_size - 1}}}",
            "actual": str(status_counts),
            "observation": f"Completed {burst_size} concurrent requests in {burst_duration:.3f}s"
        })

        # Verify database integrity: query bookings for this slot
        st_chk, active_bkgs, _, _ = self.request("GET", f"/api/bookings?resource_id={res_id}")
        slot_matches = [b for b in active_bkgs if b.get("start_time") == concur_slot_start]
        passed_db_integrity = (len(slot_matches) == 1 and slot_matches[0]["id"] == created_booking_ids[0])
        self.record_test("SuiteD", "D2.1", "Database integrity after concurrent burst: exactly 1 booking persisted", passed_db_integrity, {
            "expected": "Exactly 1 persisted booking matching timestamp in SQLite",
            "actual": f"Found {len(slot_matches)} matching bookings in active list",
            "observation": f"Persisted booking: {slot_matches}"
        })

        # Cleanup concurrent test booking
        for b_id in created_booking_ids:
            self.request("DELETE", f"/api/bookings/{b_id}")

        # D3: Immediate re-booking after cancellation
        rebook_start = f"{base_future_year}-11-03T09:00:00"
        rebook_end = f"{base_future_year}-11-03T11:00:00"
        p_rebook1 = {
            "resource_id": res_id,
            "user_id": f"u_d3_orig_{run_id}",
            "user_name": "Original Booker",
            "start_time": rebook_start,
            "end_time": rebook_end,
            "event_title": "Original Reservation"
        }
        st_rb1, data_rb1, _, _ = self.request("POST", "/api/bookings", p_rebook1)
        orig_id = data_rb1.get("id")
        # Cancel booking
        st_del_rb, _, _, _ = self.request("DELETE", f"/api/bookings/{orig_id}")
        # Now immediate re-booking of the identical slot by another user
        p_rebook2 = {
            "resource_id": res_id,
            "user_id": f"u_d3_new_{run_id}",
            "user_name": "Successor Booker",
            "start_time": rebook_start,
            "end_time": rebook_end,
            "event_title": "Re-booked Freed Reservation"
        }
        st_rb2, data_rb2, _, body_rb2 = self.request("POST", "/api/bookings", p_rebook2)
        passed_rebook = (st_rb1 == 201 and st_del_rb == 200 and st_rb2 == 201)
        self.record_test("SuiteD", "D3", "Slot liberation & immediate re-booking after DELETE cancellation (201)", passed_rebook, {
            "expected": "1st book: 201, delete: 200, 2nd book: 201",
            "actual": f"1st book: {st_rb1}, delete: {st_del_rb}, 2nd book: {st_rb2}",
            "observation": f"Re-booked booking ID: {data_rb2.get('id')}"
        })
        if data_rb2.get("id"):
            self.request("DELETE", f"/api/bookings/{data_rb2['id']}")

        # =========================================================================
        # SUMMARY & RESULTS EXPORT
        # =========================================================================
        total_tests = self.passed_count + self.failed_count
        success_rate = (self.passed_count / total_tests * 100) if total_tests > 0 else 0

        print("\n" + "=" * 80)
        print(f"{BOLD}CHALLENGE SUITE SUMMARY:{RESET}")
        print(f"Total Test Probes Executed: {total_tests}")
        print(f"Passed:                     {GREEN}{self.passed_count}{RESET}")
        print(f"Failed / Vulnerabilities:   {RED if self.failed_count > 0 else GREEN}{self.failed_count}{RESET}")
        print(f"Success Rate:               {GREEN if self.failed_count == 0 else RED}{success_rate:.1f}%{RESET}")
        print("=" * 80)

        # Write results to json
        out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "challenge_results.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "target_url": self.base_url,
                "total_probes": total_tests,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "success_rate_pct": success_rate,
                "vulnerabilities": self.vulnerabilities,
                "results": self.results
            }, f, indent=2)
        print(f"\nDetailed execution artifact written to: {out_file}\n")


if __name__ == "__main__":
    target_url = "http://127.0.0.1:8000"
    if len(sys.argv) > 1:
        target_url = sys.argv[1]
    runner = EmpiricalChallengeRunner(target_url)
    runner.run_all()
