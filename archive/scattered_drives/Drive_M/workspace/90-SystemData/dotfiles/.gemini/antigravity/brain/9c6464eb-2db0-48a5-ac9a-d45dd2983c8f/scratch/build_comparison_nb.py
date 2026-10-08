import json, uuid

cells = []

def md(source):
    return {"cell_type": "markdown", "id": "", "metadata": {}, "source": [source]}

def code(source, cid=""):
    return {"cell_type": "code", "execution_count": None, "id": cid,
            "metadata": {}, "outputs": [], "source": [source]}

# ── CELL 0: Title ─────────────────────────────────────────────────────────────
cells.append(md("""# ChakraModel — ViT vs PraNet Side-by-Side Comparison
## Same 15 Datasets · Same YOLO Detector · Direct Accuracy + FPS Comparison

This notebook runs BOTH segmenters on the same datasets and produces a
side-by-side table: Dice, IoU, mean_ms/frame, and estimated FPS.

**Segmenters compared:**
- Track A: ChakraNet ViT-Large (chakra_transformer_best.pth, 309M params)
- Track B: PraNetResNet101 (combo1_best.pth, 25.5M params)
- Stage 1 (shared): YOLOv8n detector (best.pt)

**No hardcoding**: all paths resolved dynamically via os.walk.
**No GPU cap**: cudnn.benchmark=True, TF32 enabled, torch.no_grad.
"""))

# ── CELL 1: Install ───────────────────────────────────────────────────────────
cells.append(code("""\
import subprocess, sys
subprocess.run([sys.executable, '-m', 'pip', 'install',
    'ultralytics', 'timm', 'thop', 'numpy', 'opencv-python',
    'matplotlib', 'pandas', 'tabulate', '--quiet'], check=False)
print('Packages ready.')
"""))

# ── CELL 2: Env + hardware unlock ────────────────────────────────────────────
cells.append(code("""\
import os, sys, glob, cv2, json, time, shutil, traceback
import numpy as np
import pandas as pd
from pathlib import Path
import torch

WORKING_DIR = '/kaggle/working'
INPUT_DIR   = '/kaggle/input'

# Unlock full GPU performance — remove all throttling
if torch.cuda.is_available():
    torch.backends.cudnn.benchmark     = True
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32    = True
    torch.backends.cudnn.deterministic = False
    gpu  = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    print(f'GPU: {gpu}  VRAM: {vram:.2f} GB')
    print('cudnn.benchmark=ON  TF32=ON  deterministic=OFF')
else:
    print('CPU mode (CUDA not available)')

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

print(f'\\nDatasets attached ({len(os.listdir(INPUT_DIR))}):')
for d in sorted(os.listdir(INPUT_DIR)):
    print(f'  /kaggle/input/{d}')
"""))

