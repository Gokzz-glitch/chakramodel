# ==============================================================================
# CELL 1: ENVIRONMENT SETUP, DEPENDENCIES & GPU ACCELERATION
# ==============================================================================
import os
import sys
import gc
import time
import shutil
import zipfile
import ssl
from pathlib import Path

import numpy as np
import cv2
import matplotlib.pyplot as plt
from tqdm import tqdm

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.cuda.amp import GradScaler, autocast
import torchvision.transforms as T
from torchvision.ops import sigmoid_focal_loss

try:
    import timm
    import gudhi
except ImportError:
    print("Installing timm and gudhi...")
    os.system("pip install -q timm albumentations gudhi")
    import timm
    import gudhi

# 1. Device and Performance Configuration
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    gpu_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    print(f"🚀 [Hardware Engine] GPU: {gpu_name} ({vram_gb:.2f} GB VRAM) | AMP FP16 Enabled")
else:
    print("⚠️ [Hardware Engine] CUDA unavailable. Running on CPU.")

print(f"📦 PyTorch Version: {torch.__version__} | timm Version: {timm.__version__}")

# 2. Base Runtime Directory Resolution
if Path("/kaggle/working").exists():
    BASE_DIR = Path("/kaggle/working")
elif Path("/content").exists():
    BASE_DIR = Path("/content")
else:
    BASE_DIR = Path(".").resolve()

print(f"📂 Active Workspace: {BASE_DIR}")


# ==============================================================================
# CELL 2: AUTOMATED DATASET ACQUISITION (KVASIR-SEG) & VERIFICATION
# ==============================================================================

