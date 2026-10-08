import json, re

nb = json.load(open(r'J:\My Drive\downloads\chakramodel_v10_eval.ipynb', 'r', encoding='utf-8'))
cells = nb['cells']

checks = [
    ('PolypDB/BKAI/NBI removed', lambda src: 'BKAI/NBI/images' not in src),
    ('NBI removal comment present', lambda src: 'PolypDB/BKAI/NBI REMOVED' in src),
    ('smart_join used in run_image_ds', lambda src: 'smart_join(root' in src),
    ('_find_polypgen_frame_pairs defined', lambda src: '_find_polypgen_frame_pairs' in src),
    ('data_C loop present', lambda src: 'data_C' in src and 'images_' in src),
    ('sequenceData/positive handled', lambda src: 'sequenceData' in src and 'positive' in src),
    ('segment_roi tuple unpacking fixed', lambda src: 'result[0]' in src and 'isinstance(result, tuple)' in src),
    ('fallback=False for video', lambda src: 'fallback=False' in src),
    ('fallback=True for image', lambda src: 'fallback=True' in src),
    ('leakage guard load_train_manifest', lambda src: 'load_train_manifest' in src),
    ('TRAIN_MANIFEST in evaluate_image_dataset', lambda src: 'TRAIN_MANIFEST' in src),
    ('smoke test for segment_roi', lambda src: 'smoke test' in src),
    ('ChakraNet img_size=384', lambda src: '384, 384' in src),
    ('4-tuple assertion in smoke test', lambda src: 'len(_result) == 4' in src),
]

full_src = '\n'.join(''.join(c['source']) for c in cells)

print('=== NOTEBOOK CORRECTNESS CHECKS ===')
all_pass = True
for name, fn in checks:
    passed = fn(full_src)
    status = 'PASS' if passed else 'FAIL'
    if not passed:
        all_pass = False
    print(f'  [{status}] {name}')

print()
print('Overall:', 'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED')
print(f'Total cells: {len(cells)} (13 expected)')