# ── CELL 3: Dataset map + dynamic resolution ──────────────────────────────────
cells.append(code("""\
# =================================================================
# DATASET MAP — no hardcoded absolute paths, all resolved below
# =================================================================
DATASET_MAP = {
    'chakramodel-kaggle-code':     {'role': 'code'},
    'finalmuruga-harae':           {'role': 'weights'},
    'chakratransformer-weights':   {'role': 'weights'},
    'final-om-evlautation-upload': {'role': 'eval_output'},
    'om-finalkaggle-upload':       {'role': 'eval_output'},

    'endoscene-cvc300-polyp-raw-dataset': {
        'role': 'image', 'name': 'CVC-300',
        'img_sub': 'CVC-300/images', 'mask_sub': 'CVC-300/masks',
    },
    'chakramodel-evaluation-datasets': {
        'role': 'image_multi', 'name': 'Eval Pack',
        'sub_datasets': [
            {'name': 'CVC-ClinicDB', 'img_sub': 'cvc-clinicdb/images', 'mask_sub': 'cvc-clinicdb/masks'},
            {'name': 'Kvasir-SEG',   'img_sub': 'kvasir-seg/images',   'mask_sub': 'kvasir-seg/masks'},
            {'name': 'ETIS-LARIB',   'img_sub': 'etis-larib/images',   'mask_sub': 'etis-larib/masks'},
        ],
    },
    'hyperkvasir-dataset-first-half-and-and-ld-dataset': {
        'role': 'image_multi', 'name': 'HyperKvasir+LD',
        'sub_datasets': [
            {'name': 'HyperKvasir-Seg',
             'img_sub': 'hyper-kvasir-segmented-images-part 3/segmented-images/images',
             'mask_sub': 'hyper-kvasir-segmented-images-part 3/segmented-images/masks'},
        ],
    },
    'polypdb-polyp-raw': {
        'role': 'image_multi', 'name': 'PolypDB',
        'sub_datasets': [
            {'name': 'PolypDB/Simula/NBI',  'img_sub': 'PolypDB/PolypDB/PolypDB_center_wise/Simula/NBI/images',    'mask_sub': 'PolypDB/PolypDB/PolypDB_center_wise/Simula/NBI/masks'},
            {'name': 'PolypDB/Simula/WLI',  'img_sub': 'PolypDB/PolypDB/PolypDB_center_wise/Simula/WLI/images',    'mask_sub': 'PolypDB/PolypDB/PolypDB_center_wise/Simula/WLI/masks'},
            {'name': 'PolypDB/BKAI/WLI',    'img_sub': 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/WLI/images',      'mask_sub': 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/WLI/masks'},
            {'name': 'PolypDB/BKAI/BLI',    'img_sub': 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/BLI/images',      'mask_sub': 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/BLI/masks'},
            {'name': 'PolypDB/BKAI/FICE',   'img_sub': 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/FICE/images',     'mask_sub': 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/FICE/masks'},
            {'name': 'PolypDB/BKAI/LCI',    'img_sub': 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/LCI/images',      'mask_sub': 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/LCI/masks'},
            {'name': 'PolypDB/WLI',         'img_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/WLI/images',         'mask_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/WLI/masks'},
            {'name': 'PolypDB/BLI',         'img_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/BLI/images',         'mask_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/BLI/masks'},
            {'name': 'PolypDB/FICE',        'img_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/FICE/images',        'mask_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/FICE/masks'},
            {'name': 'PolypDB/NBI',         'img_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/NBI/images',         'mask_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/NBI/masks'},
            {'name': 'PolypDB/LCI',         'img_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/LCI/images',         'mask_sub': 'PolypDB/PolypDB/PolypDB_modality_wise/LCI/masks'},
        ],
    },
    'polypgen20021-video':              {'role': 'video_positive', 'name': 'PolypGen2021-Video'},
    'ldpolypvideowithoutpolyps':        {'role': 'video_negative', 'name': 'LDPolyp-NoPolyp'},
    'ldpolypvideopolyponly':            {'role': 'video_positive', 'name': 'LDPolyp-PolypOnly'},
    'hperkvasir-labeled-videos-part2-002': {'role': 'video_positive', 'name': 'HyperKvasir-Video-P2B'},
    'hyperkvasir-labeled-videos-part2-001': {'role': 'video_positive', 'name': 'HyperKvasir-Video-P2A'},
    'cvc-sample-video':                 {'role': 'video_positive', 'name': 'CVC-Video'},
}

def resolve_dataset(ds_key):
    for root, dirs, files in os.walk(INPUT_DIR):
        if ds_key in dirs:
            return os.path.join(root, ds_key)
    return None

RESOLVED = {}
found_count = 0
print('Dataset resolution:')
for key, cfg in DATASET_MAP.items():
    path = resolve_dataset(key)
    RESOLVED[key] = path
    status = 'found' if path else 'NOT FOUND'
    found_count += (1 if path else 0)
    print(f'  [{cfg["role"]:15s}] {key:50s} {status}')
print(f'\\n{found_count}/{len(DATASET_MAP)} resolved.')
"""))

