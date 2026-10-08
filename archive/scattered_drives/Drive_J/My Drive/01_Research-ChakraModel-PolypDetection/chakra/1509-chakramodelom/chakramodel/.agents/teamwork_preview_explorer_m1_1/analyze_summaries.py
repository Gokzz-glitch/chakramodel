import json

data = json.load(open('conversation_summaries.json', 'r', encoding='utf-8'))
print('Total conversations in conversation_summaries.json:', len(data))

# Search for key terms across summaries
keywords = ['hackathon', 'tata', 'pharma', 'genesis', 'jetson', 'edge', 'slam', 'conformal', 'topo', 'gan', 'bmad', 'reviewer', 'paper', 'pranet', 'vit', 'transformer', 'kvasir']
kw_counts = {k: 0 for k in keywords}
for d in data:
    s = d.get('summary', '').lower()
    for k in keywords:
        if k in s:
            kw_counts[k] += 1

print('Keyword mentions across conversations:')
for k, count in sorted(kw_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  - {k}: {count}")
