import json

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

new_source = [
    'import os\n',
    '\n',
    'DATASET_ROOT = "/kaggle/input/"\n',
    '\n',
    '# Search in lowercase to beat Kaggle\'s auto-lowercasing\n',
    'DATASET_TARGETS = {\n',
    '    "Kvasir-SEG": "kvasir-seg",\n',
    '    "CVC-ClinicDB": "cvc-clinicdb",\n',
    '    "CVC-ColonDB": "cvc-colondb",\n',
    '    "CVC-300": "cvc-300",\n',
    '    "ETIS-Larib": "etis-larib",\n',
    '    "ClinicVideoDB": "cvc-sample-video" # Looks for the zip we uploaded\n',
    '}\n',
    '\n',
    'IMAGE_DATASETS = {}\n',
    'VIDEO_DATASET = None\n',
    'YOLO_WEIGHTS = None\n',
    'VIT_WEIGHTS = None\n',
    '\n',
    'print("Scanning /kaggle/input/ for datasets...")\n',
    'for root, dirs, files in os.walk(DATASET_ROOT):\n',
    '    lower_dirs = [d.lower() for d in dirs]\n',
    '    for name, target_dir in DATASET_TARGETS.items():\n',
    '        if target_dir in lower_dirs:\n',
    '            actual_dir = dirs[lower_dirs.index(target_dir)]\n',
    '            path = os.path.join(root, actual_dir)\n',
    '            if name == "ClinicVideoDB":\n',
    '                VIDEO_DATASET = path\n',
    '            else:\n',
    '                IMAGE_DATASETS[name] = path\n',
    '                \n',
    '    for f in files:\n',
    '        if f.lower() == "best.pt":\n',
    '            YOLO_WEIGHTS = os.path.join(root, f)\n',
    '        elif f.lower() == "chakra_transformer_best.pth":\n',
    '            VIT_WEIGHTS = os.path.join(root, f)\n',
    '\n',
    'print("\\n--- Detection Results ---")\n',
    'for name in ["Kvasir-SEG", "CVC-ClinicDB", "CVC-ColonDB", "CVC-300", "ETIS-Larib"]:\n',
    '    print(f"{name}: {\'Found at \' + IMAGE_DATASETS[name] if name in IMAGE_DATASETS else \'NOT FOUND\'}")\n',
    '\n',
    'print(f"\\nVideo Dataset (ClinicVideoDB): {\'Found at \' + VIDEO_DATASET if VIDEO_DATASET else \'NOT FOUND\'}")\n',
    'print(f"YOLOv8 Weights: {\'Found at \' + YOLO_WEIGHTS if YOLO_WEIGHTS else \'NOT FOUND\'}")\n',
    'print(f"ViT-Large Weights: {\'Found at \' + VIT_WEIGHTS if VIT_WEIGHTS else \'NOT FOUND\'}")\n'
]

# Update the exact cell containing the dataset linking logic
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and any('DATASET_ROOT = "/kaggle/input/"' in line for line in cell['source']):
        cell['source'] = new_source
        break

with open('M:/chakramodel/ChakraModel_Video_Evaluation_Kaggle.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)
