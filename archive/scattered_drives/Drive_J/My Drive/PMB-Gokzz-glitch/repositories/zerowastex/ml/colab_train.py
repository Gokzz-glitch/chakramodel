# Zer0wasteX — Google Colab Training Notebook
# Run this on Google Colab (free T4 GPU) to train your model
# Expected training time: ~2.5 hours for 150 epochs on T4
# Expected mAP@50: 88-93% on balanced 6-class Indian waste dataset
#
# Steps:
#   1. Open https://colab.research.google.com
#   2. New notebook → Runtime → Change runtime type → GPU (T4)
#   3. Paste each cell below and run in order

# ============================================================
# CELL 1 — Install dependencies
# ============================================================
# !pip install ultralytics albumentations roboflow kaggle -q

# ============================================================
# CELL 2 — Download TrashNet (public, no auth needed)
# ============================================================
# import gdown
# gdown.download(
#     "https://drive.google.com/uc?id=0B3P9oO5A3RvSUW9qTkFHdTR1Rms",
#     "trashnet.zip", quiet=False
# )
# !unzip -q trashnet.zip -d /content/trashnet

# ============================================================
# CELL 3 — Download Roboflow waste dataset (best for Indian waste)
# ============================================================
# from roboflow import Roboflow
# rf = Roboflow(api_key="YOUR_ROBOFLOW_API_KEY")
#
# # Option A: General waste classification (2500+ labelled images)
# project = rf.workspace("material-identification").project("waste-classification-ycyak")
# version = project.version(1)
# dataset_a = version.download("yolov8")
#
# # Option B: Indian-context garbage detection
# project2 = rf.workspace().project("garbage-classification-3")
# version2 = project2.version(2)
# dataset_b = version2.download("yolov8")

# ============================================================
# CELL 4 — Merge datasets into unified structure
# ============================================================
# import os, shutil
# from pathlib import Path
#
# # Create merged dataset directories
# for split in ["train", "val", "test"]:
#     Path(f"/content/merged/images/{split}").mkdir(parents=True, exist_ok=True)
#     Path(f"/content/merged/labels/{split}").mkdir(parents=True, exist_ok=True)
#
# # Copy each dataset split into merged/
# # Adjust source paths based on what was downloaded above
# for ds_root in ["/content/dataset_a", "/content/dataset_b"]:
#     for split in ["train", "valid", "test"]:
#         target_split = "val" if split == "valid" else split
#         src_imgs = Path(ds_root) / split / "images"
#         src_lbls = Path(ds_root) / split / "labels"
#         if src_imgs.exists():
#             for f in src_imgs.glob("*"):
#                 shutil.copy(f, f"/content/merged/images/{target_split}/{f.name}")
#             for f in src_lbls.glob("*"):
#                 shutil.copy(f, f"/content/merged/labels/{target_split}/{f.name}")
#
# # Count images
# for split in ["train", "val", "test"]:
#     n = len(list(Path(f"/content/merged/images/{split}").glob("*")))
#     print(f"  {split}: {n} images")

# ============================================================
# CELL 5 — Create dataset.yaml
# ============================================================
# yaml_content = """
# path: /content/merged
# train: images/train
# val:   images/val
# test:  images/test
# nc: 6
# names:
#   0: organic
#   1: plastic
#   2: paper
#   3: metal
#   4: glass
#   5: hazardous
# """
# with open("/content/dataset.yaml", "w") as f:
#     f.write(yaml_content)
# print("dataset.yaml written")

# ============================================================
# CELL 6 — TRAIN (the main event)
# ============================================================
# from ultralytics import YOLO
#
# model = YOLO("yolov8m.pt")   # Medium variant — best accuracy/speed for our task
#
# results = model.train(
#     data="/content/dataset.yaml",
#     epochs=150,
#     imgsz=640,
#     batch=32,              # T4 can handle batch=32 at 640px
#     device="cuda",
#     optimizer="AdamW",
#     lr0=0.001,
#     lrf=0.01,
#     label_smoothing=0.1,  # critical for noisy real-world labels
#     dropout=0.0,
#     amp=True,             # mixed precision (2× faster)
#     cache=True,           # cache images in GPU VRAM
#     patience=30,          # early stop
#     plots=True,
#     name="zer0wastex_v1",
# )
# print(f"Best mAP@50: {results.results_dict['metrics/mAP50(B)'] * 100:.2f}%")

# ============================================================
# CELL 7 — Validate and get per-class metrics
# ============================================================
# metrics = model.val(data="/content/dataset.yaml", split="test")
# print(f"Test mAP@50   : {metrics.box.map50 * 100:.2f}%")
# print(f"Test Precision : {metrics.box.mp * 100:.2f}%")
# print(f"Test Recall    : {metrics.box.mr * 100:.2f}%")

# ============================================================
# CELL 8 — Export weights
# ============================================================
# # Download best.pt to your local machine
# from google.colab import files
# files.download("/content/runs/detect/zer0wastex_v1/weights/best.pt")
#
# # Also export to ONNX (for Raspberry Pi / Jetson deployment)
# model.export(format="onnx", simplify=True, opset=17)
# files.download("/content/runs/detect/zer0wastex_v1/weights/best.onnx")

# ============================================================
# AFTER TRAINING:
#   1. Place best.pt in Zer0wasteX/ml/weights/best.pt
#   2. Restart vision_service.py — it auto-detects and uses your model
#   3. Run: python evaluate.py --weights weights/best.pt --data dataset.yaml
# ============================================================
