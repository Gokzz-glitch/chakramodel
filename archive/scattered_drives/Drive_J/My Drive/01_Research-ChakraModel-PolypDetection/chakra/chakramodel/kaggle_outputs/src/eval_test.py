import torch
from pathlib import Path
import sys
import numpy as np
import json

root = Path("m:/chakramodel")
sys.path.append(str(root / "src"))

from run_all_combos import make_loaders, ChakraNet, compute_metrics, DEVICE
from torch.cuda.amp import autocast

_, _, te_l = make_loaders(root, batch=8, size=448)

model = ChakraNet(channels=48, mc_dropout_p=0.15).to(DEVICE)
model.load_state_dict(torch.load(root / "weights" / "combo1_best.pth", map_location=DEVICE))
model.eval()

dices, ious, maes = [], [], []
with torch.no_grad(), autocast():
    for imgs, masks in te_l:
        imgs = imgs.to(DEVICE)
        out = model(imgs)
        if isinstance(out, tuple): out = out[0]
        probs = torch.sigmoid(out).float().cpu().numpy()
        for i in range(len(probs)):
            d, io, m = compute_metrics(probs[i,0], masks[i,0].numpy())
            dices.append(d)
            ious.append(io)
            maes.append(m)

test_dice = float(np.mean(dices))
test_iou = float(np.mean(ious))
test_mae = float(np.mean(maes))

print(f"Test Dice: {test_dice:.4f}")
print(f"Test IoU: {test_iou:.4f}")
print(f"Test MAE: {test_mae:.4f}")
