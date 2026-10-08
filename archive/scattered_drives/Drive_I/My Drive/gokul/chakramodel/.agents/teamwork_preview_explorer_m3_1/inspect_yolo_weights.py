import os
import sys
from pathlib import Path
import torch
from ultralytics import YOLO

root = Path(r"m:\chakramodel")
yolo_weights = [
    root / "yolov8x.pt",
    root / "weights" / "best.pt",
    root / "weights" / "yolov8n.pt",
    root / "weights" / "yolo26n.pt",
    root / "weights" / "yolo_custom_best.pt",
    root / "kaggle_bundle" / "weights" / "best.pt",
    root / "outputs" / "polyp_yolov8x" / "weights" / "best.pt",
    root / "runs" / "detect" / "ChakraModel_Runs" / "polyp_detection_v1" / "weights" / "best.pt"
]

print("="*100)
print(f"{'PATH':<55} | {'SIZE(MB)':<9} | {'PARAMS':<12} | {'CLASSES':<8} | {'LAYERS':<7}")
print("="*100)

for wp in yolo_weights:
    if not wp.exists():
        print(f"{str(wp.relative_to(root)):<55} | NOT FOUND")
        continue
    size_mb = wp.stat().st_size / (1024 * 1024)
    try:
        yolo = YOLO(str(wp))
        model = yolo.model
        n_params = sum(p.numel() for p in model.parameters())
        n_layers = len(list(model.modules()))
        nc = getattr(model, 'nc', getattr(model.yaml, 'get', lambda k, d=None: d)('nc', 'N/A') if hasattr(model, 'yaml') else 'N/A')
        # Check names
        names = getattr(model, 'names', getattr(yolo, 'names', 'N/A'))
        print(f"{str(wp.relative_to(root)):<55} | {size_mb:<9.2f} | {n_params:<12,} | {str(names):<8} | {n_layers:<7}")
    except Exception as e:
        # Fallback to torch.load with weights_only=False
        try:
            ckpt = torch.load(str(wp), map_location='cpu', weights_only=False)
            if 'model' in ckpt:
                m = ckpt['model']
                n_params = sum(p.numel() for p in m.parameters())
                print(f"{str(wp.relative_to(root)):<55} | {size_mb:<9.2f} | {n_params:<12,} | ckpt_dict | N/A")
            else:
                print(f"{str(wp.relative_to(root)):<55} | {size_mb:<9.2f} | Error parsing dict keys: {list(ckpt.keys())[:5]}")
        except Exception as e2:
            print(f"{str(wp.relative_to(root)):<55} | {size_mb:<9.2f} | Error: {e2}")

print("="*100)
