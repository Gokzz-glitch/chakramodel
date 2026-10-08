import json
from pathlib import Path

report_path = sorted(Path('results/overlays').glob('overlay_audit_*.json'))[-1]
with open(report_path, encoding='utf-8') as f:
    data = json.load(f)

# Full train overlay list
tr = data['per_role'].get('train', {})
train_overlays = tr.get('confirmed_overlay', [])
print('=== ALL TRAIN OVERLAY CANDIDATES ({}) ==='.format(len(train_overlays)))
for o in train_overlays:
    print('  score={}  conf={}  reason={}'.format(o['total_score'], o['confidence'], o['reason']))
    print('    img:  {}'.format(o['image_path']))
    print('    mask: {}'.format(o['mask_path']))
print()

# Full val overlay list
vr = data['per_role'].get('val', {})
val_overlays = vr.get('confirmed_overlay', [])
print('=== ALL VAL OVERLAY CANDIDATES ({}) ==='.format(len(val_overlays)))
for o in val_overlays:
    print('  score={}  conf={}  reason={}'.format(o['total_score'], o['confidence'], o['reason']))
    print('    img:  {}'.format(o['image_path']))
    print('    mask: {}'.format(o['mask_path']))
print()

# Score distribution analysis - what drives the flags?
print('=== SCORE DISTRIBUTION (train overlays) ===')
from collections import Counter
score_dist = Counter(round(o['total_score']) for o in train_overlays)
for s, c in sorted(score_dist.items()):
    print('  score={}: {} images'.format(s, c))

print()
print('=== DOMINANT HEURISTICS IN TRAIN+VAL OVERLAYS ===')
h_counts = Counter()
for o in train_overlays + val_overlays:
    for h, s in o.get('heuristic_details', {}).items():
        # parse score from reason string
        pass
    # use reason field
    for part in o['reason'].split(', '):
        if 'score=' in part:
            h_name = part.split('(')[0]
            h_counts[h_name] += 1
for h, c in h_counts.most_common():
    print('  {}: {} occurrences'.format(h, c))

print()
print('=== TEST SET OVERLAY SUMMARY ===')
for role in ['test_kvasir', 'test_clinicdb', 'test_colondb', 'test_etis', 'test_cvc300']:
    r = data['per_role'].get(role, {})
    print('  {}: CLEAN={} OVERLAY={} UNCERTAIN={}'.format(
        role, r.get('clean_count', 'N/A'), r.get('overlay_count', 'N/A'), r.get('uncertain_count', 'N/A')))
