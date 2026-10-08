import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "..", "booking.db")
db_path = os.path.abspath(db_path)
print("DB Path:", db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

integrity = cur.execute("PRAGMA integrity_check").fetchall()
print("PRAGMA integrity_check:", integrity)

tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)

indexes = cur.execute("SELECT name, tbl_name, sql FROM sqlite_master WHERE type='index'").fetchall()
print("Indexes:", indexes)

resources_count = cur.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
bookings_count = cur.execute("SELECT COUNT(*) FROM bookings").fetchone()[0]
confirmed_count = cur.execute("SELECT COUNT(*) FROM bookings WHERE status='CONFIRMED'").fetchone()[0]
cancelled_count = cur.execute("SELECT COUNT(*) FROM bookings WHERE status='CANCELLED'").fetchone()[0]

print(f"Resources: {resources_count}")
print(f"Total Bookings: {bookings_count} (Confirmed: {confirmed_count}, Cancelled: {cancelled_count})")

print("\nSample 5 bookings:")
for row in cur.execute("SELECT id, resource_id, user_id, user_name, start_time, end_time, event_title, status FROM bookings ORDER BY created_at DESC LIMIT 5").fetchall():
    print(row)

conn.close()