# ── CELL 4: Load models ───────────────────────────────────────────────────────
cells.append(code("""\
# =================================================================
# Load YOLO (shared Stage 1) + Track A (ViT) + Track B (PraNet)
# =================================================================
import torchvision.models as tvm
import torch.nn as nn
import torch.nn.functional as F

# ── Source code ───────────────────────────────────────────────
CODE_PATH = None
for root, dirs, files in os.walk(INPUT_DIR):
    if 'chakranet_segmenter.py' in files and os.path.basename(root) == 'src':
        CODE_PATH = os.path.dirname(root)
        break

if CODE_PATH:
    shutil.copytree(CODE_PATH, f'{WORKING_DIR}/chakramodel', dirs_exist_ok=True)
    src_path = f'{WORKING_DIR}/chakramodel/src'
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    os.chdir(f'{WORKING_DIR}/chakramodel')
    print(f'Source loaded from: {CODE_PATH}')
else:
    print('WARNING: chakranet_segmenter.py not found')

os.makedirs(f'{WORKING_DIR}/chakramodel/weights', exist_ok=True)

# ── Weight discovery (zero hardcoding) ────────────────────────
TRANSFORMER_PTH = None
PRANET_PTH      = None
YOLO_PT         = None
PRANET_NAMES    = {'combo1_best.pth', 'pranet_best.pth', 'resnet101_best.pth',
                   'combo1.pth', 'pranet_resnet101.pth'}

for root, dirs, files in os.walk(INPUT_DIR):
    for f in files:
        full = os.path.join(root, f)
        if f == 'chakra_transformer_best.pth' and TRANSFORMER_PTH is None:
            TRANSFORMER_PTH = full
        if f.lower() in PRANET_NAMES and PRANET_PTH is None:
            PRANET_PTH = full
        if f == 'best.pt' and YOLO_PT is None:
            YOLO_PT = full

print(f'ViT weights    : {TRANSFORMER_PTH or "NOT FOUND"}')
print(f'PraNet weights : {PRANET_PTH or "NOT FOUND"}')
print(f'YOLO weights   : {YOLO_PT or "NOT FOUND"}')

if TRANSFORMER_PTH:
    shutil.copy(TRANSFORMER_PTH, f'{WORKING_DIR}/chakramodel/weights/chakra_transformer_best.pth')
if PRANET_PTH:
    shutil.copy(PRANET_PTH, f'{WORKING_DIR}/chakramodel/weights/combo1_best.pth')
if YOLO_PT:
    shutil.copy(YOLO_PT, f'{WORKING_DIR}/chakramodel/weights/best.pt')

# ── YOLO (shared) ────────────────────────────────────────────
YOLO_MODEL = None
if YOLO_PT:
    try:
        from ultralytics import YOLO
        YOLO_MODEL = YOLO(f'{WORKING_DIR}/chakramodel/weights/best.pt')
        print(f'YOLO loaded on {DEVICE}')
    except Exception as e:
        print(f'YOLO load failed: {e}')

# ── Track A: ViT-Large (via ChakraNet wrapper) ────────────────
VIT_MODEL = None
try:
    from chakranet_segmenter import ChakraNet
    VIT_MODEL = ChakraNet(
        device=DEVICE,
        img_size=(384, 384),
        weights_path=f'{WORKING_DIR}/chakramodel/weights/chakra_transformer_best.pth',
    )
    print(f'Track A (ViT-Large, 309M) loaded on {DEVICE}')
except Exception as e:
    print(f'Track A (ViT) load failed: {e}')

# ── Track B: PraNet ResNet-101 (inline, self-contained) ───────
class _Bconv(nn.Module):
    def __init__(self, ic, oc, k, s=1, p=0, d=1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(ic, oc, k, stride=s, padding=p, dilation=d, bias=False),
            nn.BatchNorm2d(oc), nn.ReLU(inplace=True))
    def forward(self, x): return self.net(x)

class _RFB(nn.Module):
    def __init__(self, ic, oc):
        super().__init__()
        self.b0 = nn.Sequential(_Bconv(ic,oc,1))
        self.b1 = nn.Sequential(_Bconv(ic,oc,1),_Bconv(oc,oc,(1,3),p=(0,1)),_Bconv(oc,oc,(3,1),p=(1,0)),_Bconv(oc,oc,3,p=3,d=3))
        self.b2 = nn.Sequential(_Bconv(ic,oc,1),_Bconv(oc,oc,(1,5),p=(0,2)),_Bconv(oc,oc,(5,1),p=(2,0)),_Bconv(oc,oc,3,p=5,d=5))
        self.b3 = nn.Sequential(_Bconv(ic,oc,1),_Bconv(oc,oc,(1,7),p=(0,3)),_Bconv(oc,oc,(7,1),p=(3,0)),_Bconv(oc,oc,3,p=7,d=7))
        self.cat = _Bconv(4*oc,oc,3,p=1); self.res = _Bconv(ic,oc,1)
    def forward(self, x):
        return F.relu(self.cat(torch.cat([self.b0(x),self.b1(x),self.b2(x),self.b3(x)],1))+self.res(x),True)

class _RA(nn.Module):
    def __init__(self, ic, oc):
        super().__init__()
        self.c1=_Bconv(ic,oc,3,p=1); self.c2=_Bconv(oc,oc,3,p=1); self.out=nn.Conv2d(oc,1,1)
    def forward(self, feat, sal):
        x = feat*(1.0-torch.sigmoid(sal)).expand_as(feat)
        return self.out(self.c2(self.c1(x)))

class PraNetR101(nn.Module):
    def __init__(self, channels=64):
        super().__init__()
        r = tvm.resnet101(weights=tvm.ResNet101_Weights.IMAGENET1K_V2)
        self.stem=nn.Sequential(r.conv1,r.bn1,r.relu,r.maxpool)
        self.l1,self.l2,self.l3,self.l4=r.layer1,r.layer2,r.layer3,r.layer4
        self.r1=_RFB(256,channels); self.r2=_RFB(512,channels)
        self.r3=_RFB(1024,channels); self.r4=_RFB(2048,channels)
        self.ppd=_Bconv(channels*3,channels,3,p=1); self.ppd_out=nn.Conv2d(channels,1,1)
        self.ra4=_RA(channels,channels); self.ra3=_RA(channels,channels)
        self.ra2=_RA(channels,channels); self.ra1=_RA(channels,channels)
    def forward(self, x):
        h,w=x.shape[2:]
        e1=self.l1(self.stem(x)); e2=self.l2(e1); e3=self.l3(e2); e4=self.l4(e3)
        r1=self.r1(e1); r2=self.r2(e2); r3=self.r3(e3); r4=self.r4(e4)
        sz=r2.shape[2:]
        sg=self.ppd_out(self.ppd(torch.cat([r2,F.interpolate(r3,sz,mode='bilinear',align_corners=False),F.interpolate(r4,sz,mode='bilinear',align_corners=False)],1)))
        s4=self.ra4(r4,F.interpolate(sg,r4.shape[2:],mode='bilinear',align_corners=False))
        s3=self.ra3(r3,F.interpolate(s4,r3.shape[2:],mode='bilinear',align_corners=False))
        s2=self.ra2(r2,F.interpolate(s3,r2.shape[2:],mode='bilinear',align_corners=False))
        s1=self.ra1(r1,F.interpolate(s2,r1.shape[2:],mode='bilinear',align_corners=False))
        return F.interpolate(s1,(h,w),mode='bilinear',align_corners=False)

PRANET_MODEL = None
pra_wt = f'{WORKING_DIR}/chakramodel/weights/combo1_best.pth'
if os.path.exists(pra_wt):
    try:
        pranet_raw = PraNetR101(channels=64).to(DEVICE)
        sd = torch.load(pra_wt, map_location=DEVICE, weights_only=True)
        if isinstance(sd, dict) and 'state_dict' in sd: sd = sd['state_dict']
        sd = {k.replace('module.','').replace('_orig_mod.',''): v for k,v in sd.items()}
        miss,unexp = pranet_raw.load_state_dict(sd, strict=False)
        if miss:  print(f'PraNet missing keys: {len(miss)}')
        if unexp: print(f'PraNet unexpected keys: {len(unexp)}')
        pranet_raw.eval()
        PRANET_MODEL = pranet_raw
        param_count = sum(p.numel() for p in PRANET_MODEL.parameters())
        print(f'Track B (PraNet R101, {param_count/1e6:.1f}M params) loaded on {DEVICE}')
    except Exception as e:
        print(f'PraNet load failed: {e}')
        traceback.print_exc()
else:
    print('WARNING: combo1_best.pth not found — Track B will be skipped')

# ── Smoke tests ──────────────────────────────────────────────
if VIT_MODEL is not None:
    try:
        dummy = np.zeros((64,64,3), dtype=np.uint8)
        r = VIT_MODEL.segment_roi(dummy)
        print(f'ViT smoke test OK — returned {type(r).__name__}')
    except Exception as e:
        print(f'ViT smoke test FAILED: {e}')

if PRANET_MODEL is not None:
    try:
        with torch.no_grad():
            out = PRANET_MODEL(torch.zeros(1,3,352,352,device=DEVICE))
        print(f'PraNet smoke test OK — output shape {tuple(out.shape)}')
    except Exception as e:
        print(f'PraNet smoke test FAILED: {e}')
"""))

