import json
from pathlib import Path
from collections import defaultdict

report_path = sorted(Path('results/overlays').glob('overlay_audit_*.json'))[-1]
print('Report:', report_path)
with open(report_path, encoding='utf-8') as f:
    data = json.load(f)

s = data['summary']
print()
print('=== SUMMARY ===')
print('  total_unique_images_analysed:', s['total_unique_images_analysed'])
print('  total_clean    :', s['total_clean'])
print('  total_overlay  :', s['total_overlay'])
print('  total_uncertain:', s['total_uncertain'])
print('  elapsed_seconds:', s['elapsed_seconds'])
print('  training_blocked:', s['training_blocked'])

print()
print('=== PER-ROLE COUNTS ===')
for role, r in data['per_role'].items():
    if 'error' in r:
        print(f'  {role}: ERROR - {r["error"]}')
        continue
    print(f'  {role}: pairs={r["total_pairs"]} unique_images={r["unique_images"]}  '
          f'CLEAN={r["clean_count"]}  OVERLAY={r["overlay_count"]}  '
          f'UNCERTAIN={r["uncertain_count"]}  UNREADABLE={r["unreadable_count"]}')

print()
print('=== TRAIN OVERLAY PATHS ===')
tr = data['per_role'].get('train', {})
overlays = tr.get('confirmed_overlay', [])
print(f'  Count: {len(overlays)}')
for o in overlays[:20]:
    print(f'  score={o["total_score"]}  reason={o["reason"]}')
    print(f'    img:  {o["image_path"]}')
    print(f'    mask: {o["mask_path"]}')

print()
print('=== VAL OVERLAY PATHS (first 30) ===')
vr = data['per_role'].get('val', {})
val_overlays = vr.get('confirmed_overlay', [])
print(f'  Count: {len(val_overlays)}')
for o in val_overlays[:30]:
    print(f'  score={o["total_score"]}  reason={o["reason"]}')
    print(f'    img:  {o["image_path"]}')

print()
print('=== TRAIN UNCERTAIN PATHS ===')
tr_uncertain = tr.get('uncertain_manual_review', [])
print(f'  Count: {len(tr_uncertain)}')
for o in tr_uncertain[:10]:
    print(f'  score={o["total_score"]}  {o["image_path"]}')

print()
print('=== VAL UNCERTAIN PATHS ===')
val_uncertain = vr.get('uncertain_manual_review', [])
print(f'  Count: {len(val_uncertain)}')
for o in val_uncertain[:10]:
    print(f'  score={o["total_score"]}  {o["image_path"]}')

print()
print('=== CONTACT SHEET PATHS ===')
for role, r in data['per_role'].items():
    cs = r.get('contact_sheet_path', 'N/A')
    print(f'  {role}: {cs}')
flagged = s.get('flagged_contact_sheet', 'N/A')
print(f'  flagged_all: {flagged}')
