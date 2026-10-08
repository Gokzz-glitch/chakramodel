import sqlite3
import datetime
import os

DB_PATH = r"M:\free_lancing\campaign.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS outreach (
            email TEXT PRIMARY KEY,
            company TEXT,
            date_sent TEXT,
            status TEXT,
            follow_up_sent INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def log_email_sent(email, company):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO outreach (email, company, date_sent, status, follow_up_sent)
            VALUES (?, ?, ?, 'sent', 0)
        ''', (email, company, today))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()

def get_pending_followups(days_delay=3):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    target_date = (datetime.datetime.now() - datetime.timedelta(days=days_delay)).strftime("%Y-%m-%d")
    
    cursor.execute('''
        SELECT email, company FROM outreach 
        WHERE status = 'sent' AND follow_up_sent = 0 AND date_sent <= ?
    ''', (target_date,))
    
    results = cursor.fetchall()
    conn.close()
    return [{"Email": r[0], "Company": r[1], "Context": "Following up on my previous email.", "Type": "follow_up"} for r in results]

def mark_followup_sent(email):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE outreach SET follow_up_sent = 1 WHERE email = ?", (email,))
    conn.commit()
    conn.close()

def get_stats():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM outreach")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM outreach WHERE follow_up_sent = 1")
    followups = cursor.fetchone()[0]
    conn.close()
    return total, followups

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