# ── CELL 5: Utilities ────────────────────────────────────────────────────────
cells.append(code("""\
# =================================================================
# Shared evaluation utilities — no hardcoding, no magic paths
# =================================================================

IMG_EXTS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff'}
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1,1,3)
STD  = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1,1,3)

def smart_join(base, *parts):
    current = base
    for part in parts:
        if not os.path.isdir(current):
            current = os.path.join(current, part); continue
        lmap = {d.lower(): d for d in os.listdir(current)}
        current = os.path.join(current, lmap.get(part.lower(), part))
    return current

def dice_iou(pred, gt):
    p = pred.astype(bool); g = gt.astype(bool)
    inter = (p & g).sum(); union = (p | g).sum()
    return float(2*inter/(p.sum()+g.sum()+1e-8)), float(inter/(union+1e-8))

def find_mask(img_path, mask_dir):
    stem = Path(img_path).stem.lower()
    for f in os.listdir(mask_dir):
        if Path(f).stem.lower()==stem and Path(f).suffix.lower() in IMG_EXTS:
            return os.path.join(mask_dir, f)
    return None

def _pranet_infer(model, crop_bgr, thr=0.45):
    h,w = crop_bgr.shape[:2]
    rgb = cv2.cvtColor(cv2.resize(crop_bgr,(352,352)),cv2.COLOR_BGR2RGB)
    t = torch.from_numpy(((rgb.astype(np.float32)/255.0)-MEAN)/STD).permute(2,0,1).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        logits = model(t)
    prob = torch.sigmoid(logits).squeeze().cpu().numpy()
    mask352 = (prob>thr).astype(np.uint8)*255
    return cv2.resize(mask352,(w,h),interpolation=cv2.INTER_NEAREST)

def _vit_infer(model, crop_bgr):
    try:
        r = model.segment_roi(crop_bgr)
        if isinstance(r, tuple):   return r[0]
        if isinstance(r, np.ndarray): return r
        if isinstance(r, dict):    return r.get('mask', r.get('seg_mask'))
    except Exception: return None

def run_pipeline(img_bgr, yolo, seg_model, infer_fn, fallback=True):
    h,w = img_bgr.shape[:2]
    pred = np.zeros((h,w),dtype=np.uint8)
    boxes = []
    if yolo is not None:
        try:
            res = yolo(img_bgr, verbose=False)
            if res and res[0].boxes is not None and len(res[0].boxes)>0:
                boxes = res[0].boxes.xyxy.cpu().numpy().tolist()
        except Exception: pass
    if not boxes:
        if fallback: boxes=[[0,0,w,h]]
        else: return pred, 0, 0.0
    t0 = time.perf_counter()
    for box in boxes:
        x1,y1,x2,y2=[int(v) for v in box]
        x1,y1=max(0,x1),max(0,y1); x2,y2=min(w,x2),min(h,y2)
        if x2<=x1 or y2<=y1: continue
        crop=img_bgr[y1:y2,x1:x2]
        if crop.size==0: continue
        m = infer_fn(seg_model, crop)
        if m is None: continue
        ch,cw=y2-y1,x2-x1
        if m.shape!=(ch,cw): m=cv2.resize(m.astype(np.uint8),(cw,ch),interpolation=cv2.INTER_NEAREST)
        pred[y1:y2,x1:x2]=np.maximum(pred[y1:y2,x1:x2],m.astype(np.uint8))
    seg_ms=(time.perf_counter()-t0)*1000
    return pred, len(boxes), seg_ms

print('Utilities ready.')
"""))

