"""
Test Combo 6 Isolated
"""
import sys, os, nbformat, torch, torch.nn as nn, numpy as np
import torch.nn.functional as F
from torch.utils.data import Dataset, TensorDataset, DataLoader
from torch.cuda.amp import autocast
import timm

sys.stdout.reconfigure(encoding='utf-8')
NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"
nb_path = os.path.join(NOTEBOOKS_DIR, "Combo6_ChakraTransformer.ipynb")
nb = nbformat.read(nb_path, as_version=4)

ns = {"Dataset": Dataset, "DataLoader": DataLoader, "timm": timm, "F": F, "autocast": autocast, "torch": torch, "nn": nn, "np": np}

c4_lines = [l for l in nb.cells[4].source.splitlines() if not (l.strip().startswith('!') or l.strip().startswith('%'))]
c4_defs = [l for l in c4_lines if not (l.startswith("transformer_model = ") or l.startswith("dummy_tensor = ") or l.startswith("transformer_model.eval()") or l.startswith("with torch.no_grad():") or l.startswith("    dummy_logits =") or l.startswith("print(f\"✅ ChakraTransformer Architecture Verified"))]
exec('\n'.join(c4_defs), ns)

c5_lines = [l for l in nb.cells[5].source.splitlines() if not (l.strip().startswith('!') or l.strip().startswith('%'))]
c5_defs = [l for l in c5_lines if not (l.startswith("EPOCHS = ") or l.startswith("optimizer = ") or l.startswith("model = ") or l.startswith("for epoch in range") or l.startswith("print(f\"  Epochs:"))]
exec('\n'.join(c5_defs), ns)

c6_lines = [l for l in nb.cells[6].source.splitlines() if not (l.strip().startswith('!') or l.strip().startswith('%'))]
c6_defs = [l for l in c6_lines if not (l.startswith("calibrator = ") or l.startswith("calibrator.calibrate("))]
exec('\n'.join(c6_defs), ns)

ProgressiveDecoderBlock = ns["ProgressiveDecoderBlock"]
ChakraTransformerSegmenter = ns["ChakraTransformerSegmenter"]
ConformalCalibrator = ns["ConformalCalibrator"]
DiceFocalLoss = ns["DiceFocalLoss"]
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

print("1. Testing ProgressiveDecoderBlock...")
decoder_block = ProgressiveDecoderBlock(in_channels=1024, out_channels=512, dropout_p=0.10).to(device)
dummy_feat = torch.randn(2, 1024, 24, 24, device=device)
dec_out = decoder_block(dummy_feat)
assert dec_out.shape == (2, 512, 48, 48)
print("  Decoder block output OK:", dec_out.shape)

print("2. Testing ChakraTransformerSegmenter...")
model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=False).to(device)
model.train()
x = torch.randn(2, 3, 384, 384, requires_grad=True, device=device)
out = model(x)
assert out.shape == (2, 1, 384, 384)
criterion = DiceFocalLoss()
target = torch.randint(0, 2, (2, 1, 384, 384), device=device).float()
loss = criterion(out, target)
loss.backward()
assert x.grad is not None
print(f"  ViT-Large Model & Loss OK. Loss={loss.item():.4f}")

print("3. Testing ConformalCalibrator...")
calibrator = ConformalCalibrator(alpha_levels=[0.10, 0.05])
# Create CPU tensors for calibration DataLoader
cal_probs = torch.randn(8, 1, 64, 64)
cal_masks = torch.randint(0, 2, (8, 1, 64, 64)).float()
cal_loader = DataLoader(TensorDataset(cal_probs, cal_masks), batch_size=4)

class MockModel(nn.Module):
    def forward(self, x):
        return x

calibrator.calibrate(MockModel(), cal_loader, device=device)
print("  Calibrated q_hats:", calibrator.q_hats)

prob_map = np.random.uniform(0, 1, (384, 384)).astype(np.float32)
inner, outer, band = calibrator.predict_conformal_bands(prob_map, alpha=0.05)
assert inner.shape == (384, 384) and outer.shape == (384, 384) and band.shape == (384, 384)
print(f"  Conformal Bands: Inner={inner.sum()}, Outer={outer.sum()}, Band={band.sum()}")

print("\n🎉 ALL COMBO 6 COMPONENTS TESTED AND VERIFIED 100% PASS!")
