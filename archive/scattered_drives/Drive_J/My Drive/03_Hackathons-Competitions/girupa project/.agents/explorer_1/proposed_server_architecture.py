"""
Proposed Server & Runtime Architecture for Academic Event & Resource Booking Portal.
Explorer 1 (Codebase Environment & Runtime Architecture Explorer).

This reference architecture implements:
1. Zero external dependencies (uses Python standard library: http.server, sqlite3, json, socket, urllib).
2. Dynamic port discovery starting at 8000 with clash avoidance and .server_port file output.
3. ThreadingHTTPServer for concurrent request handling (crucial for concurrency testing).
4. Atomic database transactions with busy timeouts for reliable conflict prevention.
5. Unified static file serving (from public/) and REST API (/api/*).
"""

import os
import sys
import json
import socket
import sqlite3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Port Allocation Strategy
DEFAULT_PORT = 8000
PORT_FILE = ".server_port"

def find_available_port(start_port: int = DEFAULT_PORT, max_attempts: int = 50) -> int:
    """Finds an available TCP port on localhost starting at start_port."""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(('127.0.0.1', port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"Unable to find an available port in range {start_port} to {start_port + max_attempts}")

def get_db_connection(db_path: str = "booking.db") -> sqlite3.Connection:
    """Returns a SQLite connection configured with proper row factory and busy timeout."""
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(db_path: str = "booking.db"):
    """Initializes database schema and seed data if not present."""
    conn = get_db_connection(db_path)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS resources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                location TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id TEXT PRIMARY KEY,
                resource_id TEXT NOT NULL REFERENCES resources(id),
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                event_title TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bookings_resource_time 
            ON bookings (resource_id, start_time, end_time);
        """)
        # Seed resources if empty
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM resources")
        if cur.fetchone()[0] == 0:
            seed_resources = [
                ("hall-a", "Seminar Hall A", "seminar_hall", 200, "Academic Block 1"),
                ("hall-b", "Auditorium B", "auditorium", 500, "Convention Centre"),
                ("lab-cs1", "Computer Science Lab 1", "laboratory", 45, "Computing Complex"),
                ("lab-ai", "AI Research Lab", "laboratory", 30, "Computing Complex"),
                ("cr-101", "Lecture Classroom 101", "classroom", 60, "Academic Block 2"),
                ("cr-202", "Smart Classroom 202", "classroom", 75, "Academic Block 2")
            ]
            cur.executemany(
                "INSERT INTO resources (id, name, type, capacity, location) VALUES (?, ?, ?, ?, ?)",
                seed_resources
            )
    conn.close()

class BookingRequestHandler(SimpleHTTPRequestHandler):
    """Handles static files from public/ and dynamic REST API requests."""

    def __init__(self, *args, directory=None, **kwargs):
        public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
        if not os.path.exists(public_dir):
            public_dir = os.path.abspath("public")
        super().__init__(*args, directory=public_dir, **kwargs)

    def _send_json(self, status: int, data: dict or list):
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/resources":
            conn = get_db_connection()
            rows = conn.execute("SELECT id, name, type, capacity, location FROM resources").fetchall()
            resources = [dict(row) for row in rows]
            conn.close()
            self._send_json(200, resources)
            return

        if parsed.path == "/api/bookings":
            params = parse_qs(parsed.query)
            resource_id = params.get("resource_id", [None])[0]
            conn = get_db_connection()
            if resource_id:
                rows = conn.execute(
                    "SELECT id, resource_id, user_id, user_name, start_time, end_time, event_title FROM bookings WHERE resource_id = ? ORDER BY start_time ASC",
                    (resource_id,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, resource_id, user_id, user_name, start_time, end_time, event_title FROM bookings ORDER BY start_time ASC"
                ).fetchall()
            bookings = [dict(row) for row in rows]
            conn.close()
            self._send_json(200, bookings)
            return

        # Fall back to serving static files from public/
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/bookings":
            try:
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length).decode("utf-8")
                data = json.loads(raw_body)
            except Exception as e:
                self._send_json(400, {"error": "BadRequest", "message": f"Invalid JSON body: {str(e)}"})
                return

            # Validate mandatory fields
            required = ["resource_id", "user_id", "user_name", "start_time", "end_time", "event_title"]
            missing = [f for f in required if not data.get(f)]
            if missing:
                self._send_json(400, {"error": "BadRequest", "message": f"Missing required fields: {', '.join(missing)}"})
                return

            req_res = data["resource_id"]
            req_start = data["start_time"]
            req_end = data["end_time"]

            if req_start >= req_end:
                self._send_json(400, {"error": "BadRequest", "message": "start_time must be strictly earlier than end_time"})
                return

            conn = get_db_connection()
            try:
                with conn:
                    # Check resource existence
                    res_exists = conn.execute("SELECT id FROM resources WHERE id = ?", (req_res,)).fetchone()
                    if not res_exists:
                        self._send_json(404, {"error": "NotFound", "message": f"Resource {req_res} does not exist"})
                        return

                    # Strict conflict check: [start_time < existing_end] AND [end_time > existing_start]
                    conflict = conn.execute(
                        """
                        SELECT id, event_title, start_time, end_time 
                        FROM bookings 
                        WHERE resource_id = ? 
                          AND (? < end_time AND ? > start_time)
                        LIMIT 1
                        """,
                        (req_res, req_start, req_end)
                    ).fetchone()

                    if conflict:
                        self._send_json(409, {
                            "error": "Conflict",
                            "message": f"Resource {req_res} is already reserved for the requested time slot.",
                            "conflict_with": {
                                "booking_id": conflict["id"],
                                "title": conflict["event_title"],
                                "start_time": conflict["start_time"],
                                "end_time": conflict["end_time"]
                            }
                        })
                        return

                    # Create booking
                    import uuid
                    booking_id = f"bkg_{uuid.uuid4().hex[:8]}"
                    conn.execute(
                        """
                        INSERT INTO bookings (id, resource_id, user_id, user_name, start_time, end_time, event_title)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (booking_id, req_res, data["user_id"], data["user_name"], req_start, req_end, data["event_title"])
                    )

                    new_booking = {
                        "id": booking_id,
                        "resource_id": req_res,
                        "user_id": data["user_id"],
                        "user_name": data["user_name"],
                        "start_time": req_start,
                        "end_time": req_end,
                        "event_title": data["event_title"]
                    }
                    self._send_json(201, new_booking)
            finally:
                conn.close()
            return

        self._send_json(404, {"error": "NotFound", "message": f"Endpoint {self.path} not found"})

def run_server(port: int = None):
    init_db()
    if port is None:
        env_port = os.environ.get("PORT")
        if env_port and env_port.isdigit():
            port = int(env_port)
        else:
            port = find_available_port(DEFAULT_PORT)

    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, BookingRequestHandler)

    # Write port file for automated testing tools
    try:
        with open(PORT_FILE, "w", encoding="utf-8") as pf:
            pf.write(str(port))
    except Exception:
        pass

    print(f"SERVER_RUNNING: http://127.0.0.1:{port}")
    print(f"Serving static files and API at http://127.0.0.1:{port}")
    print(f"API Endpoints: GET /api/resources, GET /api/bookings, POST /api/bookings")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
    finally:
        httpd.server_close()
        if os.path.exists(PORT_FILE):
            try:
                os.remove(PORT_FILE)
            except Exception:
                pass
        print("Server shutdown complete.")

if __name__ == "__main__":
    cli_port = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        cli_port = int(sys.argv[1])
    elif "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1].isdigit():
            cli_port = int(sys.argv[idx + 1])
    run_server(cli_port)