# ── CELL 6: Comparison evaluator ─────────────────────────────────────────────
cells.append(code("""\
# =================================================================
# Per-dataset side-by-side evaluator
# =================================================================

def evaluate_both(name, img_dir, mask_dir, max_images=200):
    if not os.path.isdir(img_dir):
        print(f'  SKIP {name}: img_dir not found'); return None
    if not os.path.isdir(mask_dir):
        print(f'  SKIP {name}: mask_dir not found'); return None

    imgs = sorted([f for f in os.listdir(img_dir) if Path(f).suffix.lower() in IMG_EXTS])[:max_images]
    if not imgs: print(f'  SKIP {name}: no images'); return None

    vit_d,vit_i,vit_ms = [],[],[]
    pra_d,pra_i,pra_ms = [],[],[]
    n_skip = 0

    for fname in imgs:
        ip = os.path.join(img_dir, fname)
        mp = find_mask(ip, mask_dir)
        if mp is None: n_skip+=1; continue
        img = cv2.imread(ip)
        if img is None: n_skip+=1; continue
        gt = cv2.imread(mp, cv2.IMREAD_GRAYSCALE)
        if gt is None: n_skip+=1; continue
        gt_bin = (gt>127).astype(np.uint8)

        if VIT_MODEL is not None:
            p,_,ms = run_pipeline(img, YOLO_MODEL, VIT_MODEL, _vit_infer, fallback=True)
            d,iou = dice_iou((p>127).astype(np.uint8), gt_bin)
            vit_d.append(d); vit_i.append(iou); vit_ms.append(ms)

        if PRANET_MODEL is not None:
            p,_,ms = run_pipeline(img, YOLO_MODEL, PRANET_MODEL, _pranet_infer, fallback=True)
            d,iou = dice_iou((p>127).astype(np.uint8), gt_bin)
            pra_d.append(d); pra_i.append(iou); pra_ms.append(ms)

    def summ(dices, ious, ms_list, label):
        if not dices: return None
        mms = float(np.mean(ms_list)) if ms_list else 0.0
        return {
            'label': label, 'n': len(dices),
            'dice_mean':   round(float(np.mean(dices)),4),
            'dice_std':    round(float(np.std(dices)), 4),
            'dice_median': round(float(np.median(dices)),4),
            'iou_mean':    round(float(np.mean(ious)),4),
            'seg_ms_mean': round(mms,2),
            'seg_fps':     round(1000.0/mms,1) if mms>0 else 0.0,
        }

    return {
        'name':   name,
        'n_skip': n_skip,
        'vit':    summ(vit_d, vit_i, vit_ms, 'ViT-Large'),
        'pranet': summ(pra_d, pra_i, pra_ms, 'PraNet-R101'),
    }

def run_comparison(name, ds_key, img_sub, mask_sub, max_images=200):
    root = RESOLVED.get(ds_key)
    if not root: print(f'  SKIP {name}: not attached'); return
    img_dir  = smart_join(root, *img_sub.split('/'))
    mask_dir = smart_join(root, *mask_sub.split('/'))
    print(f'  {name} ...')
    r = evaluate_both(name, img_dir, mask_dir, max_images=max_images)
    if r:
        ALL_CMP.append(r)
        v=r['vit'] or {}; p=r['pranet'] or {}
        print(f"    ViT:    dice={v.get('dice_mean','-'):.4f}  ms={v.get('seg_ms_mean','-'):.1f}  fps={v.get('seg_fps',0):.1f}")
        print(f"    PraNet: dice={p.get('dice_mean','-'):.4f}  ms={p.get('seg_ms_mean','-'):.1f}  fps={p.get('seg_fps',0):.1f}")

print('Comparison evaluator ready.')
"""))

