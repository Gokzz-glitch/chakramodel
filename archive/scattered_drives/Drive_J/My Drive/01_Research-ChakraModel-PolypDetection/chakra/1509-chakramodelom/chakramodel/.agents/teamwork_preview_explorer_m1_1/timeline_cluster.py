import json
from collections import defaultdict

data = json.load(open('OM_rama_krish_convo.json', 'r', encoding='utf-8'))

by_date = defaultdict(list)
for d in data:
    ts = d.get('timestamp', 'Unknown')
    date = ts.split('T')[0] if 'T' in ts else ts
    by_date[date].append(d)

for date in sorted(by_date.keys()):
    convs = by_date[date]
    print(f"==================================================")
    print(f"DATE: {date} (Total: {len(convs)} conversations)")
    print(f"==================================================")
    
    # Collect distinct topics/keywords
    topics = []
    for c in convs:
        s = c.get('summary', '')
        # pick first sentence or 100 chars
        first_line = s.strip().split('\n')[0][:100]
        topics.append(first_line)
    
    # Show up to 5 representative samples
    for i, t in enumerate(topics[:6]):
        print(f"  [{i+1}] {t}")
    if len(topics) > 6:
        print(f"  ... and {len(topics) - 6} more conversations")
    print()
