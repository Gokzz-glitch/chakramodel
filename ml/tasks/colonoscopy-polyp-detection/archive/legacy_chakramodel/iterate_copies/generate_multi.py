import os
import nbformat as nbf

with open('m:/chakramodel/kaggle_hardened_pipeline.py', 'r') as f:
    lines = f.readlines()

new_script = []
for line in lines[:24]:
    new_script.append(line)

new_script.append("""
# We will sweep across multiple thresholds to find the optimum!
CONFIDENCE_THRESHOLDS = [0.25, 0.40, 0.50, 0.65, 0.80]

# ==========================================
# DATASET CONFIGURATION
# ==========================================
# To evaluate a new dataset, just add a new line below:
# 'YourDatasetName': '/kaggle/input/path-to-your-dataset-folder'
# If a path doesn't exist or is empty, the script will safely skip it.

EVAL_DATASETS = {
    'CVC-ClinicDB': '/kaggle/input/chakramodel-evaluation-datasets/cvc-clinicdb',
    'CVC-300': '/kaggle/input/chakramodel-evaluation-datasets/cvc-300',
    'ETIS-Larib': '/kaggle/input/chakramodel-evaluation-datasets/etis-laribpolypdb'
    
    # Example of adding a new dataset (remove the # to enable):
    # 'Kvasir': '/kaggle/input/hyperkvasir-dataset-first-half-ld-dataset',
}
# ==========================================
""")

for line in lines[33:143]:
    new_script.append(line)

new_script.append("""
# Loop over all defined datasets
for ds_name, dataset_path in EVAL_DATASETS.items():
    print(f"\\n{'='*50}")
    print(f"EVALUATING DATASET: {ds_name}")
    print(f"{'-'*50}")
    
    if not os.path.exists(dataset_path):
        print(f"SKIPPING {ds_name} - Path not found: {dataset_path}")
        continue
""")

for line in lines[144:]:
    new_script.append('    ' + line)

with open('m:/chakramodel/kaggle_hardened_pipeline_multi_final.py', 'w') as f:
    f.writelines(new_script)

nb = nbf.v4.new_notebook()
with open('m:/chakramodel/kaggle_hardened_pipeline_multi_final.py', 'r') as f:
    code = f.read()
nb['cells'] = [nbf.v4.new_code_cell(code)]
nbf.write(nb, 'm:/chakramodel/kaggle_hardened_pipeline_multi_final.ipynb')