# ── CELL 7: Run all ───────────────────────────────────────────────────────────
cells.append(code("""\
# =================================================================
# Run side-by-side on all attached image datasets
# =================================================================
ALL_CMP = []

print('=' * 65)
print('ViT vs PraNet — IMAGE DATASETS')
print('=' * 65)

run_comparison('CVC-300',      'endoscene-cvc300-polyp-raw-dataset',
               'CVC-300/images', 'CVC-300/masks')

run_comparison('CVC-ClinicDB', 'chakramodel-evaluation-datasets',
               'cvc-clinicdb/images', 'cvc-clinicdb/masks')

run_comparison('Kvasir-SEG',   'chakramodel-evaluation-datasets',
               'kvasir-seg/images', 'kvasir-seg/masks')

run_comparison('ETIS-LARIB',   'chakramodel-evaluation-datasets',
               'etis-larib/images', 'etis-larib/masks')

run_comparison('HyperKvasir-Seg',
               'hyperkvasir-dataset-first-half-and-and-ld-dataset',
               'hyper-kvasir-segmented-images-part 3/segmented-images/images',
               'hyper-kvasir-segmented-images-part 3/segmented-images/masks')

POLYPDB_KEY = 'polypdb-polyp-raw'
for sub_name, sub_img, sub_mask in [
    ('PolypDB/Simula/WLI','PolypDB/PolypDB/PolypDB_center_wise/Simula/WLI/images','PolypDB/PolypDB/PolypDB_center_wise/Simula/WLI/masks'),
    ('PolypDB/Simula/NBI','PolypDB/PolypDB/PolypDB_center_wise/Simula/NBI/images','PolypDB/PolypDB/PolypDB_center_wise/Simula/NBI/masks'),
    ('PolypDB/BKAI/WLI',  'PolypDB/PolypDB/PolypDB_center_wise/BKAI/WLI/images',  'PolypDB/PolypDB/PolypDB_center_wise/BKAI/WLI/masks'),
    ('PolypDB/BKAI/BLI',  'PolypDB/PolypDB/PolypDB_center_wise/BKAI/BLI/images',  'PolypDB/PolypDB/PolypDB_center_wise/BKAI/BLI/masks'),
    ('PolypDB/BKAI/FICE', 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/FICE/images', 'PolypDB/PolypDB/PolypDB_center_wise/BKAI/FICE/masks'),
    ('PolypDB/BKAI/LCI',  'PolypDB/PolypDB/PolypDB_center_wise/BKAI/LCI/images',  'PolypDB/PolypDB/PolypDB_center_wise/BKAI/LCI/masks'),
    ('PolypDB/WLI',       'PolypDB/PolypDB/PolypDB_modality_wise/WLI/images',      'PolypDB/PolypDB/PolypDB_modality_wise/WLI/masks'),
    ('PolypDB/BLI',       'PolypDB/PolypDB/PolypDB_modality_wise/BLI/images',      'PolypDB/PolypDB/PolypDB_modality_wise/BLI/masks'),
    ('PolypDB/FICE',      'PolypDB/PolypDB/PolypDB_modality_wise/FICE/images',     'PolypDB/PolypDB/PolypDB_modality_wise/FICE/masks'),
    ('PolypDB/NBI',       'PolypDB/PolypDB/PolypDB_modality_wise/NBI/images',      'PolypDB/PolypDB/PolypDB_modality_wise/NBI/masks'),
    ('PolypDB/LCI',       'PolypDB/PolypDB/PolypDB_modality_wise/LCI/images',      'PolypDB/PolypDB/PolypDB_modality_wise/LCI/masks'),
]:
    run_comparison(sub_name, POLYPDB_KEY, sub_img, sub_mask, max_images=100)

print('\\nAll image comparisons complete.')
"""))

