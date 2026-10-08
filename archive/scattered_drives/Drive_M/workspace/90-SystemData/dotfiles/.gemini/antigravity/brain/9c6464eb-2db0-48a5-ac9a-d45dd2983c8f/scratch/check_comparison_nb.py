import json
nb = json.load(open(r'J:\My Drive\downloads\chakramodel_vit_vs_pranet_comparison.ipynb', encoding='utf-8'))
src = '\n'.join(''.join(c['source']) for c in nb['cells'])
checks = [
    ('No hardcoded Windows paths', 'M:\\\\chakramodel' not in src),
    ('Uses os.walk for dataset resolution', 'os.walk(INPUT_DIR)' in src),
    ('smart_join present', 'def smart_join' in src),
    ('ViT loaded via ChakraNet wrapper', 'from chakranet_segmenter import ChakraNet' in src),
    ('PraNet loaded inline (no hardcoded import)', 'class PraNetR101' in src),
    ('YOLO weights discovered dynamically', "f == 'best.pt'" in src),
    ('DDP prefix strip present', "'module.'" in src),
    ('fallback=True for image', 'fallback=True' in src),
    ('Dice + IoU computed', 'def dice_iou' in src),
    ('FPS measured per dataset', 'seg_fps' in src),
    ('Results saved to JSON', 'vit_vs_pranet_comparison.json' in src),
    ('cudnn benchmark ON', 'cudnn.benchmark' in src),
    ('TF32 enabled', 'allow_tf32' in src),
    ('Smoke test present', 'smoke test' in src),
    ('CVC-300 key present', 'endoscene-cvc300-polyp-raw-dataset' in src),
    ('chakramodel-evaluation-datasets key present', 'chakramodel-evaluation-datasets' in src),
    ('polypdb-polyp-raw key present', 'polypdb-polyp-raw' in src),
    ('PolypGen2021 key present', 'polypgen20021-video' in src),
    ('LDPolyp key present', 'ldpolypvideowithoutpolyps' in src),
    ('HyperKvasir video key present', 'hperkvasir-labeled-videos-part2-002' in src),
    ('CVC-Video key present', 'cvc-sample-video' in src),
]
print('=== COMPARISON NOTEBOOK INTEGRITY CHECKS ===')
all_pass = True
for name, result in checks:
    status = 'PASS' if result else 'FAIL'
    if not result:
        all_pass = False
    print(f'  [{status}] {name}')
print()
n_cells = len(nb['cells'])
print('Overall: ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED')
print(f'Total cells: {n_cells}')
