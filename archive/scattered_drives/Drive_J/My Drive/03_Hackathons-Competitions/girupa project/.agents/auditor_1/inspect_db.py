import sqlite3

conn = sqlite3.connect('booking.db')
cur = conn.cursor()
cur.execute("SELECT id, user_id, user_name, start_time, end_time, created_at FROM bookings WHERE id = 'bkg_0f73a0e5'")
print("Record bkg_0f73a0e5:", cur.fetchone())

cur.execute("SELECT id, user_id, user_name, start_time, end_time, created_at FROM bookings WHERE id = 'bkg_03195632'")
print("Record bkg_03195632:", cur.fetchone())
