import os, cv2, torch
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from torch.amp import autocast
import timm

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}

class ChakraTransformerSegmenter(nn.Module):
    def __init__(self, backbone_name='vit_large_patch16_384', pretrained=False, num_classes=1):
        super(ChakraTransformerSegmenter, self).__init__()
        self.backbone = timm.create_model(backbone_name, pretrained=pretrained, features_only=False)
        self.embed_dim = self.backbone.embed_dim
        self.decode_head = nn.Sequential(
            nn.ConvTranspose2d(self.embed_dim, 256, kernel_size=4, stride=4),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.ConvTranspose2d(256, 64,  kernel_size=4, stride=4),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, num_classes, kernel_size=3, padding=1)
        )
        self.dropout1 = nn.Dropout2d(p=0.5)
        self.dropout2 = nn.Dropout2d(p=0.5)

    def forward(self, x):
        B, C, H, W = x.shape
        features = self.backbone.forward_features(x)
        if features.dim() == 3:
            expected_patches = (H // 16) * (W // 16)
            if features.shape[1] == expected_patches + 1:
                features = features[:, 1:, :]
            features = features.transpose(1, 2).contiguous().view(B, self.embed_dim, H // 16, W // 16)

        x_dec = features
        for i, layer in enumerate(self.decode_head):
            x_dec = layer(x_dec)
            if i == 2:  x_dec = self.dropout1(x_dec)
            elif i == 5: x_dec = self.dropout2(x_dec)
        logits = x_dec
        if logits.shape[2:] != (H, W):
            logits = F.interpolate(logits, size=(H, W), mode='bilinear', align_corners=False)
        return logits

class EvalPolypDataset(Dataset):
    def __init__(self, file_paths, mask_dict, img_size=384):
        self.file_paths = file_paths
        self.mask_dict  = mask_dict
        self.img_size   = img_size
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        self.std  = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
    def __len__(self): return len(self.file_paths)
    def __getitem__(self, idx):
        img_path  = self.file_paths[idx]
        mask_path = self.mask_dict.get(img_path.stem)
        img = cv2.imread(str(img_path))
        if img is None: img = np.zeros((self.img_size, self.img_size, 3), dtype=np.uint8)
        else: img = cv2.resize(img, (self.img_size, self.img_size), interpolation=cv2.INTER_LINEAR)
        if mask_path is not None and Path(mask_path).exists():
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None: mask = np.zeros((self.img_size, self.img_size), dtype=np.uint8)
            else: mask = cv2.resize(mask, (self.img_size, self.img_size), interpolation=cv2.INTER_NEAREST)
        else: mask = np.zeros((self.img_size, self.img_size), dtype=np.uint8)
        img_t  = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).permute(2, 0, 1).float() / 255.0
        img_t  = (img_t - self.mean) / self.std
        mask_t = torch.from_numpy((mask > 127).astype(np.float32)).unsqueeze(0)
        return img_t, mask_t

def compute_metrics(model, loader, device):
    model.eval().to(device)
    dices, ious, precs, recs = [], [], [], []
    with torch.no_grad():
        for batch_idx, (imgs, masks) in enumerate(loader):
            if batch_idx % 10 == 0:
                print(f"Processing batch {batch_idx}/{len(loader)}")
            print("  Moving to device...")
            imgs = imgs.to(device)
            print("  Forward pass...")
            logits = model(imgs)
            print("  Moving to CPU...")
            probs = torch.sigmoid(logits).cpu().numpy()
            gts   = masks.numpy()
            print("  Metrics calculation...")
            for i in range(len(probs)):
                p  = (probs[i, 0] > 0.5).astype(np.float32)
                g  = (gts[i,   0] > 0.5).astype(np.float32)
                tp = (p * g).sum()
                fp = (p * (1.0 - g)).sum()
                fn = ((1.0 - p) * g).sum()
                dices.append((2.0*tp + 1e-6) / (2.0*tp + fp + fn + 1e-6))
                ious.append(  (tp    + 1e-6) / (tp + fp + fn + 1e-6))
                precs.append( (tp    + 1e-6) / (tp + fp + 1e-6))
                recs.append(  (tp    + 1e-6) / (tp + fn + 1e-6))
    return {'dice': float(np.mean(dices)), 'iou': float(np.mean(ious)),
            'precision': float(np.mean(precs)), 'recall': float(np.mean(recs))}

def discover_img_mask_paths(root_dir, img_dir_names, mask_dir_names):
    root = Path(root_dir)
    if not root.exists(): return [], {}
    img_lo  = {n.lower() for n in img_dir_names}
    mask_lo = {n.lower() for n in mask_dir_names}
    img_dirs, mask_dirs = [], []
    for p in root.rglob('*'):
        if not p.is_dir(): continue
        lo = p.name.lower()
        if lo in img_lo:  img_dirs.append(p)
        if lo in mask_lo: mask_dirs.append(p)
    img_files = []
    for d in img_dirs:
        img_files += sorted([f for f in d.iterdir() if f.suffix.lower() in IMAGE_EXTS], key=lambda x: x.name)
    mask_dict = {}
    for d in mask_dirs:
        for f in d.iterdir():
            if f.suffix.lower() in IMAGE_EXTS: mask_dict[f.stem] = f
    return img_files, mask_dict

def run_evaluation(dataset_root, dataset_name, img_dir_names, mask_dir_names, model, device):
    print(f'\\n==== Evaluating {dataset_name} ====')
    img_files, mask_dict = discover_img_mask_paths(dataset_root, img_dir_names, mask_dir_names)
    if not img_files:
        print(f'WARNING: No images found under {dataset_root}. Skipping.')
        return None
    print(f'Discovered {len(img_files)} images, {len(mask_dict)} masks')
    dataset = EvalPolypDataset(img_files, mask_dict, img_size=384)
    loader  = DataLoader(dataset, batch_size=1, shuffle=False, num_workers=0, pin_memory=False)
    metrics = compute_metrics(model, loader, device)
    print(f"Dice (DSC) : {metrics['dice']:.4f}")
    print(f"mIoU       : {metrics['iou']:.4f}")
    return metrics

def main():
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Using device: {device}')
    
    # Auto-detect base directory for cross-environment compatibility
    base_dir = str(Path(__file__).resolve().parent)
    print(f'Using base directory: {base_dir}')
    
    model = ChakraTransformerSegmenter(pretrained=False)
    weight_path = Path(f'{base_dir}/weights/chakra_transformer_best.pth')
    if not weight_path.exists():
        weight_path = Path(f'{base_dir}/chakra_transformer_best.pth')
        
    if not weight_path.exists():
        print(f"Weight not found at {weight_path}")
        return
    print(f'Loading weights from: {weight_path}')
    state_dict = torch.load(weight_path, map_location=device, weights_only=True)
    new_state_dict = {}
    for k, v in state_dict.items():
        name = k.replace("_orig_mod.", "").replace("module.", "")
        new_state_dict[name] = v
    model.load_state_dict(new_state_dict, strict=False)
    model.to(device).eval()

    colondb_root = Path(f'{base_dir}/data/cvc-colondb')
    if not colondb_root.exists():
        colondb_root = Path(f'{base_dir}/cvc-colondb')
    if colondb_root.exists():
        run_evaluation(str(colondb_root), 'CVC-ColonDB', ['images'], ['masks'], model, device)
        
    cvc300_root = Path(f'{base_dir}/data/cvc-300')
    if not cvc300_root.exists():
        cvc300_root = Path(f'{base_dir}/cvc-300')
    if cvc300_root.exists():
        run_evaluation(str(cvc300_root), 'CVC-300', ['images'], ['masks'], model, device)

if __name__ == '__main__':
    main()
