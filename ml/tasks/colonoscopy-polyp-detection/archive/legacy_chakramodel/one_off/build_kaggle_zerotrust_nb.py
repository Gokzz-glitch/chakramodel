import os
import zipfile
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

# 1. Create the Kaggle_ZeroTrust_Code.zip
code_zip = "Kaggle_ZeroTrust_Code.zip"
with zipfile.ZipFile(code_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    for folder in ['src', '.agents/verification']:
        for root, dirs, files in os.walk(folder):
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            for file in files:
                if file.endswith(('.pyc', '.pt', '.pth')):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=".")
                zf.write(file_path, arcname)
                
    # Also explicitly add metrics_engine_v2.py which is at the root
    if os.path.exists("metrics_engine_v2.py"):
        zf.write("metrics_engine_v2.py", "metrics_engine_v2.py")
        print("Added metrics_engine_v2.py")

print(f"Created {code_zip} successfully.")

# 2. Generate the Notebook
nb = new_notebook()

nb.cells.append(new_markdown_cell(
    "# 🔒 Zero-Trust Supervised Verification (Kaggle Edition)\n\n"
    "This notebook unpacks the ChakraModel zero-trust verification harness and runs it on the Kaggle datasets. "
    "By using Kaggle's dual-GPU environment, we can rapidly process massive datasets like HyperKvasir and SUN-SEG."
))

# Environment Setup
nb.cells.append(new_code_cell(
    "!pip install -q ultralytics timm albumentations opencv-python-headless"
))

# Unpack Code
nb.cells.append(new_code_cell(
    "import os\n"
    "import shutil\n"
    "import subprocess\n\n"
    "# Extract the zero-trust code bundle (assuming it's attached as a dataset or uploaded to working directory)\n"
    "zip_path = None\n"
    "for p in ['/kaggle/working/Kaggle_ZeroTrust_Code.zip', '/kaggle/input/Kaggle_ZeroTrust_Code.zip']:\n"
    "    if os.path.exists(p):\n"
    "        zip_path = p\n"
    "        break\n"
    "if not zip_path:\n"
    "    # Search recursively in input\n"
    "    for root, dirs, files in os.walk('/kaggle/input'):\n"
    "        if 'Kaggle_ZeroTrust_Code.zip' in files:\n"
    "            zip_path = os.path.join(root, 'Kaggle_ZeroTrust_Code.zip')\n"
    "            break\n\n"
    "if zip_path:\n"
    "    print(f'Unpacking code from {zip_path}')\n"
    "    !unzip -q -o \"{zip_path}\" -d /kaggle/working/\n"
    "else:\n"
    "    print('WARNING: Kaggle_ZeroTrust_Code.zip not found! Please attach it.')\n"
))

# Link Weights
nb.cells.append(new_code_cell(
    "# Link model weights to /kaggle/working/weights so the script finds them\n"
    "os.makedirs('/kaggle/working/weights', exist_ok=True)\n"
    "weight_targets = {'chakra_transformer_best.pth', 'best.pt'}\n"
    "found_weights = set()\n"
    "for root, dirs, files in os.walk('/kaggle/input'):\n"
    "    for f in files:\n"
    "        if f in weight_targets and f not in found_weights:\n"
    "            src = os.path.join(root, f)\n"
    "            dst = os.path.join('/kaggle/working/weights', f)\n"
    "            if not os.path.exists(dst):\n"
    "                shutil.copy(src, dst)\n"
    "            found_weights.add(f)\n"
    "            print(f'Linked {f} from {src}')\n\n"
    "if len(found_weights) < 2:\n"
    "    print('WARNING: Missing some weights! Ensure both chakra_transformer_best.pth and best.pt are uploaded.')\n"
))

# Execute Verification Harness
nb.cells.append(new_code_cell(
    "import glob\n\n"
    "# The 5 verified dataset folders uploaded so far (from Google Sheet)\n"
    "target_datasets = [\n"
    "    'LDPolypVideo_Polyp_Raw',\n"
    "    'EndoScene_CVC300_Polyp_Raw',\n"
    "    'PICCOLO_Dataset_Polyp_Raw',\n"
    "    'PolypDB_Polyp_Raw',\n"
    "    'HyperKvasir_Segmented_Raw'\n"
    "]\n\n"
    "print('================================================')\n"
    "print('   RUNNING ZERO-TRUST SUPERVISED VERIFICATION')\n"
    "print('================================================\\n')\n\n"
    "for dataset_name in target_datasets:\n"
    "    # Find the dataset path in /kaggle/input\n"
    "    # Because Kaggle lowercases dataset folder names, we do a case-insensitive search\n"
    "    dataset_path = None\n"
    "    for root, dirs, files in os.walk('/kaggle/input'):\n"
    "        for d in dirs:\n"
    "            if d.lower().replace('-', '_') == dataset_name.lower().replace('-', '_'):\n"
    "                dataset_path = os.path.join(root, d)\n"
    "                break\n"
    "        if dataset_path: break\n\n"
    "    if not dataset_path:\n"
    "        print(f'\\n[SKIPPED] Dataset {dataset_name} not found in /kaggle/input (Did you attach it?)')\n"
    "        continue\n\n"
    "    print(f'\\n>> VERIFYING {dataset_name} at {dataset_path}')\n"
    "    \n"
    "    # The harness expects an absolute path and passes it via DATASET_ROOT\n"
    "    env = os.environ.copy()\n"
    "    env['DATASET_ROOT'] = dataset_path\n"
    "    \n"
    "    # Fix working directory for imports to resolve correctly\n"
    "    cwd = '/kaggle/working'\n"
    "    script_harness = '.agents/verification/supervised_verification_harness.py'\n"
    "    script_eval = '.agents/verification/verify_eval.py'\n\n"
    "    cmd = [\n"
    "        'python', script_harness,\n"
    "        '--dataset-root', dataset_path,\n"
    "        '--script', script_eval\n"
    "    ]\n\n"
    "    try:\n"
    "        # Execute the harness natively\n"
    "        subprocess.run(cmd, env=env, cwd=cwd, check=True)\n"
    "    except subprocess.CalledProcessError as e:\n"
    "        print(f'\\n[ERROR] Verification failed for {dataset_name}')\n\n"
    "print('\\n================================================')\n"
    "print('VERIFICATION COMPLETE! Check /kaggle/working/verification_verdicts for Signed Cards.')\n"
    "!ls -la /kaggle/working/verification_verdicts\n"
))

out = "Kaggle_ZeroTrust_Verification.ipynb"
with open(out, 'w', encoding='utf-8') as f:
    nbformat.write(nb, f)
print(f"Created {out} successfully.")