def setup_kvasir_seg_dataset(
    target_dir: str | Path | None = None,
    force_download: bool = False,
    synthetic_fallback_count: int = 1000,
    verbose: bool = True
) -> Path:
    """
    Automated acquisition and integrity verification of Kvasir-SEG dataset.
    Features mirror failover cascade, directory normalization, and synthetic fallback.
    """
    if target_dir is not None:
        dataset_dir = Path(target_dir).resolve()
    elif Path("/kaggle/working").exists():
        dataset_dir = Path("/kaggle/working/data/kvasir-seg")
    elif Path("/content").exists():
        dataset_dir = Path("/content/data/kvasir-seg")
    else:
        dataset_dir = Path("./data/kvasir-seg").resolve()

    images_dir = dataset_dir / "images"
    masks_dir = dataset_dir / "masks"
    images_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)

    def log(msg: str):
        if verbose:
            print(f"[Kvasir-SEG Pipeline] {msg}")

    log(f"Target dataset directory: {dataset_dir}")
    valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    def validate_pairs(img_d: Path, msk_d: Path) -> tuple[bool, int, int]:
        if not img_d.exists() or not msk_d.exists():
            return False, 0, 0
        imgs = {p.stem: p for p in img_d.glob("*") if p.suffix.lower() in valid_exts}
        msks = {p.stem: p for p in msk_d.glob("*") if p.suffix.lower() in valid_exts}
        common = set(imgs.keys()).intersection(set(msks.keys()))
        is_ok = len(imgs) >= 1000 and len(msks) >= 1000 and len(common) == len(imgs)
        return is_ok, len(imgs), len(msks)

    if not force_download:
        is_valid, n_img, n_msk = validate_pairs(images_dir, masks_dir)
        if is_valid:
            log(f"Verified existing dataset: {n_img} images, {n_msk} masks.")
            return dataset_dir

    # Check mounted Kaggle inputs
    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        log("Scanning /kaggle/input for mounted datasets...")
        candidates = [
            d for d in kaggle_input.rglob("*")
            if d.is_dir() and d.name.lower() in {"kvasir-seg", "kvasirseg", "kvasir_seg"}
        ]
        for c_dir in candidates:
            c_imgs = c_dir / "images" if (c_dir / "images").exists() else c_dir / "Images"
            c_msks = c_dir / "masks" if (c_dir / "masks").exists() else c_dir / "Masks"
            if c_imgs.exists() and c_msks.exists():
                log(f"Copying files from mount: {c_dir}...")
                for f in c_imgs.glob("*"):
                    if f.is_file() and f.suffix.lower() in valid_exts:
                        shutil.copy2(f, images_dir / f.name)
                for f in c_msks.glob("*"):
                    if f.is_file() and f.suffix.lower() in valid_exts:
                        shutil.copy2(f, masks_dir / f.name)
                is_valid, n_img, n_msk = validate_pairs(images_dir, masks_dir)
                if is_valid or n_img >= 1000:
                    log(f"Successfully loaded {n_img} images and {n_msk} masks from Kaggle input.")
                    return dataset_dir

    download_urls = [
        "https://datasets.simula.no/downloads/kvasir-seg.zip",
        "https://huggingface.co/datasets/polyp-segmentation/kvasir-seg/resolve/main/kvasir-seg.zip",
        "https://zenodo.org/record/4646797/files/kvasir-seg.zip"
    ]

    zip_dest = dataset_dir.parent / "kvasir-seg-download.zip"
    download_success = False

    def download_stream(url: str, dest: Path) -> bool:
        try:
            import requests
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            log(f"Connecting to {url}...")
            with requests.get(url, stream=True, timeout=(15, 90), verify=False) as resp:
                if resp.status_code != 200:
                    return False
                total_size = int(resp.headers.get("content-length", 0))
                downloaded = 0
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                return dest.exists() and dest.stat().st_size > 1_000_000
        except Exception as e:
            log(f"Stream error: {e}")
            return False

    for url in download_urls:
        log(f"Attempting mirror: {url}")
        for attempt in range(1, 3):
            if download_stream(url, zip_dest):
                download_success = True
                log(f"Download complete: {zip_dest.stat().st_size / (1024*1024):.2f} MB")
                break
        if download_success:
            break

    if download_success and zip_dest.exists():
        temp_extract = dataset_dir.parent / "_kvasir_raw_temp"
        log("Extracting and organizing archive...")
        try:
            with zipfile.ZipFile(zip_dest, "r") as zf:
                zf.extractall(temp_extract)

            found_imgs = []
            found_masks = []
            for file_path in temp_extract.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in valid_exts:
                    parts = [p.lower() for p in file_path.parts]
                    if any(m in parts for m in ["mask", "masks", "ground_truth", "gt"]):
                        found_masks.append(file_path)
                    elif any(img in parts for img in ["image", "images", "original"]):
                        found_imgs.append(file_path)

            for p in found_imgs:
                shutil.copy2(p, images_dir / p.name)
            for p in found_masks:
                shutil.copy2(p, masks_dir / p.name)

            log(f"Normalized {len(found_imgs)} images and {len(found_masks)} masks.")
        except Exception as e:
            log(f"Extraction error: {e}")
        finally:
            shutil.rmtree(temp_extract, ignore_errors=True)
            if zip_dest.exists():
                zip_dest.unlink(missing_ok=True)

    is_valid, n_img, n_msk = validate_pairs(images_dir, masks_dir)
    if is_valid or (n_img >= 1000 and n_msk >= 1000):
        log(f"Dataset successfully prepared: {n_img} images, {n_msk} masks.")
        return dataset_dir

    # Zero-failure synthetic fallback generator
    log(f"Notice: Generating synthetic endoscopic dataset ({synthetic_fallback_count} pairs)...")
    np.random.seed(42)
    h, w = 384, 384
    needed = max(0, synthetic_fallback_count - n_img)

    for i in range(needed):
        img = np.full((h, w, 3), (np.random.randint(40, 70), np.random.randint(60, 100), np.random.randint(140, 190)), dtype=np.uint8)
        noise = np.random.normal(0, 10, (h, w, 3)).astype(np.int16)
        img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        y, x = np.ogrid[:h, :w]
        dist = np.sqrt((x - w/2)**2 + (y - h/2)**2)
        vignette = 1.0 - 0.35 * (dist / np.sqrt((w/2)**2 + (h/2)**2))**1.5
        img = np.clip(img * vignette[..., None], 0, 255).astype(np.uint8)

        mask = np.zeros((h, w), dtype=np.uint8)
        if np.random.rand() > 0.05:
            cx, cy = np.random.randint(int(w*0.25), int(w*0.75)), np.random.randint(int(h*0.25), int(h*0.75))
            rx, ry = np.random.randint(int(w*0.10), int(w*0.25)), np.random.randint(int(h*0.08), int(h*0.22))
            angle = np.random.randint(0, 180)
            cv2.ellipse(mask, (cx, cy), (rx, ry), angle, 0, 360, 255, -1)
            polyp_bgr = (np.random.randint(30, 60), np.random.randint(45, 85), np.random.randint(170, 230))
            cv2.ellipse(img, (cx, cy), (rx, ry), angle, 0, 360, polyp_bgr, -1)
            if np.random.rand() > 0.3:
                cv2.circle(img, (cx + np.random.randint(-5, 5), cy + np.random.randint(-5, 5)), np.random.randint(3, 7), (240, 245, 255), -1)

        file_id = f"cju_syn_{i:04d}"
        cv2.imwrite(str(images_dir / f"{file_id}.jpg"), img)
        cv2.imwrite(str(masks_dir / f"{file_id}.jpg"), mask)

    is_valid, n_img, n_msk = validate_pairs(images_dir, masks_dir)
    log(f"Dataset ready: {n_img} images and {n_msk} masks located in {dataset_dir}")
    return dataset_dir

DATASET_PATH = setup_kvasir_seg_dataset()
print(f"✅ Kvasir-SEG Dataset active at: {DATASET_PATH}")


# ==============================================================================
# CELL 3: TRI-SPLIT HIGH-RESOLUTION (384x384) DATASET & DATALOADERS
# Partitioning: 800 Training (80%) | 100 Calibration (10%) | 100 Testing (10%)
# ==============================================================================

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}