# ── CELL 8: Results table + save ─────────────────────────────────────────────
cells.append(code("""\
# =================================================================
# Final results table + JSON export
# =================================================================

rows = []
for r in ALL_CMP:
    v = r['vit']    or {}
    p = r['pranet'] or {}
    vd = v.get('dice_mean', None)
    pd_ = p.get('dice_mean', None)
    winner = 'ViT' if (vd or 0) > (pd_ or 0) else ('PraNet' if (pd_ or 0) > (vd or 0) else 'Tie')
    rows.append({
        'Dataset':       r['name'],
        'N':             (v or p).get('n', '-'),
        'ViT Dice':      vd,
        'ViT IoU':       v.get('iou_mean'),
        'ViT ms/img':    v.get('seg_ms_mean'),
        'ViT FPS':       v.get('seg_fps'),
        'PraNet Dice':   pd_,
        'PraNet IoU':    p.get('iou_mean'),
        'PraNet ms/img': p.get('seg_ms_mean'),
        'PraNet FPS':    p.get('seg_fps'),
        'Winner':        winner,
    })

df = pd.DataFrame(rows)
print(df.to_string(index=False))

# Summary stats
vit_dices = [r['ViT Dice']    for r in rows if isinstance(r['ViT Dice'],    float)]
pra_dices = [r['PraNet Dice'] for r in rows if isinstance(r['PraNet Dice'], float)]
vit_fps   = [r['ViT FPS']     for r in rows if isinstance(r['ViT FPS'],     float) and r['ViT FPS']>0]
pra_fps   = [r['PraNet FPS']  for r in rows if isinstance(r['PraNet FPS'],  float) and r['PraNet FPS']>0]

print('\\n' + '='*65)
print('SUMMARY')
print('='*65)
vit_wins = sum(1 for r in rows if r['Winner']=='ViT')
pra_wins = sum(1 for r in rows if r['Winner']=='PraNet')
print(f'Dataset wins:  ViT={vit_wins}/{len(rows)}  PraNet={pra_wins}/{len(rows)}')
if vit_dices: print(f'Mean ViT Dice across datasets:    {np.mean(vit_dices):.4f}')
if pra_dices: print(f'Mean PraNet Dice across datasets: {np.mean(pra_dices):.4f}')
if vit_fps:   print(f'Mean ViT Seg FPS:    {np.mean(vit_fps):.1f}')
if pra_fps:   print(f'Mean PraNet Seg FPS: {np.mean(pra_fps):.1f}')

# Save results
out = '/kaggle/working/vit_vs_pranet_comparison.json'
with open(out, 'w') as f:
    json.dump({'comparison': ALL_CMP, 'summary_rows': rows}, f, indent=2)
print(f'\\nResults saved to {out}')
"""))

# ── Assemble notebook ─────────────────────────────────────────────────────────
nb = {
    "nbformat": 4, "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10.0"},
        "accelerator": "GPU"
    },
    "cells": cells
}
for c in nb["cells"]:
    c["id"] = uuid.uuid4().hex[:8]

outpath = r"J:\My Drive\downloads\chakramodel_vit_vs_pranet_comparison.ipynb"
with open(outpath, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print(f"Written: {outpath}  ({len(cells)} cells)")
