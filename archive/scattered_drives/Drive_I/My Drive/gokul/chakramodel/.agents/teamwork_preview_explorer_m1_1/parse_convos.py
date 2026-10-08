import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
data = json.load(open('OM_rama_krish_convo.json', 'r', encoding='utf-8'))

dates_to_inspect = ['2026-08-14', '2026-08-21', '2026-08-29', '2026-08-30', '2026-09-01', '2026-09-02', 'Unknown timestamp']
for d in data:
    ts = d.get('timestamp', 'Unknown')
    date = ts.split('T')[0] if 'T' in ts else ts
    if date in dates_to_inspect:
        cid = d.get('conversation_id', 'none')
        summary = d.get('summary', '')
        print(f"=== {ts} | ID: {cid} ===")
        print(summary[:400])
        print("-" * 50)
