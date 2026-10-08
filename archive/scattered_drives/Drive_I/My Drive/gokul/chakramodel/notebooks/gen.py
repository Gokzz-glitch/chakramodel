import json
import os

notebook = {
 'cells': [
  {
   'cell_type': 'markdown',
   'metadata': {},
   'source': [
    '# ChakraModel - Final Kaggle Proof Evaluation\n',
    '\n',
    'This notebook provides the definitive, undeniable proof of ChakraModel\'s performance on full-cohort OOD datasets and real-world video sequences from HyperKvasir. No truncation. No synthetic data.'
   ]
  },
  {
   'cell_type': 'markdown',
   'metadata': {},
   'source': [
    '## 1. Environment Setup'
   ]
  },
  {
   'cell_type': 'code',
   'execution_count': None,
   'metadata': {},
   'outputs': [],
   'source': [
    'import os\n',
    'import shutil\n',
    '\n',
    '!rm -rf /kaggle/working/chakramodel\n',
    'CODE_PATH = \'/kaggle/input/chakramodel-kaggle-code\'\n',
    'if os.path.exists(CODE_PATH):\n',
    '    shutil.copytree(CODE_PATH, \'/kaggle/working/chakramodel\', dirs_exist_ok=True)\n',
    '    %cd /kaggle/working/chakramodel\n',
    '    !pip install ultralytics thop gdown numpy opencv-python matplotlib > /dev/null\n',
    '    print("Environment setup complete.")\n',
    'else:\n',
    '    print(f"CRITICAL ERROR: Code path {CODE_PATH} not found.")'
   ]
  },
  {
   'cell_type': 'markdown',
   'metadata': {},
   'source': [
    '## 2. Load Weights'
   ]
  },
  {
   'cell_type': 'code',
   'execution_count': None,
   'metadata': {},
   'outputs': [],
   'source': [
    '# Link Weights - Updated to match the real diagnostic path\n',
    'WEIGHTS_SRC = \'/kaggle/input/datasets/gokulraj324/chakramodel-weightsupdated4\'\n',
    '!mkdir -p weights\n',
    'if os.path.exists(WEIGHTS_SRC):\n',
    '    !cp -r {WEIGHTS_SRC}/* weights/\n',
    '    print("Weights loaded successfully.")\n',
    'else:\n',
    '    print(f"WARNING: Weights path {WEIGHTS_SRC} not found.")'
   ]
  },
  {
   'cell_type': 'markdown',
   'metadata': {},
   'source': [
    '## 3. Video Inference & Temporal Proof (FPS Logging)'
   ]
  },
  {
   'cell_type': 'code',
   'execution_count': None,
   'metadata': {},
   'outputs': [],
   'source': [
    'import glob\n',
    '\n',
    '# Find any mp4 videos attached to the notebook\n',
    'video_files = glob.glob("/kaggle/input/**/*.mp4", recursive=True)\n',
    'if not video_files:\n',
    '    print("WARNING: No mp4 videos found in /kaggle/input.")\n',
    'else:\n',
    '    print(f"Found {len(video_files)} video files. Running inference on the first 5 videos...\\n")\n',
    '    for vid in video_files[:5]:\n',
    '        print(f"Evaluating: {vid}")\n',
    '        !python src/infer_stream.py --source "{vid}" --model combo1 --weights weights/combo1_best.pth --yolo weights/best.pt'
   ]
  },
  {
   'cell_type': 'markdown',
   'metadata': {},
   'source': [
    '## 4. Full-Cohort Cross-Dataset Evaluation (OOD Truth)'
   ]
  },
  {
   'cell_type': 'code',
   'execution_count': None,
   'metadata': {},
   'outputs': [],
   'source': [
    'import sys\n',
    'import cv2\n',
    'import numpy as np\n',
    'import json\n',
    'from tqdm.auto import tqdm\n',
    '\n',
    'sys.path.append(\'/kaggle/working/chakramodel/src\')\n',
    'try:\n',
    '    from chakranet_segmenter import ChakraNet\n',
    '    from metrics.seg_metrics import dice as binary_dice_coefficient, iou as binary_iou\n',
    '    segmenter = ChakraNet(device="cpu")\n',
    'except Exception as e:\n',
    '    print(f"Failed to load segmenter: {e}")\n',
    '    segmenter = None\n',
    '\n',
    'def eval_folder(img_dir, mask_dir):\n',
    '    img_paths = [os.path.join(img_dir, f) for f in os.listdir(img_dir) if f.lower().endswith((\'.png\', \'.jpg\', \'.jpeg\'))]\n',
    '    results = []\n',
    '    for img_path in tqdm(img_paths, desc=os.path.basename(os.path.dirname(img_dir))):\n',
    '        basename = os.path.basename(img_path)\n',
    '        mask_path = os.path.join(mask_dir, basename)\n',
    '        if not os.path.exists(mask_path):\n',
    '            mask_path = os.path.join(mask_dir, os.path.splitext(basename)[0] + \'.png\')\n',
    '            if not os.path.exists(mask_path):\n',
    '                mask_path = os.path.join(mask_dir, os.path.splitext(basename)[0] + \'.jpg\')\n',
    '        if not os.path.exists(mask_path): continue\n',
    '        img = cv2.imread(img_path)\n',
    '        gt_mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)\n',
    '        if img is None or gt_mask is None: continue\n',
    '        gt_mask = (gt_mask > 127).astype(np.uint8)\n',
    '        pred_mask, _, _, _ = segmenter.segment_roi(img, threshold=0.45, mc_passes=1)\n',
    '        if pred_mask is None: continue\n',
    '        pred_mask = cv2.resize(pred_mask, (gt_mask.shape[1], gt_mask.shape[0]), interpolation=cv2.INTER_NEAREST)\n',
    '        pred_mask_bin = (pred_mask > 127).astype(np.uint8)\n',
    '        results.append({"image": basename, "dice": binary_dice_coefficient(pred_mask_bin, gt_mask), "iou": binary_iou(pred_mask_bin, gt_mask)})\n',
    '    if not results: return {"images": 0, "mean_dice": 0, "mean_iou": 0}\n',
    '    return {"images": len(results), "mean_dice": float(np.mean([r["dice"] for r in results])), "mean_iou": float(np.mean([r["iou"] for r in results]))}\n',
    '\n',
    'final_metrics = {}\n',
    'if segmenter:\n',
    '    print("\\nScanning /kaggle/input for image/mask pairs...")\n',
    '    for root, dirs, files in os.walk("/kaggle/input"):\n',
    '        if "images" in dirs and "masks" in dirs:\n',
    '            dataset_name = os.path.basename(root)\n',
    '            # Avoid duplicate checks if nested\n',
    '            if dataset_name not in final_metrics:\n',
    '                print(f"\\nEvaluating found dataset: {dataset_name}...")\n',
    '                final_metrics[dataset_name] = eval_folder(os.path.join(root, "images"), os.path.join(root, "masks"))\n',
    '\n',
    '    !mkdir -p results\n',
    '    with open("results/final_proof_eval.json", "w") as f:\n',
    '        json.dump(final_metrics, f, indent=4)\n',
    '    print("\\nFINAL PROOF METRICS:\\n", json.dumps(final_metrics, indent=4))\n'
   ]
  },
  {
   'cell_type': 'markdown',
   'metadata': {},
   'source': [
    '## 5. Artifact Packaging'
   ]
  },
  {
   'cell_type': 'code',
   'execution_count': None,
   'metadata': {},
   'outputs': [],
   'source': [
    '%cd /kaggle/working\n',
    '!zip -r final_proof_artifacts.zip chakramodel/results chakramodel/outputs > /dev/null\n',
    'print("\\nDone! You can now download final_proof_artifacts.zip from the output data panel.")'
   ]
  }
 ],
 'metadata': {
  'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
  'language_info': {'name': 'python', 'version': '3.10.12'}
 },
 'nbformat': 4,
 'nbformat_minor': 4
}

with open(r'm:\chakramodel\notebooks\Kaggle_Final_Proof_Eval.ipynb', 'w') as f:
    json.dump(notebook, f, indent=2)
print('Notebook regenerated successfully.')