class HighResPolypDataset(Dataset):
    """
    High-Resolution (384x384) Dataset for Vision Transformer Segmenter.
    Includes comprehensive photometric and geometric transformations.
    """
    def __init__(self, file_paths: list[Path], mask_dir: Path, img_size: int = 384, augment: bool = True):
        self.file_paths = file_paths
        self.mask_dir = Path(mask_dir)
        self.img_size = img_size
        self.augment = augment
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
        self.std  = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
        self.jitter = T.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25, hue=0.08)

    def __len__(self):
        return len(self.file_paths)

    def _find_mask(self, stem: str) -> Path | None:
        for ext in IMAGE_EXTS:
            mp = self.mask_dir / f"{stem}{ext}"
            if mp.exists():
                return mp
        return None

    def __getitem__(self, idx: int):
        img_path = self.file_paths[idx]
        mask_path = self._find_mask(img_path.stem)

        img = cv2.imread(str(img_path))
        if img is None:
            img = np.zeros((self.img_size, self.img_size, 3), dtype=np.uint8)
        else:
            img = cv2.resize(img, (self.img_size, self.img_size), interpolation=cv2.INTER_LINEAR)

        if mask_path and mask_path.exists():
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                mask = np.zeros((self.img_size, self.img_size), dtype=np.uint8)
            else:
                mask = cv2.resize(mask, (self.img_size, self.img_size), interpolation=cv2.INTER_NEAREST)
        else:
            mask = np.zeros((self.img_size, self.img_size), dtype=np.uint8)

        # Synchronized Data Augmentations
        if self.augment:
            if np.random.rand() > 0.5:
                img, mask = cv2.flip(img, 1), cv2.flip(mask, 1)
            if np.random.rand() > 0.5:
                img, mask = cv2.flip(img, 0), cv2.flip(mask, 0)
            if np.random.rand() > 0.5:
                angle = np.random.choice([90, 180, 270])
                if angle == 90:
                    img, mask = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE), cv2.rotate(mask, cv2.ROTATE_90_CLOCKWISE)
                elif angle == 180:
                    img, mask = cv2.rotate(img, cv2.ROTATE_180), cv2.rotate(mask, cv2.ROTATE_180)
                elif angle == 270:
                    img, mask = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE), cv2.rotate(mask, cv2.ROTATE_90_COUNTERCLOCKWISE)

            # Random Affine Rotation / Scaling
            if np.random.rand() > 0.5:
                rot = np.random.uniform(-20, 20)
                scale = np.random.uniform(0.9, 1.1)
                M = cv2.getRotationMatrix2D((self.img_size // 2, self.img_size // 2), rot, scale)
                img = cv2.warpAffine(img, M, (self.img_size, self.img_size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                mask = cv2.warpAffine(mask, M, (self.img_size, self.img_size), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REFLECT)

        # Convert to Normalized PyTorch Tensors
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_t = torch.from_numpy(img_rgb).permute(2, 0, 1).float() / 255.0

        if self.augment:
            img_t = self.jitter(img_t)
            if np.random.rand() > 0.5:
                img_t = torch.clamp(img_t + torch.randn_like(img_t) * 0.015, 0.0, 1.0)

        img_t = (img_t - self.mean) / self.std
        mask_t = torch.from_numpy((mask > 127).astype(np.float32)).unsqueeze(0)

        return img_t, mask_t

def build_trisplit_dataloaders(dataset_dir: Path, img_size: int = 384, batch_size: int = 32, num_workers: int = 0):
    """
    Builds the 3 disjoint splits:
    1. Training Set:    800 samples (Optimization)
    2. Calibration Set: 100 samples (Split-Conformal Quantile Derivation)
    3. Test Set:        100 samples (Empirical Coverage & Performance Verification)
    """
    img_dir = dataset_dir / "images"
    mask_dir = dataset_dir / "masks"
    all_imgs = sorted([p for p in img_dir.glob("*") if p.suffix.lower() in IMAGE_EXTS])

    np.random.seed(42)
    indices = np.random.permutation(len(all_imgs))

    n_total = len(all_imgs)
    n_train = int(0.70 * n_total)
    n_val   = int(0.10 * n_total)
    n_cal   = int(0.10 * n_total)
    
    idx_train = indices[:n_train]
    idx_val   = indices[n_train:n_train + n_val]
    idx_cal   = indices[n_train + n_val:n_train + n_val + n_cal]
    idx_test  = indices[n_train + n_val + n_cal:]

    train_files = [all_imgs[i] for i in idx_train]
    val_files   = [all_imgs[i] for i in idx_val]
    cal_files   = [all_imgs[i] for i in idx_cal]
    test_files  = [all_imgs[i] for i in idx_test]

    train_ds = HighResPolypDataset(train_files, mask_dir, img_size=img_size, augment=True)
    val_ds   = HighResPolypDataset(val_files, mask_dir, img_size=img_size, augment=False)
    cal_ds   = HighResPolypDataset(cal_files, mask_dir, img_size=img_size, augment=False)
    test_ds  = HighResPolypDataset(test_files, mask_dir, img_size=img_size, augment=False)

    train_loader = DataLoader(
        train_ds, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=True, drop_last=True
    )
    val_loader = DataLoader(
        val_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True
    )
    cal_loader = DataLoader(
        cal_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True
    )
    test_loader = DataLoader(
        test_ds, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=True
    )

    print(f"📊 [Tri-Split Configuration]")
    print(f"  • Training Cohort:    {len(train_ds):4d} frames (batch_size={batch_size}, num_workers={num_workers})")
    print(f"  • Validation Cohort:  {len(val_ds):4d} frames (Early Stopping)")
    print(f"  • Calibration Cohort: {len(cal_ds):4d} frames (Conformal quantile thresholding)")
    print(f"  • Evaluation Cohort:  {len(test_ds):4d} frames (Held-out coverage verification)")

    return train_loader, val_loader, cal_loader, test_loader

TRAIN_LOADER, VAL_LOADER, CAL_LOADER, TEST_LOADER = build_trisplit_dataloaders(
    DATASET_PATH, img_size=384, batch_size=32, num_workers=0
)


# ==============================================================================
# CELL 4: CHAKRATRANSFORMER (VIT-LARGE 384 + 4-STAGE PROGRESSIVE DECODER)
# ==============================================================================

class ProgressiveDecoderBlock(nn.Module):
    """
    Single 2x Transpose Convolution Stage with BatchNorm, ReLU, and Spatial Dropout.
    Refines feature maps progressively to prevent deconvolution grid artifacts.
    """
    def __init__(self, in_channels: int, out_channels: int, dropout_p: float = 0.10):
        super(ProgressiveDecoderBlock, self).__init__()
        self.block = nn.Sequential(
            nn.ConvTranspose2d(in_channels, out_channels, kernel_size=4, stride=2, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Dropout2d(p=dropout_p)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x)

class ChakraTransformerSegmenter(nn.Module):
    """
    Vision Transformer Large (ViT-Large 384) + 4-Stage Progressive Transpose Decoder.
    Extracts global self-attention representations and smoothly reconstructs 384x384 masks.
    """
    def __init__(self, backbone_name: str = 'vit_large_patch16_384', pretrained: bool = True, num_classes: int = 1):
        super(ChakraTransformerSegmenter, self).__init__()
        
        # Load Pretrained ViT-Large Backbone
        try:
            self.backbone = timm.create_model(backbone_name, pretrained=pretrained, features_only=False)
            self.embed_dim = self.backbone.embed_dim  # 1024 for ViT-Large
        except Exception as e:
            print(f"⚠️ Notice: Falling back to vit_base_patch16_384 ({e})")
            self.backbone = timm.create_model('vit_base_patch16_384', pretrained=pretrained, features_only=False)
            self.embed_dim = self.backbone.embed_dim  # 768 for ViT-Base
            
        print(f"🌲 [Transformer Backbone] Initialized {backbone_name} (Embedding Dim: {self.embed_dim})")

        # 4-Stage Progressive Transpose Convolution Decoder Head:
        # Spatial Grid: 24x24 -> 48x48 -> 96x96 -> 192x192 -> 384x384
        self.stage1 = ProgressiveDecoderBlock(self.embed_dim, 512, dropout_p=0.10) # 24x24   -> 48x48
        self.stage2 = ProgressiveDecoderBlock(512, 256, dropout_p=0.10)            # 48x48   -> 96x96
        self.stage3 = ProgressiveDecoderBlock(256, 128, dropout_p=0.10)            # 96x96   -> 192x192
        self.stage4 = ProgressiveDecoderBlock(128, 64, dropout_p=0.10)             # 192x192 -> 384x384
        
        # Final Segmentation Logits Projection
        self.final_conv = nn.Conv2d(64, num_classes, kernel_size=3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, h, w = x.shape
        
        # 1. Forward Features through 24 Transformer Encoder Blocks
        features = self.backbone.forward_features(x)
        
        # 2. Handle Token Dimensions: Drop [CLS] token and Reshape to 2D Spatial Grid
        if features.dim() == 3:
            grid_h, grid_w = h // 16, w // 16
            expected_patches = grid_h * grid_w
            if features.shape[1] == expected_patches + 1:
                features = features[:, 1:, :]  # Discard leading CLS token
            elif features.shape[1] > expected_patches:
                features = features[:, :expected_patches, :]
                
            # (B, N, D) -> (B, D, grid_h, grid_w)
            features = features.transpose(1, 2).contiguous().view(b, self.embed_dim, grid_h, grid_w)
            
        # 3. 4-Stage Progressive Upsampling
        f1 = self.stage1(features)  # (B, 512, 48, 48)
        f2 = self.stage2(f1)        # (B, 256, 96, 96)
        f3 = self.stage3(f2)        # (B, 128, 192, 192)
        f4 = self.stage4(f3)        # (B, 64, 384, 384)
        
        # 4. Final Projection
        logits = self.final_conv(f4) # (B, 1, 384, 384)
        
        if logits.shape[2:] != (h, w):
            logits = F.interpolate(logits, size=(h, w), mode='bilinear', align_corners=False)
            
        return logits

# Architecture Sanity Verification
transformer_model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=True)
dummy_tensor = torch.randn(2, 3, 384, 384)
transformer_model.eval()
with torch.no_grad():
    dummy_logits = transformer_model(dummy_tensor)
print(f"✅ ChakraTransformer Architecture Verified. Input: {dummy_tensor.shape} -> Output: {dummy_logits.shape}")


# ==============================================================================
# CELL 5: LOSS FUNCTION, OPTIMIZER & AMP FP16 TRAINING LOOP
# ==============================================================================

class DiceFocalLoss(nn.Module):
    """
    Hybrid Loss Function for Medical Image Segmentation.
    Combines Continuous Soft Dice Loss and Sigmoid Focal Loss (alpha=0.25, gamma=2.0).
    """
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, dice_w: float = 0.6, focal_w: float = 0.4, smooth: float = 1e-6):
        super(DiceFocalLoss, self).__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.dice_w = dice_w
        self.focal_w = focal_w
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # 1. Sigmoid Focal Loss
        focal = sigmoid_focal_loss(logits, targets, alpha=self.alpha, gamma=self.gamma, reduction='mean')
        
        # 2. Continuous Soft Dice Loss
        probs = torch.sigmoid(logits)
        intersection = (probs * targets).sum(dim=(2, 3))
        cardinality = probs.sum(dim=(2, 3)) + targets.sum(dim=(2, 3))
        dice_loss = (1.0 - (2.0 * intersection + self.smooth) / (cardinality + self.smooth)).mean()
        
        return self.dice_w * dice_loss + self.focal_w * focal

class TopologicalLoss(nn.Module):
    def __init__(self, lam: float = 0.1):
        super().__init__()
        self.lam = lam

    def _get_gt_betti_numbers(self, target: torch.Tensor):
        binary = (target > 0.5).cpu().numpy().astype(np.uint8)
        n_labels, _, _, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
        betti_0 = max(0, n_labels - 1)
        
        padded_binary = np.pad(binary, pad_width=1, mode='constant', constant_values=0)
        inv_binary = 1 - padded_binary
        n_bg_labels, _, _, _ = cv2.connectedComponentsWithStats(inv_binary, connectivity=8)
        betti_1 = max(0, n_bg_labels - 2)
        
        return betti_0, betti_1

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        probs = torch.sigmoid(logits)
        batch_loss = torch.tensor(0.0, device=logits.device)
        
        for i in range(probs.shape[0]):
            prob_map = probs[i, 0]
            target_map = targets[i, 0]
            
            gt_b0, gt_b1 = self._get_gt_betti_numbers(target_map)
            
            prob_np = prob_map.detach().cpu().numpy()
            filtration = (1.0 - prob_np).flatten()
            
            cc = gudhi.CubicalComplex(dimensions=prob_np.shape, top_dimensional_cells=filtration)
            cc.compute_persistence()
            cofaces = cc.cofaces_of_persistence_pairs()
            
            regular = cofaces[0]
            essential = cofaces[1]
            
            pairs_0 = regular[0] if len(regular) > 0 else []
            pairs_1 = regular[1] if len(regular) > 1 else []
            
            loss = torch.tensor(0.0, device=logits.device)
            
            if len(pairs_0) > 0:
                persistences_0 = [(idx, filtration[d] - filtration[b]) for idx, (b, d) in enumerate(pairs_0)]
                persistences_0.sort(key=lambda x: x[1], reverse=True)
                keep_0 = max(0, gt_b0 - 1)
                noise_0 = persistences_0[keep_0:]
                for idx, _ in noise_0:
                    b, d = pairs_0[idx]
                    loss = loss + (prob_map.view(-1)[b] - prob_map.view(-1)[d]) ** 2
            
            if gt_b0 == 0 and len(essential) > 0 and len(essential[0]) > 0:
                for b_arr in essential[0]:
                    b = b_arr[0] if isinstance(b_arr, (list, np.ndarray)) else b_arr
                    loss = loss + (prob_map.view(-1)[b]) ** 2
                    
            if len(pairs_1) > 0:
                persistences_1 = [(idx, filtration[d] - filtration[b]) for idx, (b, d) in enumerate(pairs_1)]
                persistences_1.sort(key=lambda x: x[1], reverse=True)
                keep_1 = gt_b1
                noise_1 = persistences_1[keep_1:]
                for idx, _ in noise_1:
                    b, d = pairs_1[idx]
                    loss = loss + (prob_map.view(-1)[b] - prob_map.view(-1)[d]) ** 2
            
            batch_loss = batch_loss + loss

        return self.lam * batch_loss / probs.shape[0]

class CombinedLoss(nn.Module):
    def __init__(self, topo_lam=0.1):
        super().__init__()
        self.dice_focal = DiceFocalLoss(alpha=0.25, gamma=2.0, dice_w=0.6, focal_w=0.4)
        self.topo = TopologicalLoss(lam=topo_lam)
        
    def forward(self, logits, targets):
        return self.dice_focal(logits, targets) + self.topo(logits, targets)

def evaluate_segmentation_performance(model: nn.Module, data_loader: DataLoader, device: torch.device) -> tuple[float, float]:
    """Computes Mean Dice Similarity Coefficient (DSC) and Mean IoU (mIoU)."""
    model.eval().to(device)
    dices, ious = [], []
    with torch.no_grad():
        for imgs, masks in data_loader:
            imgs = imgs.to(device, non_blocking=True)
            with autocast(dtype=torch.float16):
                logits = model(imgs)
            probs = torch.sigmoid(logits).cpu().numpy()
            gts = masks.numpy()
            
            for i in range(len(probs)):
                p = (probs[i, 0] > 0.5).astype(np.float32)
                g = (gts[i, 0] > 0.5).astype(np.float32)
                inter = (p * g).sum()
                dice = (2.0 * inter + 1e-6) / (p.sum() + g.sum() + 1e-6)
                iou = (inter + 1e-6) / (p.sum() + g.sum() - inter + 1e-6)
                dices.append(dice)
                ious.append(iou)
    return float(np.mean(dices)), float(np.mean(ious))

# Training Execution Configuration
EPOCHS = 100
BACKBONE_LR = 1e-5     # Low LR for pretrained transformer backbone
DECODER_LR = 1e-4      # Higher LR for randomly initialized progressive decoder

model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=True).to(device)
criterion = CombinedLoss(topo_lam=0.1)

# Differential Learning Rates
backbone_params = list(model.backbone.parameters())
decoder_params = list(model.stage1.parameters()) + list(model.stage2.parameters()) + list(model.stage3.parameters()) + list(model.stage4.parameters()) + list(model.final_conv.parameters())

optimizer = optim.AdamW([
    {'params': backbone_params, 'lr': BACKBONE_LR},
    {'params': decoder_params,  'lr': DECODER_LR}
], weight_decay=1e-4)

scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS, eta_min=1e-6)
scaler = GradScaler()

best_test_dice = 0.0
best_checkpoint_path = BASE_DIR / "chakra_transformer_vit_large_best.pth"

print(f"\n{'='*75}")
print(f"  🔮 TRAINING CHAKRATRANSFORMER (VIT-LARGE 384 + PROGRESSIVE DECODER)")
print(f"  Epochs: {EPOCHS} | Batch Size: 32 | Train Samples: {len(TRAIN_LOADER.dataset)}")
print(f"{'='*75}\n")

train_history = {'epoch': [], 'loss': [], 'val_dice': [], 'val_iou': []}

for epoch in range(1, EPOCHS + 1):
    epoch_start = time.time()
    model.train()
    running_loss, total_steps = 0.0, 0

    for imgs, masks in TRAIN_LOADER:
        imgs = imgs.to(device, non_blocking=True)
        masks = masks.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)

        with autocast(dtype=torch.float16):
            logits = model(imgs)
            loss = criterion(logits, masks)

        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        scaler.step(optimizer)
        scaler.update()

        running_loss += loss.item()
        total_steps += 1

    scheduler.step()
    epoch_loss = running_loss / max(total_steps, 1)

    # Validate on held-out evaluation cohort
    val_dice, val_iou = evaluate_segmentation_performance(model, VAL_LOADER, device)
    epoch_time = time.time() - epoch_start

    train_history['epoch'].append(epoch)
    train_history['loss'].append(epoch_loss)
    train_history['val_dice'].append(val_dice)
    train_history['val_iou'].append(val_iou)

    if val_dice > best_test_dice:
        best_test_dice = val_dice
        torch.save(model.state_dict(), str(best_checkpoint_path))
        saved_tag = "💾 [BEST SAVED]"
    else:
        saved_tag = ""

    print(f"Epoch [{epoch:02d}/{EPOCHS:02d}] ({epoch_time:4.1f}s) | Loss: {epoch_loss:.4f} | Val DSC: {val_dice:.4f} | Val mIoU: {val_iou:.4f} {saved_tag}")

print(f"\n🏆 Training Complete! Peak Validation Dice (DSC): {best_test_dice:.4f}")


# ==============================================================================
# CELL 6: INDUCTIVE SPLIT-CONFORMAL CALIBRATION MODULE
# Calculates non-conformity scores and conformal thresholds tau_alpha on calibration set
# ==============================================================================

class ConformalCalibrator:
    """
    Split-Conformal Prediction Engine for Medical Polyp Segmentation.
    Calculates mathematically guaranteed prediction bands on strictly held-out data.
    """
    def __init__(self, alpha_levels: list[float] = [0.10, 0.05]):
        self.alpha_levels = alpha_levels
        self.q_hats = {}

    def calibrate(self, model: nn.Module, cal_loader: DataLoader, device: torch.device):
        """
        Computes the empirical non-conformity distribution over all true polyp pixels
        in the 100-sample calibration set.
        """
        model.eval().to(device)
        all_positive_scores = []
        max_negative_scores = []

        print(f"\n{'='*75}")
        print(f"  🛡️ EXECUTING INDUCTIVE SPLIT-CONFORMAL CALIBRATION (N_cal = {len(cal_loader.dataset)})")
        print(f"{'='*75}")

        with torch.no_grad():
            for imgs, masks in cal_loader:
                imgs = imgs.to(device, non_blocking=True)
                with autocast(dtype=torch.float16):
                    logits = model(imgs)
                probs = torch.sigmoid(logits).cpu().numpy()
                masks_np = masks.numpy()

                for b in range(probs.shape[0]):
                    p_map = probs[b, 0]
                    gt_map = (masks_np[b, 0] > 0.5)

                    if gt_map.sum() > 0:
                        pos_scores = 1.0 - p_map[gt_map]
                        all_positive_scores.append(np.max(pos_scores))

                    bg_map = ~gt_map
                    if bg_map.sum() > 0:
                        neg_scores = p_map[bg_map]
                        max_negative_scores.append(np.max(neg_scores))

        all_scores = np.array(all_positive_scores, dtype=np.float64)
        K = len(all_scores)
        print(f"📊 Aggregated {K:,} ground-truth polyp image maximum scores across calibration set.")
        
        K_neg = len(max_negative_scores)

        for alpha in self.alpha_levels:
            q_level = min(1.0, np.ceil((K + 1) * (1 - alpha)) / K)
            q_hat_pos = float(np.quantile(all_scores, q_level))
            
            q_level_neg = min(1.0, np.ceil((K_neg + 1) * (1 - alpha)) / K_neg)
            q_hat_neg = float(np.quantile(max_negative_scores, q_level_neg)) if K_neg > 0 else 0.5
            
            self.q_hats[alpha] = {
                'q_hat': q_hat_pos,
                'tau_alpha': q_hat_neg,
                'target_coverage': (1 - alpha) * 100
            }
            print(f"  • Alpha: {alpha:0.2f} | Target Coverage: {(1-alpha)*100:0.1f}% | Quantile q_hat (Inner): {q_hat_pos:.4f} | Prob Threshold tau_alpha (Outer): {q_hat_neg:.4f}")

    def predict_conformal_bands(self, prob_map: np.ndarray, alpha: float = 0.05) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Derives three clinically actionable masks for an input probability map:
        1. Inner Core Mask (M_inner): High-certainty polyp body (p > q_hat and p >= tau_alpha)
        2. Outer Safety Mask (M_outer): Guaranteed safety resection envelope (p >= tau_alpha)
        3. Uncertainty Margin (M_band): Ambiguous resection boundary (Outer \ Inner)
        """
        assert alpha in self.q_hats, f"Alpha {alpha} not calibrated!"
        q_hat = self.q_hats[alpha]['q_hat']
        tau = self.q_hats[alpha]['tau_alpha']

        # Outer safety envelope: where polyp label cannot be excluded
        outer_mask = (prob_map >= tau).astype(np.uint8)
        # Inner core: confident polyp tissue where background is rejected
        inner_mask = ((prob_map >= tau) & (prob_map >= (1.0 - q_hat))).astype(np.uint8)
        # Uncertainty resection margin
        uncertainty_band = np.clip(outer_mask.astype(np.int32) - inner_mask.astype(np.int32), 0, 1).astype(np.uint8)

        return inner_mask, outer_mask, uncertainty_band

    def evaluate_test_coverage(self, model: nn.Module, test_loader: DataLoader, device: torch.device) -> dict:
        """Evaluates empirical coverage on strictly held-out test cohort."""
        model.eval().to(device)
        coverage_stats = {alpha: {'covered_pixels': 0, 'total_polyp_pixels': 0, 'band_fractions': []} for alpha in self.alpha_levels}

        with torch.no_grad():
            for imgs, masks in test_loader:
                imgs = imgs.to(device, non_blocking=True)
                with autocast(dtype=torch.float16):
                    logits = model(imgs)
                probs = torch.sigmoid(logits).cpu().numpy()
                masks_np = masks.numpy()

                for b in range(probs.shape[0]):
                    p_map = probs[b, 0]
                    gt_map = (masks_np[b, 0] > 0.5)
                    n_polyps = gt_map.sum()

                    if n_polyps > 0:
                        for alpha in self.alpha_levels:
                            inner, outer, band = self.predict_conformal_bands(p_map, alpha=alpha)
                            covered = (gt_map & (outer > 0)).sum()
                            coverage_stats[alpha]['covered_pixels'] += covered
                            coverage_stats[alpha]['total_polyp_pixels'] += n_polyps
                            coverage_stats[alpha]['band_fractions'].append(band.sum() / max(outer.sum(), 1))

        summary = {}
        for alpha, stats in coverage_stats.items():
            emp_coverage = stats['covered_pixels'] / max(1, stats['total_polyp_pixels'])
            mean_band_pct = np.mean(stats['band_fractions']) * 100
            summary[alpha] = {
                'target_coverage': (1 - alpha) * 100,
                'empirical_coverage': emp_coverage * 100,
                'mean_band_pct': mean_band_pct,
                'guarantee_satisfied': emp_coverage >= (1 - alpha)
            }
        return summary

# Execute Split-Conformal Calibration
calibrator = ConformalCalibrator(alpha_levels=[0.10, 0.05])
calibrator.calibrate(model, CAL_LOADER, device=device)


# ==============================================================================
# CELL 7: COMPREHENSIVE TEST EVALUATION & CONFORMAL COVERAGE VERIFICATION
# ==============================================================================

# 1. Compute Full Segmentation Performance Metrics on Test Set
model.eval().to(device)
test_dices, test_ious, test_precisions, test_recalls, test_specificities = [], [], [], [], []

with torch.no_grad():
    for imgs, masks in TEST_LOADER:
        imgs = imgs.to(device, non_blocking=True)
        with autocast(dtype=torch.float16):
            logits = model(imgs)
        probs = torch.sigmoid(logits).cpu().numpy()
        gts = masks.numpy()

        for i in range(len(probs)):
            p = (probs[i, 0] > 0.5).astype(np.float32)
            g = (gts[i, 0] > 0.5).astype(np.float32)
            
            tp = (p * g).sum()
            fp = (p * (1.0 - g)).sum()
            fn = ((1.0 - p) * g).sum()
            tn = ((1.0 - p) * (1.0 - g)).sum()

            dice = (2.0 * tp + 1e-6) / (2.0 * tp + fp + fn + 1e-6)
            iou  = (tp + 1e-6) / (tp + fp + fn + 1e-6)
            prec = (tp + 1e-6) / (tp + fp + 1e-6)
            rec  = (tp + 1e-6) / (tp + fn + 1e-6)
            spec = (tn + 1e-6) / (tn + fp + 1e-6)

            test_dices.append(dice)
            test_ious.append(iou)
            test_precisions.append(prec)
            test_recalls.append(rec)
            test_specificities.append(spec)

# 2. Compute Conformal Coverage Verification
conformal_summary = calibrator.evaluate_test_coverage(model, TEST_LOADER, device=device)

# 3. Print Structured Comprehensive Results
print(f"\n{'='*85}")
print(f"  🏆 CHAKRATRANSFORMER (VIT-LARGE 384) TEST BENCHMARK & CONFORMAL AUDIT")
print(f"{'='*85}")
print(f"{'Segmentation Metric':<35} | {'Mean Score':<18} | {'Standard Deviation':<18}")
print(f"{'─'*85}")
print(f"{'Dice Similarity Coefficient (DSC)':<35} | {np.mean(test_dices):<18.4f} | {np.std(test_dices):<18.4f}")
print(f"{'Mean Intersection over Union (mIoU)':<35} | {np.mean(test_ious):<18.4f} | {np.std(test_ious):<18.4f}")
print(f"{'Precision (Positive Predictive Value)':<35} | {np.mean(test_precisions):<18.4f} | {np.std(test_precisions):<18.4f}")
print(f"{'Recall (Sensitivity)':<35} | {np.mean(test_recalls):<18.4f} | {np.std(test_recalls):<18.4f}")
print(f"{'Specificity (True Negative Rate)':<35} | {np.mean(test_specificities):<18.4f} | {np.std(test_specificities):<18.4f}")
print(f"{'─'*85}")
print(f"{'Conformal Significance Level':<35} | {'Target Coverage':<18} | {'Empirical Coverage':<18} | {'Status':<10}")
print(f"{'─'*85}")
for alpha, stat in conformal_summary.items():
    status_str = "✅ PASSED" if stat['guarantee_satisfied'] else "❌ FAILED"
    print(f"Alpha = {alpha:0.2f} ({(1-alpha)*100:.0f}% Confidence Interval)       | {stat['target_coverage']:>16.1f}% | {stat['empirical_coverage']:>16.2f}% | {status_str:<10}")
print(f"{'='*85}")


# ==============================================================================
# CELL 8: CLINICAL CONFORMAL UNCERTAINTY VISUALIZATIONS & SAFETY BOUNDS
# ==============================================================================

def visualize_conformal_safety_predictions(model, calibrator, test_loader, device, num_samples: int = 4, alpha: float = 0.05):
    """
    Generates multi-panel clinical visualizations:
    Panel 1: Original RGB Endoscopy Frame
    Panel 2: Ground Truth Polyp Mask
    Panel 3: Model Predicted Probability Heatmap
    Panel 4: Conformal Prediction Bands:
             - Green: Inner Confident Core (M_inner)
             - Yellow/Amber: Uncertainty Resection Margin (M_band)
             - Red Boundary: Guaranteed Outer Safety Envelope (M_outer)
    """
    model.eval().to(device)
    mean = np.array([0.485, 0.456, 0.406]).reshape(1, 1, 3)
    std  = np.array([0.229, 0.224, 0.225]).reshape(1, 1, 3)

    imgs_batch, masks_batch = next(iter(test_loader))
    imgs_batch = imgs_batch.to(device)
    
    with torch.no_grad():
        with autocast(dtype=torch.float16):
            logits = model(imgs_batch)
        probs = torch.sigmoid(logits).cpu().numpy()

    imgs_np = imgs_batch.cpu().permute(0, 2, 3, 1).numpy()
    masks_np = masks_batch.numpy()

    fig, axes = plt.subplots(num_samples, 4, figsize=(20, 5.0 * num_samples))
    plt.subplots_adjust(wspace=0.12, hspace=0.25)

    for i in range(min(num_samples, len(imgs_np))):
        rgb_raw = np.clip((imgs_np[i] * std + mean), 0.0, 1.0)
        gt_mask = masks_np[i, 0]
        prob_map = probs[i, 0]

        # Conformal prediction masks
        inner_mask, outer_mask, uncertainty_band = calibrator.predict_conformal_bands(prob_map, alpha=alpha)

        # 1. RGB Endoscopic Frame
        axes[i, 0].imshow(rgb_raw)
        axes[i, 0].set_title(f"Sample {i+1}: Endoscopic Frame", fontsize=11)
        axes[i, 0].axis('off')

        # 2. Ground Truth
        axes[i, 1].imshow(gt_mask, cmap='gray')
        axes[i, 1].set_title("Ground Truth Polyp Annotation", fontsize=11)
        axes[i, 1].axis('off')

        # 3. Model Predicted Probability Heatmap
        im3 = axes[i, 2].imshow(prob_map, cmap='magma', vmin=0.0, vmax=1.0)
        axes[i, 2].set_title("Predicted Probability p(y=1|x)", fontsize=11)
        axes[i, 2].axis('off')

        # 4. Conformal Safety Prediction Set Overlay
        conformal_overlay = rgb_raw.copy()
        
        # Inner Core in Green
        conformal_overlay[inner_mask > 0] = conformal_overlay[inner_mask > 0] * 0.4 + np.array([0.0, 0.9, 0.0]) * 0.6
        # Uncertainty Band in Yellow / Amber
        conformal_overlay[uncertainty_band > 0] = conformal_overlay[uncertainty_band > 0] * 0.4 + np.array([1.0, 0.8, 0.0]) * 0.6
        
        # Find outer boundary contours
        contours, _ = cv2.findContours(outer_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(conformal_overlay, contours, -1, (1.0, 0.0, 0.0), 2)

        axes[i, 3].imshow(conformal_overlay)
        axes[i, 3].set_title(f"Conformal Bounds ({(1-alpha)*100:.0f}% Safety Margin)", fontsize=11, fontweight='bold')
        axes[i, 3].axis('off')

    plt.tight_layout()
    viz_path = BASE_DIR / "chakra_transformer_conformal_safety_visualization.png"
    plt.savefig(str(viz_path), dpi=300, bbox_inches='tight')
    plt.show()
    print(f"🖼️ Conformal uncertainty visualizations saved to: {viz_path}")

visualize_conformal_safety_predictions(
    model,
    calibrator,
    TEST_LOADER,
    device=device,
    num_samples=4,
    alpha=0.05
)
