import json
import os

with open(r'm:\chakramodel\notebooks\Kaggle_Final_Proof_Eval.ipynb', 'r') as f:
    nb = json.load(f)

# Update Cell 2 (Environment Setup) to auto-detect CODE_PATH
nb['cells'][2]['source'] = [
    'import os\n',
    'import shutil\n',
    'import glob\n',
    '\n',
    '!rm -rf /kaggle/working/chakramodel\n',
    '\n',
    '# Auto-detect code path by looking for a known file (e.g. src/chakranet_segmenter.py)\n',
    'CODE_PATH = None\n',
    'for root, dirs, files in os.walk("/kaggle/input"):\n',
    '    if "chakranet_segmenter.py" in files and os.path.basename(root) == "src":\n',
    '        CODE_PATH = os.path.dirname(root)\n',
    '        break\n',
    '\n',
    'if CODE_PATH:\n',
    '    print(f"Found Code Dataset at: {CODE_PATH}")\n',
    '    shutil.copytree(CODE_PATH, "/kaggle/working/chakramodel", dirs_exist_ok=True)\n',
    '    %cd /kaggle/working/chakramodel\n',
    '    !pip install ultralytics thop gdown numpy opencv-python matplotlib > /dev/null\n',
    '    print("Environment setup complete.")\n',
    'else:\n',
    '    print("CRITICAL ERROR: Could not find the source code dataset. Please make sure ChakraModel_Kaggle_Code is attached.")\n'
]

# Update Cell 4 (Load Weights) to auto-detect WEIGHTS_SRC
nb['cells'][4]['source'] = [
    '# Link Weights - Auto-detect weights path by looking for chakra_transformer_best.pth\n',
    'WEIGHTS_SRC = None\n',
    'for root, dirs, files in os.walk("/kaggle/input"):\n',
    '    if "chakra_transformer_best.pth" in files:\n',
    '        WEIGHTS_SRC = root\n',
    '        break\n',
    '\n',
    '!mkdir -p weights\n',
    'if WEIGHTS_SRC:\n',
    '    print(f"Found Weights Dataset at: {WEIGHTS_SRC}")\n',
    '    !cp -r {WEIGHTS_SRC}/* weights/\n',
    '    print("Weights loaded successfully.")\n',
    'else:\n',
    '    print("WARNING: Could not find chakra_transformer_best.pth in any attached dataset.")\n'
]

with open(r'm:\chakramodel\notebooks\Kaggle_Final_Proof_Eval.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print('Updated Kaggle_Final_Proof_Eval.ipynb to be 100% path-agnostic.')
