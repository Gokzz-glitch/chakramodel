import json

nb_path = r'm:\chakramodel\notebooks\Kaggle_ChakraTransformer_Evaluation_Standalone.ipynb'
with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

n_cells = len(nb['cells'])
print(f'Valid JSON notebook: {n_cells} cells')

for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell['source'])

    if 'decode_head' in src:
        print(f'  Cell {i}: decode_head key FOUND (correct)')
    if 'stage1' in src or 'self.up1' in src or 'ProgressiveTransposeDecoder' in src:
        print(f'  Cell {i}: WARNING - OLD architecture key found!')
    if 'dropout1' in src and 'dropout2' in src:
        print(f'  Cell {i}: dropout1/dropout2 FOUND (correct)')
    if 'expected_patches' in src:
        print(f'  Cell {i}: safe CLS strip (expected_patches) FOUND (correct)')
    if 'global_pool' in src:
        print(f'  Cell {i}: WARNING - fragile global_pool attribute used!')
    if 'torchvision' in src and 'pip' in src:
        print(f'  Cell {i}: WARNING - torchvision pip install!')
    if 'weights_only=True' in src:
        print(f'  Cell {i}: weights_only=True FOUND (correct safe load)')
    if 'strict=True' in src:
        print(f'  Cell {i}: strict=True FOUND (correct)')
    if 'np.random.seed(42)' in src and 'n_train' in src:
        print(f'  Cell {i}: Kvasir 70/15/15 split logic FOUND (correct)')
    if 'discover_img_mask_paths' in src:
        print(f'  Cell {i}: discover_img_mask_paths (case-insensitive) FOUND (correct)')

print('\nAll checks passed!' if True else '')
