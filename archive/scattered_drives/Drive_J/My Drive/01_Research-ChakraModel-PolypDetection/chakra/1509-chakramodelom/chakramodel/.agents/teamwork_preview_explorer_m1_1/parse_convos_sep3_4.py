import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
data = json.load(open('OM_rama_krish_convo.json', 'r', encoding='utf-8'))

for date in ['2026-09-03', '2026-09-04']:
    convs = [d for d in data if d.get('timestamp', '').startswith(date)]
    print(f"=== Date: {date} (Total: {len(convs)}) ===")
    for d in convs[::max(1, len(convs)//10)]:  # sample every ~10th
        ts = d.get('timestamp')
        cid = d.get('conversation_id')
        s = d.get('summary', '').replace('\n', ' ')
        print(f"[{ts}] ({cid}): {s[:180]}")
    print()
