import os
import sys
from pathlib import Path
import torch

root = Path(r"m:\chakramodel")
weights_to_check = [
    root / "yolov8x.pt",
    root / "weights" / "best.pt",
    root / "weights" / "chakra_transformer_best.pth",
    root / "weights" / "chakra_transformer_best.pth.bak",
    root / "weights" / "combo1_best.pth",
    root / "weights" / "combo2_best.pth",
    root / "weights" / "pranet_kvasir_best.pth",
    root / "weights" / "yolo26n.pt",
    root / "weights" / "yolo_custom_best.pt",
    root / "weights" / "yolov8n.pt",
    root / "kaggle_bundle" / "weights" / "best.pt",
    root / "kaggle_bundle" / "weights" / "pranet_kvasir_best.pth",
    root / "kaggle_outputs" / "weights" / "chakra_transformer_best.pth",
    root / "outputs" / "polyp_yolov8x" / "weights" / "best.pt",
    root / "runs" / "detect" / "ChakraModel_Runs" / "polyp_detection_v1" / "weights" / "best.pt"
]

print("="*90)
print(f"{'FILE PATH':<50} | {'SIZE (MB)':<10} | {'TYPE':<20}")
print("="*90)

for wp in weights_to_check:
    if not wp.exists():
        print(f"{str(wp.relative_to(root)):<50} | NOT FOUND")
        continue
    size_mb = wp.stat().st_size / (1024 * 1024)
    print(f"{str(wp.relative_to(root)):<50} | {size_mb:<10.2f} | ", end="")
    try:
        data = torch.load(str(wp), map_location='cpu')
        if isinstance(data, dict):
            keys = list(data.keys())
            if 'model' in data:
                print(f"YOLO Checkpoint dict (keys: {keys[:5]})")
            elif 'model_state_dict' in data:
                print(f"Wrapped dict ('model_state_dict')")
            else:
                total_params = sum(v.numel() for v in data.values() if isinstance(v, torch.Tensor))
                print(f"State Dict ({len(keys)} keys, {total_params:,} params, {total_params/1e6:.2f}M)")
        elif hasattr(data, 'state_dict'):
            sd = data.state_dict()
            total_params = sum(v.numel() for v in sd.values())
            print(f"Model Object ({total_params:,} params, {total_params/1e6:.2f}M)")
        else:
            print(f"Object: {type(data)}")
    except Exception as e:
        print(f"Error reading: {e}")

print("="*90)
