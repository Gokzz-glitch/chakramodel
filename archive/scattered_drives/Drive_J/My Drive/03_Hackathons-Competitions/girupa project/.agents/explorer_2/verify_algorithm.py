import sqlite3
import uuid
import datetime

# Setup in-memory DB
conn = sqlite3.connect(':memory:')
conn.isolation_level = None
cur = conn.cursor()

cur.executescript('''
CREATE TABLE resources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    location TEXT NOT NULL,
    equipment TEXT NOT NULL,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE bookings (
    id TEXT PRIMARY KEY,
    resource_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    start_epoch INTEGER NOT NULL,
    end_epoch INTEGER NOT NULL,
    event_title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CONFIRMED'
);
CREATE INDEX idx_bkg_res ON bookings(resource_id, status, start_epoch, end_epoch);
''')

# Seed
cur.execute('INSERT INTO resources VALUES (?, ?, ?, ?, ?, ?, ?, 1)', 
    ('hall-a', 'Seminar Hall A', 'seminar_hall', 200, 'Block A Ground Floor', '["Projector", "Mics"]', 'Main hall'))

def book(resource_id, user_id, user_name, start_str, end_str, title):
    try:
        dt_start = datetime.datetime.fromisoformat(start_str)
        dt_end = datetime.datetime.fromisoformat(end_str)
    except Exception as e:
        return 400, {'error': f'Invalid ISO format: {e}'}
    
    s_epoch = int(dt_start.timestamp())
    e_epoch = int(dt_end.timestamp())
    if s_epoch >= e_epoch:
        return 400, {'error': 'start_time must be strictly before end_time.'}
    
    cur.execute('BEGIN IMMEDIATE')
    # Check resource
    cur.execute('SELECT count(*) FROM resources WHERE id = ? AND is_active = 1', (resource_id,))
    if cur.fetchone()[0] == 0:
        cur.execute('ROLLBACK')
        return 404, {'error': f'Resource {resource_id} not found.'}
    
    # Check overlap: new_start < existing_end and new_end > existing_start
    cur.execute('''
        SELECT id, event_title, start_time, end_time, user_name 
        FROM bookings 
        WHERE resource_id = ? AND status = 'CONFIRMED' AND start_epoch < ? AND end_epoch > ?
    ''', (resource_id, e_epoch, s_epoch))
    conflict = cur.fetchone()
    if conflict:
        cur.execute('ROLLBACK')
        return 409, {
            'error': 'Conflict', 
            'message': f'Resource {resource_id} is already reserved for the requested time slot.',
            'conflict': {'id': conflict[0], 'event_title': conflict[1], 'start_time': conflict[2], 'end_time': conflict[3]}
        }
    
    b_id = f'bkg-{uuid.uuid4().hex[:8]}'
    cur.execute('''
        INSERT INTO bookings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CONFIRMED')
    ''', (b_id, resource_id, user_id, user_name, start_str, end_str, s_epoch, e_epoch, title))
    cur.execute('COMMIT')
    return 201, {'id': b_id, 'resource_id': resource_id, 'status': 'CONFIRMED'}

# Test 1: Initial booking
code, res = book('hall-a', 'prof_smith', 'Prof. Smith', '2026-09-20T10:00:00', '2026-09-20T12:00:00', 'AI Colloquium')
assert code == 201, f'Expected 201, got {code}'
print('Test 1 (Initial booking): PASSED')

# Test 2: Exact duplicate booking
code, res = book('hall-a', 'prof_jones', 'Prof. Jones', '2026-09-20T10:00:00', '2026-09-20T12:00:00', 'Math Workshop')
assert code == 409, f'Expected 409, got {code}: {res}'
print('Test 2 (Exact duplicate rejection): PASSED')

# Test 3: Partial overlap (starts before, ends inside)
code, res = book('hall-a', 'prof_jones', 'Prof. Jones', '2026-09-20T09:00:00', '2026-09-20T11:00:00', 'Math Workshop')
assert code == 409, f'Expected 409, got {code}'
print('Test 3 (Partial overlap start rejection): PASSED')

# Test 4: Partial overlap (starts inside, ends after)
code, res = book('hall-a', 'prof_jones', 'Prof. Jones', '2026-09-20T11:00:00', '2026-09-20T13:00:00', 'Math Workshop')
assert code == 409, f'Expected 409, got {code}'
print('Test 4 (Partial overlap end rejection): PASSED')

# Test 5: Enveloping (outside)
code, res = book('hall-a', 'prof_jones', 'Prof. Jones', '2026-09-20T08:00:00', '2026-09-20T14:00:00', 'Mega Conference')
assert code == 409, f'Expected 409, got {code}'
print('Test 5 (Enveloping rejection): PASSED')

# Test 6: Enclosed (inside)
code, res = book('hall-a', 'prof_jones', 'Prof. Jones', '2026-09-20T10:30:00', '2026-09-20T11:30:00', 'Brief Meeting')
assert code == 409, f'Expected 409, got {code}'
print('Test 6 (Enclosed rejection): PASSED')

# Test 7: Adjacent before (consecutive, 08:00 to 10:00)
code, res = book('hall-a', 'prof_clark', 'Prof. Clark', '2026-09-20T08:00:00', '2026-09-20T10:00:00', 'Early Class')
assert code == 201, f'Expected 201, got {code}: {res}'
print('Test 7 (Adjacent before accepted): PASSED')

# Test 8: Adjacent after (consecutive, 12:00 to 14:00)
code, res = book('hall-a', 'prof_davis', 'Prof. Davis', '2026-09-20T12:00:00', '2026-09-20T14:00:00', 'Afternoon Seminar')
assert code == 201, f'Expected 201, got {code}: {res}'
print('Test 8 (Adjacent after accepted): PASSED')

# Test 9: Invalid time range (start >= end)
code, res = book('hall-a', 'bad_user', 'Bad User', '2026-09-20T15:00:00', '2026-09-20T14:00:00', 'Impossible')
assert code == 400, f'Expected 400, got {code}'
print('Test 9 (Invalid time range 400): PASSED')

# Test 10: Non-existent resource
code, res = book('non-existent', 'user', 'User', '2026-09-20T15:00:00', '2026-09-20T16:00:00', 'Test')
assert code == 404, f'Expected 404, got {code}'
print('Test 10 (Non-existent resource 404): PASSED')

# Test 11: Different resource at same time should succeed
cur.execute('INSERT INTO resources VALUES (?, ?, ?, ?, ?, ?, ?, 1)', 
    ('hall-b', 'Seminar Hall B', 'seminar_hall', 120, 'Science Complex', '[]', 'Second hall'))
code, res = book('hall-b', 'prof_smith', 'Prof. Smith', '2026-09-20T10:00:00', '2026-09-20T12:00:00', 'Parallel Session')
assert code == 201, f'Expected 201, got {code}'
print('Test 11 (Different resource concurrent slot accepted): PASSED')

print('\n>>> ALL 11 ALGORITHM VERIFICATION TESTS PASSED UNCONDITIONALLY! <<<')
