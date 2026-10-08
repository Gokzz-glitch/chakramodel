import sqlite3

conn = sqlite3.connect(r"J:\My Drive\girupa project\booking.db")
cur = conn.cursor()
cur.execute("SELECT * FROM bookings WHERE id = 'bkg_ba8e9e8c'")
print("Found row for bkg_ba8e9e8c:", cur.fetchone())

cur.execute("SELECT id, user_id, user_name, created_at FROM bookings ORDER BY created_at DESC LIMIT 5")
print("Top 5 latest bookings:")
for r in cur.fetchall():
    print(r)
conn.close()
