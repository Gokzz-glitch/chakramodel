import json
from pathlib import Path

report = sorted(Path('results/metrics').glob('integrity_report_*.json'))[-1]
with open(report, encoding='utf-8') as f:
    data = json.load(f)

img_failures = [fa for fa in data['failures'] if fa['gate'] == 'intra_split_duplicate_image']
mask_failures = [fa for fa in data['failures'] if fa['gate'] == 'intra_split_duplicate_mask']

print('=== DUPLICATE IMAGE GROUPS BY DATASET ===')
by_dataset = {}
for fa in img_failures:
    paths = fa['paths']
    dataset = Path(paths[0]).parts[-3]
    if dataset not in by_dataset:
        by_dataset[dataset] = []
    frame_nums = sorted([int(Path(p).stem) for p in paths])
    by_dataset[dataset].append({
        'sha256_prefix': fa['sha256'][:16],
        'frame_numbers': frame_nums,
        'byte_confirmed': fa['byte_confirmed'],
    })

for ds, groups in by_dataset.items():
    print('\n  Dataset: {}  ({} duplicate groups)'.format(ds, len(groups)))
    for g in groups:
        frames = g['frame_numbers']
        gap = max(frames) - min(frames) if len(frames) > 1 else 0
        print('    SHA={}...  frames={}  max_gap={}'.format(
            g['sha256_prefix'], frames, gap))

print()
print('=== DUPLICATE MASK GROUPS BY DATASET ===')
by_dataset_m = {}
for fa in mask_failures:
    paths = fa['paths']
    dataset = Path(paths[0]).parts[-2]
    if dataset not in by_dataset_m:
        by_dataset_m[dataset] = []
    frame_nums = sorted([int(Path(p).stem) for p in paths])
    by_dataset_m[dataset].append({
        'sha256_prefix': fa['sha256'][:16],
        'frame_numbers': frame_nums,
        'byte_confirmed': fa['byte_confirmed'],
    })

for ds, groups in by_dataset_m.items():
    print('\n  Dataset: {}  ({} duplicate groups)'.format(ds, len(groups)))
    for g in groups:
        frames = g['frame_numbers']
        gap = max(frames) - min(frames) if len(frames) > 1 else 0
        print('    SHA={}...  frames={}  max_gap={}'.format(
            g['sha256_prefix'], frames, gap))

print()
print('CRITICAL: Are any of these in train or val?')
train_val_dups = [fa for fa in data['failures'] 
                  if fa['gate'] in ('intra_split_duplicate_image', 'intra_split_duplicate_mask')
                  and fa['role'] in ('train', 'val')]
print('  train/val intra-split duplicates: {}'.format(len(train_val_dups)))

test_dups = [fa for fa in data['failures']
             if fa['gate'] in ('intra_split_duplicate_image', 'intra_split_duplicate_mask')
             and fa['role'] not in ('train', 'val')]
print('  test-only intra-split duplicates: {}'.format(len(test_dups)))
for fa in test_dups:
    print('    role={} gate={}'.format(fa['role'], fa['gate']))
