import sqlite3

conn = sqlite3.connect("booking.db")
cur = conn.cursor()
cur.execute("SELECT * FROM bookings WHERE id = 'bkg_2d07577e'")
print("Found row:", cur.fetchone())
conn.close()
