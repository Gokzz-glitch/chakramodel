#!/usr/bin/env python3
"""
chakraseg_v3.py — ChakraSeg-v3 training / evaluation harness (29 Sep 2026)

One file, eight sub-commands:
  audit    check a manifest: split inventory, path resolution, negatives, group overlap
  train    train one run (arch x backbone x recipe x seed), then test it (results.json, per_image.csv)
  eval     re-score a finished run on any manifest (new test sets / negatives) without retraining
  summary  aggregate all runs: seed mean +- sd, cost, paired bootstrap vs a reference configuration
  ops      operating-point sweep (presence / peak thresholds) at false-alarm budgets, from per_image.csv
  fps      benchmark inference speed of a configuration
  compare  paired bootstrap of two runs' per-image results

Architectures (--arch):
  v3vit    foundation ViT (DINOv2 / DINOv3 / ImageNet ViT via timm) -> multi-scale
           reassemble + optional CNN spatial-prior branch + U-Net decoder (GroupNorm)
           + optional presence head (image-level p(polyp)); --gate hard zeroes the mask when
           p(polyp) <= --gate-tau (UNet3+ CGM style), --gate mult multiplies (SAM3 style)
  v3conv   hierarchical conv encoder (e.g. DINOv3 ConvNeXt, ResNet) + same decoder/head
  sam2unet official SAM2-UNet (needs --sam2unet-repo and --hiera-ckpt)

Freezing (--freeze): full (layer-wise LR decay) | lora | frozen
Negatives: rows whose split starts with 'neg' or whose mask is empty are treated as
polyp-free (all-zero mask, presence label 0).

Evaluation matches the leakbench conventions: Dice/IoU per image at p>0.5 after resizing the
prediction to the ground-truth size; false alarm on a polyp-free frame = predicted area
> 0.1% of the frame.
"""
import argparse, json, math, os, random, sys, time
from collections import defaultdict

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

import torch
import torch.nn as nn
import torch.nn.functional as F

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
FA_AREA = 0.001  # fraction of frame

# ---------------------------------------------------------------- manifest ----
IMG_COLS = ["image", "image_path", "img", "img_path", "path", "frame", "file"]
MASK_COLS = ["mask", "mask_path", "gt", "gt_path", "label_path"]
SPLIT_COLS = ["split", "subset", "set", "partition"]
GROUP_COLS = ["group", "group_id", "video", "sequence", "seq"]


def _pick(cols, cands):
    low = {c.lower(): c for c in cols}
    for c in cands:
        if c in low:
            return low[c]
    return None


def _norm(p):
    if p is None:
        return None
    if isinstance(p, float) and math.isnan(p):
        return None
    p = str(p).strip()
    if p == "" or p.lower() in ("none", "nan", "null", "-"):
        return None
    return p.replace("\\", "/")


class PathResolver:
    """Resolve manifest paths against a list of roots, optional prefix maps, and a
    suffix index (last 3 path components) built lazily for anything still missing."""

    def __init__(self, roots, path_maps=(), manifest_dir=None):
        self.roots = [r for r in roots if r and os.path.isdir(r)]
        if manifest_dir:  # the manifest's folder and its parent (datasets often keep manifests/ under the root)
            self.roots += [manifest_dir, os.path.dirname(manifest_dir)]
        self.maps = []
        for m in path_maps:
            if "=" in m:
                a, b = m.split("=", 1)
                self.maps.append((a.replace("\\", "/"), b))
        self._index = None
        self.hits = defaultdict(int)

    def _build_index(self):
        idx = {}
        for r in self.roots:
            for dp, _, fs in os.walk(r):
                for f in fs:
                    full = os.path.join(dp, f)
                    parts = full.replace("\\", "/").split("/")
                    for k in (3, 2):
                        if len(parts) >= k:
                            idx.setdefault("/".join(parts[-k:]).lower(), full)
        self._index = idx

    def __call__(self, p):
        p = _norm(p)
        if p is None:
            return None
        if os.path.isfile(p):
            self.hits["as_is"] += 1
            return p
        for a, b in self.maps:
            if p.startswith(a):
                q = os.path.join(b, p[len(a):].lstrip("/"))
                if os.path.isfile(q):
                    self.hits["mapped"] += 1
                    return q
        rel = p.lstrip("/")
        if len(rel) > 2 and rel[1] == ":":  # windows drive letter
            rel = rel[2:].lstrip("/")
        for r in self.roots:
            q = os.path.join(r, rel)
            if os.path.isfile(q):
                self.hits["root"] += 1
                return q
        if self._index is None:
            self._build_index()
        parts = rel.split("/")
        for k in (3, 2):
            if len(parts) >= k:
                q = self._index.get("/".join(parts[-k:]).lower())
                if q:
                    self.hits[f"suffix{k}"] += 1
                    return q
        self.hits["missing"] += 1
        return None


def load_manifest(path, roots, path_maps=()):
    import pandas as pd
    sep = "\t" if path.endswith(".tsv") else ","
    df = pd.read_csv(path, sep=sep, dtype=str, keep_default_na=False)
    ic, mc = _pick(df.columns, IMG_COLS), _pick(df.columns, MASK_COLS)
    sc, gc = _pick(df.columns, SPLIT_COLS), _pick(df.columns, GROUP_COLS)
    if ic is None:
        raise SystemExit(f"[manifest] no image column in {list(df.columns)}")
    res = PathResolver(roots, path_maps, os.path.dirname(os.path.abspath(path)))
    rows = []
    for _, r in df.iterrows():
        split = (r[sc] if sc else os.path.splitext(os.path.basename(path))[0]).strip() or "unspecified"
        img = res(r[ic])
        msk_raw = _norm(r[mc]) if mc else None
        msk = res(msk_raw) if msk_raw else None
        neg = split.lower().startswith("neg") or msk_raw is None
        rows.append(dict(image=img, mask=msk, split=split, neg=bool(neg),
                         group=(r[gc] if gc else ""), raw_image=r[ic], raw_mask=msk_raw))
    return rows, dict(res.hits), dict(image=ic, mask=mc, split=sc, group=gc)


def split_rows(rows):
    d = defaultdict(list)
    for r in rows:
        d[r["split"]].append(r)
    return d


# ----------------------------------------------------------------- dataset ----
def read_rgb(p):
    im = cv2.imread(p, cv2.IMREAD_COLOR)
    if im is None:
        raise IOError(f"cannot read image {p}")
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB)


def read_mask(p, shape):
    if p is None:
        return np.zeros(shape[:2], np.uint8)
    m = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if m is None:
        raise IOError(f"cannot read mask {p}")
    if m.shape[:2] != shape[:2]:
        m = cv2.resize(m, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
    return (m > 127).astype(np.uint8)


def degrade(im):
    """Acquisition-degradation augmentation (Part 3 anatomy: unseen test sets are 2.5-4.7x blurrier at
    network resolution and lower-contrast than Kvasir). One of: gaussian/defocus blur, linear motion blur,
    down-up resampling, JPEG re-encoding."""
    # strengths calibrated on Kvasir at 352 px so the median Laplacian-variance ratio (~0.2-0.3) matches the
    # unseen test sets' sharpness relative to Kvasir (ColonDB 0.30, ETIS 0.29, CVC-300 0.21; Part 3 section 2)
    k = random.random()
    if k < 0.3:
        s = random.uniform(0.4, 0.85)
        return cv2.GaussianBlur(im, (0, 0), s)
    if k < 0.55:
        L = random.choice([3, 5, 5, 7])
        ker = np.zeros((L, L), np.float32); ker[L // 2, :] = 1.0 / L
        M = cv2.getRotationMatrix2D((L / 2 - 0.5, L / 2 - 0.5), random.uniform(0, 180), 1.0)
        ker = cv2.warpAffine(ker, M, (L, L)); ker /= max(ker.sum(), 1e-6)
        return cv2.filter2D(im, -1, ker)
    if k < 0.8:
        h, w = im.shape[:2]; f = random.uniform(0.55, 0.85)
        small = cv2.resize(im, (max(8, int(w * f)), max(8, int(h * f))), interpolation=cv2.INTER_AREA)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    q = random.randint(30, 70)
    ok, enc = cv2.imencode(".jpg", im[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)[:, :, ::-1] if ok else im


def lab_jitter(im):
    """Colour-distribution shift in Lab (in the spirit of SANet's colour exchange): shifts L/a/b means
    and rescales their spread, so the model cannot rely on Kvasir's high polyp/surround colour contrast."""
    lab = cv2.cvtColor(np.ascontiguousarray(im), cv2.COLOR_RGB2LAB).astype(np.float32)
    for c, sd in ((0, 10.0), (1, 6.0), (2, 6.0)):
        mu = lab[..., c].mean()
        lab[..., c] = (lab[..., c] - mu) * random.uniform(0.8, 1.2) + mu + random.gauss(0, sd)
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


class SegDataset(torch.utils.data.Dataset):
    def __init__(self, rows, size, train, deg_p=0.0, lab_p=0.0):
        self.rows = [r for r in rows if r["image"] is not None and (r["neg"] or r["mask"] is not None)]
        self.dropped = len(rows) - len(self.rows)
        self.size, self.train = size, train
        self.deg_p, self.lab_p = deg_p, lab_p

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        im = read_rgb(r["image"])
        m = read_mask(None if r["neg"] else r["mask"], im.shape)
        s = self.size
        im = cv2.resize(im, (s, s), interpolation=cv2.INTER_LINEAR)
        m = cv2.resize(m, (s, s), interpolation=cv2.INTER_NEAREST)
        if self.train:
            if random.random() < 0.5:
                im, m = im[:, ::-1], m[:, ::-1]
            if random.random() < 0.5:
                im, m = im[::-1], m[::-1]
            k = random.randint(0, 3)
            im, m = np.rot90(im, k), np.rot90(m, k)
            im = np.ascontiguousarray(im)
            if self.deg_p and random.random() < self.deg_p:
                im = degrade(im)
            if self.lab_p and random.random() < self.lab_p:
                im = lab_jitter(im)
            if random.random() < 0.8:  # brightness / contrast / saturation jitter
                im = im.astype(np.float32)
                im = im * random.uniform(0.8, 1.2) + random.uniform(-20, 20)
                g = im.mean(axis=2, keepdims=True)
                im = g + (im - g) * random.uniform(0.8, 1.2)
                im = np.clip(im, 0, 255)
        im = (np.ascontiguousarray(im).astype(np.float32) / 255.0 - MEAN) / STD
        x = torch.from_numpy(im.transpose(2, 0, 1).copy())
        y = torch.from_numpy(np.ascontiguousarray(m).astype(np.float32))[None]
        pres = torch.tensor([float(y.sum() > 0)])
        return x, y, pres


class EvalDataset(torch.utils.data.Dataset):
    """Returns the resized input plus the ORIGINAL-resolution mask (as uint8) for exact scoring."""

    def __init__(self, rows, size):
        self.rows = [r for r in rows if r["image"] is not None and (r["neg"] or r["mask"] is not None)]
        self.size = size

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        im = read_rgb(r["image"])
        m = read_mask(None if r["neg"] else r["mask"], im.shape)
        x = cv2.resize(im, (self.size, self.size), interpolation=cv2.INTER_LINEAR)
        x = (x.astype(np.float32) / 255.0 - MEAN) / STD
        return torch.from_numpy(x.transpose(2, 0, 1).copy()), torch.from_numpy(m), i


def eval_collate(b):
    return torch.stack([t[0] for t in b]), [t[1] for t in b], [t[2] for t in b]


# ------------------------------------------------------------------ models ----
def gn(c):
    return nn.GroupNorm(math.gcd(32, c), c)


class ConvGN(nn.Sequential):
    def __init__(self, cin, cout, k=3):
        super().__init__(nn.Conv2d(cin, cout, k, padding=k // 2, bias=False), gn(cout), nn.GELU())


class LoRALinear(nn.Module):
    def __init__(self, base: nn.Linear, r=16, alpha=32):
        super().__init__()
        self.base = base
        for p in self.base.parameters():
            p.requires_grad = False
        self.r, self.scale = r, alpha / r
        self.A = nn.Parameter(torch.zeros(r, base.in_features))
        self.B = nn.Parameter(torch.zeros(base.out_features, r))
        nn.init.kaiming_uniform_(self.A, a=math.sqrt(5))

    def forward(self, x):
        return self.base(x) + (x @ self.A.t() @ self.B.t()) * self.scale


def add_lora(vit, r, alpha, targets=("qkv",)):
    n = 0
    for blk in vit.blocks:
        if "qkv" in targets and hasattr(blk.attn, "qkv"):
            blk.attn.qkv = LoRALinear(blk.attn.qkv, r, alpha); n += 1
        if "fc1" in targets and hasattr(blk.mlp, "fc1"):
            blk.mlp.fc1 = LoRALinear(blk.mlp.fc1, r, alpha); n += 1
        if "fc2" in targets and hasattr(blk.mlp, "fc2"):
            blk.mlp.fc2 = LoRALinear(blk.mlp.fc2, r, alpha); n += 1
    return n



class InputNorm(nn.Module):
    """The data pipeline normalises with ImageNet mean/std. Backbones pretrained with other statistics (the
    augreg ViTs use mean = std = 0.5) get an exact affine conversion; for ImageNet-stat backbones it is the identity."""

    def __init__(self, timm_model):
        super().__init__()
        cfg = getattr(timm_model, "pretrained_cfg", None) or {}
        m = torch.tensor(cfg.get("mean", tuple(MEAN)), dtype=torch.float32)
        s = torch.tensor(cfg.get("std", tuple(STD)), dtype=torch.float32)
        self.register_buffer("scale", (torch.from_numpy(STD) / s).view(1, 3, 1, 1), persistent=False)
        self.register_buffer("shift", ((torch.from_numpy(MEAN) - m) / s).view(1, 3, 1, 1), persistent=False)
        self.identity = bool(torch.allclose(self.scale, torch.ones_like(self.scale)) and
                             torch.allclose(self.shift, torch.zeros_like(self.shift), atol=1e-6))

    def forward(self, x):
        return x if self.identity else x * self.scale + self.shift

class ViTPyramid(nn.Module):
    """Plain ViT -> 4-level pyramid (x4, x2, x1, x0.5 of the token grid), DPT-style reassemble."""

    def __init__(self, name, pretrained, img_size, dim, freeze, lora_r, lora_alpha, grad_ckpt, drop_path=0.0,
                 backbone_ckpt=""):
        super().__init__()
        import timm
        self.vit = timm.create_model(name, pretrained=pretrained, num_classes=0, drop_path_rate=drop_path,
                                     dynamic_img_size=True, img_size=img_size)
        if backbone_ckpt:  # e.g. ssl_continue.py output (in-domain continued pretraining, Part 4)
            sd = torch.load(backbone_ckpt, map_location="cpu")
            sd = sd.get("state_dict", sd) if isinstance(sd, dict) else sd
            sd.pop("pos_embed", None)  # keep this model's pos_embed at its own grid
            res = self.vit.load_state_dict(sd, strict=False)
            if res.unexpected_keys or any(k != "pos_embed" for k in res.missing_keys):
                raise RuntimeError(f"backbone ckpt mismatch: missing {res.missing_keys[:5]} unexpected {res.unexpected_keys[:5]}")
            print(f"[model] loaded in-domain backbone weights from {backbone_ckpt}")
        self.inorm = InputNorm(self.vit)
        self.patch = self.vit.patch_embed.patch_size[0]
        L = len(self.vit.blocks)
        self.take = [L // 4 - 1, L // 2 - 1, 3 * L // 4 - 1, L - 1]
        E = self.vit.embed_dim
        if freeze in ("lora", "frozen"):
            for p in self.vit.parameters():
                p.requires_grad = False
        if freeze == "lora":
            add_lora(self.vit, lora_r, lora_alpha)
        if grad_ckpt:
            self.vit.set_grad_checkpointing(True)
        self.re = nn.ModuleList([
            nn.Sequential(nn.Conv2d(E, dim, 1), nn.ConvTranspose2d(dim, dim, 4, 4), gn(dim)),
            nn.Sequential(nn.Conv2d(E, dim, 1), nn.ConvTranspose2d(dim, dim, 2, 2), gn(dim)),
            nn.Sequential(nn.Conv2d(E, dim, 1), gn(dim)),
            nn.Sequential(nn.Conv2d(E, dim, 1), nn.Conv2d(dim, dim, 3, 2, 1), gn(dim)),
        ])
        self.embed_dim = E
        self.has_cls = getattr(self.vit, "num_prefix_tokens", 0) > 0

    def forward(self, x):
        inter = self.vit.forward_intermediates(self.inorm(x), indices=self.take, norm=True, output_fmt="NCHW",
                                               intermediates_only=True, return_prefix_tokens=True)
        feats, prefix = [], None
        for t in inter:
            if isinstance(t, (tuple, list)):
                t, pre = t
                prefix = pre
            feats.append(t)
        pyr = [m(f) for m, f in zip(self.re, feats)]
        cls = prefix[:, 0] if (prefix is not None and prefix.shape[1] > 0) else None
        return pyr, cls


class ConvPyramid(nn.Module):
    def __init__(self, name, pretrained, dim, freeze):
        super().__init__()
        import timm
        self.net = timm.create_model(name, pretrained=pretrained, features_only=True,
                                     out_indices=(0, 1, 2, 3))
        chs = self.net.feature_info.channels()
        self.inorm = InputNorm(self.net)
        if freeze == "frozen":
            for p in self.net.parameters():
                p.requires_grad = False
        self.proj = nn.ModuleList([nn.Sequential(nn.Conv2d(c, dim, 1), gn(dim)) for c in chs])
        self.embed_dim = chs[-1]
        self.has_cls = False

    def forward(self, x):
        fs = self.net(self.inorm(x))
        return [p(f) for p, f in zip(self.proj, fs)], None


class CNNPrior(nn.Module):
    """Trainable CNN branch (spatial prior) fused into the ViT pyramid (ASPS / ViT-Adapter idea)."""

    def __init__(self, name, pretrained, dim, xattn):
        super().__init__()
        import timm
        self.net = timm.create_model(name, pretrained=pretrained, features_only=True, out_indices=(1, 2, 3, 4))
        self.inorm = InputNorm(self.net)
        chs = self.net.feature_info.channels()
        self.proj = nn.ModuleList([nn.Sequential(nn.Conv2d(c, dim, 1), gn(dim)) for c in chs])
        self.fuse = nn.ModuleList([nn.Sequential(ConvGN(2 * dim, dim, 1), ConvGN(dim, dim, 3)) for _ in chs])
        self.xattn = nn.MultiheadAttention(dim, 8, batch_first=True) if xattn else None
        self.xnorm = nn.LayerNorm(dim) if xattn else None

    def forward(self, x, pyr):
        cs = [p(f) for p, f in zip(self.proj, self.net(self.inorm(x)))]
        out = []
        for i, (v, c) in enumerate(zip(pyr, cs)):
            c = F.interpolate(c, size=v.shape[-2:], mode="bilinear", align_corners=False)
            f = self.fuse[i](torch.cat([v, c], 1)) + v
            if self.xattn is not None and i == len(pyr) - 1:
                B, C, H, W = f.shape
                q = f.flatten(2).transpose(1, 2)
                kv = c.flatten(2).transpose(1, 2)
                a, _ = self.xattn(self.xnorm(q), kv, kv, need_weights=False)
                f = f + a.transpose(1, 2).reshape(B, C, H, W)
            out.append(f)
        return out


class UNetDecoder(nn.Module):
    def __init__(self, dim, aux):
        super().__init__()
        self.blocks = nn.ModuleList([nn.Sequential(ConvGN(2 * dim, dim), ConvGN(dim, dim)) for _ in range(3)])
        self.head = nn.Sequential(ConvGN(dim, dim // 2), nn.Conv2d(dim // 2, 1, 1))
        self.aux = nn.ModuleList([nn.Conv2d(dim, 1, 1) for _ in range(2)]) if aux else None

    def forward(self, pyr):
        x = pyr[3]
        auxo = []
        for j, skip in enumerate([pyr[2], pyr[1], pyr[0]]):
            x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
            x = self.blocks[j](torch.cat([x, skip], 1))
            if self.aux is not None and j < 2:
                auxo.append(self.aux[j](x))
        return self.head(x), auxo


class ChakraSegV3(nn.Module):
    def __init__(self, a):
        super().__init__()
        self.kind = a.arch
        if a.arch == "v3vit":
            self.enc = ViTPyramid(a.backbone, a.pretrained, a.img_size, a.dim, a.freeze,
                                  a.lora_r, a.lora_alpha, a.grad_ckpt, getattr(a, "drop_path", 0.0),
                                  getattr(a, "backbone_ckpt", ""))
            self.prior = CNNPrior(a.cnn_branch, a.pretrained, a.dim, a.xattn_fuse) if a.cnn_branch != "none" else None
        else:
            self.enc = ConvPyramid(a.backbone, a.pretrained, a.dim, a.freeze)
            self.prior = None
        self.dec = UNetDecoder(a.dim, a.aux)
        self.presence = None
        if a.presence:
            pin = a.dim + (self.enc.embed_dim if getattr(self.enc, "has_cls", False) else 0)
            self.presence = nn.Sequential(nn.Linear(pin, 256), nn.GELU(), nn.Dropout(0.1), nn.Linear(256, 1))

    def forward(self, x):
        pyr, cls = self.enc(x)
        if self.prior is not None:
            pyr = self.prior(x, pyr)
        mask, aux = self.dec(pyr)
        size = x.shape[-2:]
        mask = F.interpolate(mask, size=size, mode="bilinear", align_corners=False)
        aux = [F.interpolate(t, size=size, mode="bilinear", align_corners=False) for t in aux]
        pres = None
        if self.presence is not None:
            g = F.adaptive_avg_pool2d(pyr[3], 1).flatten(1)
            if cls is not None:
                g = torch.cat([g, cls], 1)
            pres = self.presence(g)
        return mask, aux, pres


class SAM2UNetWrap(nn.Module):
    def __init__(self, a):
        super().__init__()
        sys.path.insert(0, a.sam2unet_repo)
        import sam2.build_sam as bs  # vendored in the official repo
        if not torch.cuda.is_available():  # build_sam2 defaults to device="cuda"
            import functools
            bs.build_sam2 = functools.partial(bs.build_sam2, device="cpu")
        import SAM2UNet as S
        S.build_sam2 = bs.build_sam2
        self.m = S.SAM2UNet(a.hiera_ckpt or None)

    def forward(self, x):
        p0, p1, p2 = self.m(x)
        size = x.shape[-2:]
        up = lambda t: F.interpolate(t, size=size, mode="bilinear", align_corners=False)
        return up(p0), [up(p1), up(p2)], None


def build_model(a):
    if a.arch == "sam2unet":
        return SAM2UNetWrap(a)
    return ChakraSegV3(a)


def size_multiple(a):
    if a.arch == "v3vit":
        import re
        m = re.search(r"patch(\d+)", a.backbone)
        return int(m.group(1)) if m else 16
    return 32


# ------------------------------------------------------------------ losses ----
def structure_loss(pred, mask):
    weit = 1 + 5 * torch.abs(F.avg_pool2d(mask, kernel_size=31, stride=1, padding=15) - mask)
    wbce = F.binary_cross_entropy_with_logits(pred, mask, reduction="none")
    wbce = (weit * wbce).sum(dim=(2, 3)) / weit.sum(dim=(2, 3))
    p = torch.sigmoid(pred)
    inter = ((p * mask) * weit).sum(dim=(2, 3))
    union = ((p + mask) * weit).sum(dim=(2, 3))
    wiou = 1 - (inter + 1) / (union - inter + 1)
    return wbce + wiou  # per-sample, shape (B, 1)


# ------------------------------------------------------------- optimiser ----
def param_groups(model, a):
    groups = []
    seen = set()

    def add(params, lr, wd, tag):
        ps = [p for p in params if p.requires_grad and id(p) not in seen]
        for p in ps:
            seen.add(id(p))
        dec = [p for p in ps if p.ndim > 1]
        nod = [p for p in ps if p.ndim <= 1]
        if dec:
            groups.append(dict(params=dec, lr=lr, weight_decay=wd, tag=tag))
        if nod:
            groups.append(dict(params=nod, lr=lr, weight_decay=0.0, tag=tag + "_nd"))

    if a.arch == "v3vit":
        vit = model.enc.vit
        if a.freeze == "full":
            L = len(vit.blocks)
            for n, p in vit.named_parameters():
                if not p.requires_grad:
                    continue
                if n.startswith("blocks."):
                    lid = int(n.split(".")[1]) + 1
                elif any(k in n for k in ("patch_embed", "pos_embed", "cls_token", "reg_token")):
                    lid = 0
                else:
                    lid = L + 1
                add([p], a.lr * a.llrd ** (L + 1 - lid), a.wd, f"vit{lid}")
        else:  # LoRA params (if any) train at the head LR
            add([p for p in vit.parameters()], a.lr, a.wd, "lora")
        if model.prior is not None:
            add(model.prior.net.parameters(), a.lr_cnn, a.wd, "cnn")
    elif a.arch == "v3conv":
        net = model.enc.net
        # stage-wise decay for hierarchical backbones (deepest stage = lr_backbone)
        named = list(net.named_parameters())
        n_st = 4
        for n, p in named:
            st = 0
            for k in range(n_st):
                if f"stages.{k}" in n or f"stages_{k}" in n or f"layer{k + 1}" in n:
                    st = k
            add([p], a.lr_backbone * a.llrd ** (n_st - 1 - st), a.wd, f"stage{st}")
    else:  # sam2unet: official recipe trains adapters + decoder with one LR
        pass
    add(model.parameters(), a.lr, a.wd, "head")
    return groups


def lr_at(step, total, warm, base):
    if step < warm:
        return base * (step + 1) / warm
    t = (step - warm) / max(1, total - warm)
    return base * (0.01 + 0.99 * 0.5 * (1 + math.cos(math.pi * t)))


# ------------------------------------------------------------- evaluation ----
@torch.no_grad()
def predict_probs(model, x, use_presence=True, tta=False, gate="hard", tau=0.5):
    """Returns (gated prob, raw prob, presence prob).
    gate='hard' (default, UNet3+ CGM style): mask kept unchanged when p(polyp) > tau, zeroed otherwise.
    gate='mult' (SAM3 style): mask prob multiplied by p(polyp) -- shrinks borderline positives."""
    mask, _, pres = model(x)
    p = torch.sigmoid(mask.float())
    if tta:
        m2, _, pr2 = model(torch.flip(x, dims=[3]))
        p = 0.5 * (p + torch.flip(torch.sigmoid(m2.float()), dims=[3]))
        if pres is not None:
            pres = 0.5 * (pres + pr2)
    raw = p
    pp = torch.sigmoid(pres.float()).view(-1) if pres is not None else None
    if pp is not None and use_presence:
        g = pp.view(-1, 1, 1, 1)
        p = p * g if gate == "mult" else p * (g > tau).float()
    return p, raw, pp


def score_split(model, rows, a, device, name):
    ds = EvalDataset(rows, a.img_size)
    dl = torch.utils.data.DataLoader(ds, batch_size=a.eval_bs, shuffle=False, num_workers=a.workers,
                                     collate_fn=eval_collate)
    per = []
    model.eval()
    for x, ms, idx in dl:
        x = x.to(device, non_blocking=True)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=(bool(a.amp) and device.type == "cuda")):
            pg, pr, pp = predict_probs(model, x, use_presence=True, tta=a.tta,
                                       gate=getattr(a, "gate", "hard"), tau=getattr(a, "gate_tau", 0.5))
        for b in range(x.shape[0]):
            gt = ms[b].numpy().astype(bool)
            H, W = gt.shape
            rec = dict(split=name, image=ds.rows[idx[b]]["image"], neg=ds.rows[idx[b]]["neg"],
                       gt_area=float(gt.mean()),
                       presence=(float(pp[b]) if pp is not None else float("nan")))
            for tag, prob in (("gated", pg), ("raw", pr)):
                pm = F.interpolate(prob[b:b + 1], size=(H, W), mode="bilinear", align_corners=False)[0, 0]
                pm = pm.float().cpu().numpy()
                pb = pm > 0.5
                inter = float((pb & gt).sum()); ps = float(pb.sum()); gs = float(gt.sum())
                rec[f"{tag}_area"] = ps / (H * W)
                rec[f"{tag}_peak"] = float(pm.max())
                if gs > 0:
                    rec[f"{tag}_dice"] = (2 * inter + 1e-8) / (ps + gs + 1e-8)
                    rec[f"{tag}_iou"] = (inter + 1e-8) / (ps + gs - inter + 1e-8)
                    rec[f"{tag}_hit"] = float(inter > 0)
                else:
                    rec[f"{tag}_fa"] = float(ps / (H * W) > FA_AREA)
            per.append(rec)
    return per


def summarise(per):
    out = {}
    by = defaultdict(list)
    for r in per:
        by[r["split"]].append(r)
    for s, rs in by.items():
        d = dict(n=len(rs))
        for tag in ("gated", "raw"):
            dice = [r[f"{tag}_dice"] for r in rs if f"{tag}_dice" in r]
            fa = [r[f"{tag}_fa"] for r in rs if f"{tag}_fa" in r]
            if dice:
                d[f"{tag}_mDice"] = float(np.mean(dice))
                d[f"{tag}_mIoU"] = float(np.mean([r[f"{tag}_iou"] for r in rs if f"{tag}_iou" in r]))
                d[f"{tag}_detect"] = float(np.mean([r[f"{tag}_hit"] for r in rs if f"{tag}_hit" in r]))
                d["n_pos"] = len(dice)
                d[f"{tag}_dice_sd"] = float(np.std(dice))
            if fa:
                d[f"{tag}_fa_rate"] = float(np.mean(fa))
                d["n_neg"] = len(fa)
        out[s] = d
    return out


# ------------------------------------------------------------------- train ----
def seed_all(s):
    random.seed(s); np.random.seed(s); torch.manual_seed(s); torch.cuda.manual_seed_all(s)


def count_params(m):
    t = sum(p.numel() for p in m.parameters())
    tr = sum(p.numel() for p in m.parameters() if p.requires_grad)
    return t, tr


def cmd_train(a):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    seed_all(a.seed)
    rows, hits, cols = load_manifest(a.manifest, a.roots, a.path_map)
    sp = split_rows(rows)
    tr_rows = [r for s in a.train_splits for r in sp.get(s, [])]
    va_rows = sp.get(a.val_split, [])
    if not tr_rows:
        raise SystemExit(f"[train] no rows in train splits {a.train_splits}; have {sorted(sp)}")
    run = a.run_name or f"{a.arch}_{a.backbone.split('.')[0]}_{a.freeze}_cnn-{a.cnn_branch}_pres{int(a.presence)}_s{a.seed}"
    out = os.path.join(a.out, run)
    os.makedirs(out, exist_ok=True)
    if os.path.isfile(os.path.join(out, "results.json")) and not a.overwrite:
        print(f"[train] {run} already has results.json; skip (use --overwrite)")
        return
    if not a.pretrained:
        a.save_full = 1  # frozen weights are random -> must be saved to be reproducible
    json.dump(vars(a), open(os.path.join(out, "config.json"), "w"), indent=1, default=str)
    model = build_model(a).to(device)
    tot, trn = count_params(model)
    print(f"[model] {run}: params total {tot / 1e6:.1f}M, trainable {trn / 1e6:.2f}M | resolve {hits} | cols {cols}")
    ds = SegDataset(tr_rows, a.img_size, train=True, deg_p=a.deg_aug, lab_p=a.lab_aug)
    n_neg = sum(r["neg"] for r in ds.rows)
    print(f"[data] train {len(ds)} ({n_neg} polyp-free), dropped {ds.dropped}; val {len(va_rows)}")
    dl = torch.utils.data.DataLoader(ds, batch_size=a.bs, shuffle=True, num_workers=a.workers,
                                     drop_last=True, pin_memory=(device.type == "cuda"))
    groups = param_groups(model, a) if a.arch != "sam2unet" else \
        [dict(params=[p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=a.wd)]
    for g in groups:
        g["base_lr"] = g["lr"]
    opt = torch.optim.AdamW(groups, lr=a.lr, weight_decay=a.wd)
    scaler = torch.amp.GradScaler("cuda", enabled=(bool(a.amp) and device.type == "cuda"))
    steps_per_epoch = max(1, len(dl) // a.accum)
    total, warm = a.epochs * steps_per_epoch, a.warmup_epochs * steps_per_epoch
    mult = size_multiple(a)
    rates = [float(r) for r in a.ms_rates.split(",")] if a.ms_rates else [1.0]
    best, best_ep, step, log = -1.0, -1, 0, []
    t0 = time.time()
    for ep in range(a.epochs):
        model.train()
        tl, tn = 0.0, 0
        opt.zero_grad(set_to_none=True)
        for it, (x, y, pres) in enumerate(dl):
            x, y, pres = x.to(device, non_blocking=True), y.to(device), pres.to(device)
            r = random.choice(rates)
            if r != 1.0:
                s = int(round(a.img_size * r / mult) * mult)
                x = F.interpolate(x, size=(s, s), mode="bilinear", align_corners=False)
                y = (F.interpolate(y, size=(s, s), mode="bilinear", align_corners=False) > 0.5).float()
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=(bool(a.amp) and device.type == "cuda")):
                mask, aux, pl = model(x)
            mask, aux = mask.float(), [t.float() for t in aux]
            w = torch.ones_like(pres)
            if not a.mask_loss_on_neg:
                w = pres  # SAM3-style decoupling: masks supervised only where a polyp exists
            lm = (structure_loss(mask, y) * w).sum() / w.sum().clamp_min(1)
            for t in aux:
                lm = lm + a.aux_w * (structure_loss(t, y) * w).sum() / w.sum().clamp_min(1)
            loss = lm
            if pl is not None:
                loss = loss + a.presence_w * F.binary_cross_entropy_with_logits(pl.float(), pres)
            scaler.scale(loss / a.accum).backward()
            if (it + 1) % a.accum == 0:
                for g in opt.param_groups:
                    g["lr"] = lr_at(step, total, warm, g["base_lr"])
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], a.clip)
                scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
                step += 1
            tl += float(loss.detach()) * x.shape[0]; tn += x.shape[0]
            if a.max_iters and it + 1 >= a.max_iters:
                break
        rec = dict(epoch=ep, loss=tl / max(1, tn), time_min=(time.time() - t0) / 60)
        if va_rows and ((ep + 1) % a.eval_every == 0 or ep == a.epochs - 1):
            s = summarise(score_split(model, va_rows, a, device, a.val_split)).get(a.val_split, {})
            rec.update({k: v for k, v in s.items() if k in ("gated_mDice", "gated_fa_rate", "raw_mDice")})
            crit = s.get("gated_mDice", -1)
            if crit > best:
                best, best_ep = crit, ep
                torch.save(trainable_state(model, a.save_full), os.path.join(out, "best.pt"))
        log.append(rec)
        print(f"[ep {ep:03d}] " + " ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in rec.items()), flush=True)
        if a.max_epochs_time and (time.time() - t0) / 3600 > a.max_epochs_time:
            print("[train] time budget hit; stopping"); break
    json.dump(log, open(os.path.join(out, "log.json"), "w"), indent=1)
    if best_ep < 0:  # no val split -> keep last
        torch.save(trainable_state(model, a.save_full), os.path.join(out, "best.pt"))
    load_trainable(model, torch.load(os.path.join(out, "best.pt"), map_location=device))
    test_and_write(model, a, device, sp, out, dict(best_epoch=best_ep, best_val=best, params_total=tot,
                                                   params_trainable=trn, train_n=len(ds), train_neg=n_neg,
                                                   minutes=(time.time() - t0) / 60, run=run))


def trainable_state(model, full):
    sd = model.state_dict()
    if full:
        return sd
    keep = {n for n, p in model.named_parameters() if p.requires_grad}
    keep |= {n for n, _ in model.named_buffers()}
    return {k: v for k, v in sd.items() if k in keep}


def load_trainable(model, sd):
    missing, unexpected = model.load_state_dict(sd, strict=False)
    if unexpected:
        raise RuntimeError(f"unexpected keys when loading: {unexpected[:5]}")
    return missing


def test_and_write(model, a, device, sp, out, meta):
    per = []
    names = [s for s in sorted(sp) if any(s.lower().startswith(p) for p in a.test_prefixes)]
    for s in names:
        t1 = time.time()
        per += score_split(model, sp[s], a, device, s)
        print(f"[test] {s}: {len(sp[s])} rows in {time.time() - t1:.0f}s", flush=True)
    summ = summarise(per)
    fps = benchmark_fps(model, a, device) if device.type == "cuda" else None
    res = dict(meta=meta, fps=fps, splits=summ)
    json.dump(res, open(os.path.join(out, "results.json"), "w"), indent=1)
    import csv
    keys = sorted({k for r in per for k in r})
    with open(os.path.join(out, "per_image.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(per)
    print(json.dumps(res, indent=1)[:4000])


@torch.no_grad()
def benchmark_fps(model, a, device, iters=100, warm=20):
    model.eval()
    x = torch.randn(1, 3, a.img_size, a.img_size, device=device)
    with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=(device.type == "cuda")):
        for _ in range(warm):
            predict_probs(model, x)
        if device.type == "cuda":
            torch.cuda.synchronize()
        t = time.time()
        for _ in range(iters):
            predict_probs(model, x)
        if device.type == "cuda":
            torch.cuda.synchronize()
    return iters / (time.time() - t)


# --------------------------------------------------------------- commands ----
def cmd_audit(a):
    rows, hits, cols = load_manifest(a.manifest, a.roots, a.path_map)
    sp = split_rows(rows)
    print(f"[audit] columns {cols}; resolution {hits}")
    for s in sorted(sp):
        rs = sp[s]
        miss_i = sum(r["image"] is None for r in rs)
        miss_m = sum((not r["neg"]) and r["mask"] is None for r in rs)
        neg = sum(r["neg"] for r in rs)
        groups = len({r["group"] for r in rs if r["group"]})
        print(f"  {s:28s} n={len(rs):6d} neg={neg:6d} missing_img={miss_i:5d} missing_mask={miss_m:5d} groups={groups}")
    tr = {r["group"] for s in a.train_splits for r in sp.get(s, []) if r["group"]}
    va = {r["group"] for r in sp.get(a.val_split, []) if r["group"]}
    print(f"[audit] train/val group overlap: {len(tr & va)}")


def load_run(run_dir, device, overrides=None):
    """Rebuild a run exactly as trained (same img_size -> same pos_embed shape), load its weights, THEN apply
    overrides (manifest, test resolution, ...). ViTs use dynamic_img_size, so a different test size is fine."""
    cfg = json.load(open(os.path.join(run_dir, "config.json")))
    cfg.setdefault("gate", "mult")  # runs trained before --gate existed used multiplicative gating
    cfg.setdefault("gate_tau", 0.5)
    a = argparse.Namespace(**cfg)
    seed_all(int(cfg.get("seed", 42)))  # identical init for any non-saved (frozen, random) weights
    model = build_model(a).to(device)
    load_trainable(model, torch.load(os.path.join(run_dir, "best.pt"), map_location=device))
    model.eval()
    for k, v in (overrides or {}).items():
        setattr(a, k, v)
    return model, a


def cmd_eval(a):
    """Re-score an existing run on any manifest (e.g. Kvasir-Instrument, BUET, REAL-Colon negatives)."""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    over = dict(manifest=a.manifest, roots=a.roots, path_map=a.path_map, test_prefixes=a.test_prefixes,
                tta=a.tta, eval_bs=a.eval_bs, workers=a.workers)
    if a.img_size:  # test-time resolution override (Part 3: ETIS frames are 1225x966, polyps tiny at 352-392)
        over["img_size"] = a.img_size
    if a.gate:
        over["gate"] = a.gate
    if a.gate_tau >= 0:
        over["gate_tau"] = a.gate_tau
    model, ra = load_run(a.run, device, over)
    rows, hits, cols = load_manifest(a.manifest, a.roots, a.path_map)
    sp = split_rows(rows)
    names = [s for s in sorted(sp) if any(s.lower().startswith(p) for p in a.test_prefixes)]
    per = []
    for s in names:
        per += score_split(model, sp[s], ra, device, s)
    summ = summarise(per)
    tag = a.tag or os.path.splitext(os.path.basename(a.manifest))[0]
    json.dump(dict(manifest=a.manifest, resolve=hits, splits=summ),
              open(os.path.join(a.run, f"results_{tag}.json"), "w"), indent=1)
    import csv
    keys = sorted({k for r in per for k in r})
    with open(os.path.join(a.run, f"per_image_{tag}.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(per)
    print(json.dumps(summ, indent=1))


def cmd_summary(a):
    """Aggregate every run under --out: seed mean +- sd per split, and a paired bootstrap of each
    configuration against --ref on seed-averaged per-image scores (the E3 convention)."""
    import glob, re
    import pandas as pd
    recs, per_frames = [], {}
    for rj in sorted(glob.glob(os.path.join(a.out, "*", "results.json"))):
        rd = os.path.dirname(rj)
        d = json.load(open(rj)); cfg = json.load(open(os.path.join(rd, "config.json")))
        name = cfg.get("run_name") or os.path.basename(rd)
        conf = re.sub(r"_s\d+$", "", name)
        for split, s in d["splits"].items():
            recs.append(dict(config=conf, seed=cfg.get("seed"), split=split,
                             dice=s.get("gated_mDice"), fa=s.get("gated_fa_rate"),
                             raw_dice=s.get("raw_mDice"), raw_fa=s.get("raw_fa_rate"),
                             fps=d.get("fps"), trainable_M=d["meta"]["params_trainable"] / 1e6,
                             minutes=d["meta"]["minutes"]))
        pi = os.path.join(rd, "per_image.csv")
        if os.path.isfile(pi):
            per_frames.setdefault(conf, []).append(pd.read_csv(pi))
    if not recs:
        raise SystemExit(f"[summary] no results.json under {a.out}")
    df = pd.DataFrame(recs)
    g = df.groupby(["config", "split"])
    agg = g.agg(dice=("dice", "mean"), dice_sd=("dice", "std"), fa=("fa", "mean"), fa_sd=("fa", "std"),
                seeds=("seed", "nunique")).reset_index()
    lines = ["# ChakraSeg-v3 summary", "", f"runs under `{a.out}`: {df[['config','seed']].drop_duplicates().shape[0]}", ""]
    for metric, lab in (("dice", "gated mDice (mean ± sd over seeds)"), ("fa", "gated false-alarm rate")):
        sub = agg.dropna(subset=[metric])
        if sub.empty:
            continue
        tab = sub.pivot(index="config", columns="split", values=metric)
        sd = sub.pivot(index="config", columns="split", values=metric + "_sd")
        lines += [f"## {lab}", "", "| config | " + " | ".join(tab.columns) + " |",
                  "|---|" + "---|" * len(tab.columns)]
        for c in tab.index:
            cells = []
            for s in tab.columns:
                v, e = tab.loc[c, s], sd.loc[c, s]
                cells.append("" if pd.isna(v) else (f"{v:.4f}" + ("" if pd.isna(e) else f" ± {e:.4f}")))
            lines.append(f"| {c} | " + " | ".join(cells) + " |")
        lines.append("")
    meta = df.groupby("config").agg(fps=("fps", "mean"), trainable_M=("trainable_M", "mean"),
                                   minutes=("minutes", "mean")).reset_index()
    lines += ["## cost", "", "| config | trainable (M) | FPS (T4, bs1, fp16) | train minutes/run |", "|---|---|---|---|"]
    for _, r in meta.iterrows():
        fps = "" if pd.isna(r.fps) else f"{r.fps:.1f}"
        lines.append(f"| {r.config} | {r.trainable_M:.2f} | {fps} | {r.minutes:.0f} |")
    lines.append("")
    if a.ref and a.ref in per_frames:
        rng = np.random.default_rng(0)

        def seedavg(frames):
            x = pd.concat(frames)
            cols = [c for c in ("gated_dice", "gated_fa") if c in x.columns]
            return x.groupby(["split", "image"])[cols].mean().reset_index()

        R = seedavg(per_frames[a.ref])
        lines += [f"## paired bootstrap vs `{a.ref}` (seed-averaged per image; * = 95% CI excludes 0)", "",
                  "| config | split | metric | n | ref | config | Δ | 95% CI |", "|---|---|---|---|---|---|---|---|"]
        for conf, frames in sorted(per_frames.items()):
            if conf == a.ref:
                continue
            X = seedavg(frames)
            m = R.merge(X, on=["split", "image"], suffixes=("_r", "_x"))
            for split, sm in m.groupby("split"):
                for met in ("gated_dice", "gated_fa"):
                    if f"{met}_r" not in sm or sm[f"{met}_r"].isna().all():
                        continue
                    ok = sm[[f"{met}_r", f"{met}_x"]].dropna()
                    if ok.empty:
                        continue
                    d = (ok[f"{met}_x"] - ok[f"{met}_r"]).values
                    bs = [rng.choice(d, len(d)).mean() for _ in range(a.boot)]
                    lo, hi = np.percentile(bs, [2.5, 97.5])
                    star = " *" if (lo > 0 or hi < 0) else ""
                    lines.append(f"| {conf} | {split} | {met.split('_')[1]} | {len(d)} | {ok[f'{met}_r'].mean():.4f} | "
                                 f"{ok[f'{met}_x'].mean():.4f} | {d.mean():+.4f}{star} | [{lo:+.4f}, {hi:+.4f}] |")
        lines.append("")
    md = "\n".join(lines)
    open(os.path.join(a.out, "summary.md"), "w").write(md)
    df.to_csv(os.path.join(a.out, "summary_long.csv"), index=False)
    print(md)


def cmd_ops(a):
    """Operating-point sweep from a run's per_image CSV (no GPU needed).
    Decision per frame: fire = (presence > t_p) and (raw_peak > t_m) and (raw_area > FA_AREA).
    tau is chosen on --tune-splits (polyp-free frames NOT used for reporting) to meet each false-alarm
    budget, then detection on polyp test splits and FA on the other negative splits are reported."""
    import pandas as pd
    df = pd.read_csv(a.per_image)
    has_p = "presence" in df and df["presence"].notna().any()
    tps = np.unique(np.concatenate([[0.0], np.quantile(df["presence"].dropna(), np.linspace(0, 1, 201))])) if has_p else [0.0]
    tms = [0.5, 0.7, 0.9, 0.95, 0.99, 0.995]
    neg = df[df.neg.astype(str).str.lower().isin(["true", "1"])]
    pos = df[~df.index.isin(neg.index)]
    tune = neg[neg.split.isin(a.tune_splits)] if a.tune_splits else neg
    other = neg[~neg.index.isin(tune.index)]

    def fire(d, tp, tm):
        f = (d["raw_peak"] > tm) & (d["raw_area"] > FA_AREA)
        if has_p:
            f &= d["presence"] > tp
        return f

    print(f"[ops] tune on {sorted(tune.split.unique())} (n={len(tune)}); report on polyp splits "
          f"{sorted(pos.split.unique())} and other negatives {sorted(other.split.unique())}")
    for budget in a.budgets:
        best = None
        for tm in tms:
            for tp in tps:
                fa = fire(tune, tp, tm).mean() if len(tune) else 0.0
                if fa <= budget:
                    det = (fire(pos, tp, tm) & (pos["raw_hit"] > 0)).mean() if len(pos) else 0.0
                    if best is None or det > best[0]:
                        best = (det, tp, tm, fa)
                    break  # tps ascending: first feasible tp is the most permissive for this tm
        if best is None:
            print(f"  budget {budget:.3f}: infeasible"); continue
        det, tp, tm, fa = best
        line = f"  budget {budget:.3f}: t_presence={tp:.4f} t_mask={tm:.3f} tune_FA={fa:.4f} detection={det:.4f}"
        for s_, d in pos.groupby("split"):
            line += f" | {s_} det={(fire(d, tp, tm) & (d['raw_hit'] > 0)).mean():.3f}"
        for s_, d in other.groupby("split"):
            line += f" | {s_} FA={fire(d, tp, tm).mean():.4f}"
        print(line)


def cmd_pseudo(a):
    """Noisy-student pseudo-labelling (Part 4): run a trained teacher over unlabeled frames, keep only
    confident positives (presence high, mask crisp) and confident negatives (presence low, nothing marked),
    write masks + a manifest that can be merged with the labelled one (split 'train_pseudo')."""
    import csv
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    over = dict(eval_bs=a.eval_bs, workers=a.workers, tta=a.tta)
    if a.img_size:
        over["img_size"] = a.img_size
    model, ra = load_run(a.run, device, over)
    rows, hits, _ = load_manifest(a.manifest, a.roots, a.path_map)
    rows = [r for r in rows if r["image"] is not None]
    for r in rows:  # unlabeled -> score as polyp-free placeholder rows (mask ignored)
        r["neg"], r["mask"] = True, None
    # seeded shuffle: with --max-pos/--max-neg the kept set is a random sample across ALL sources (pool.csv is
    # ordered by source), and scoring stops as soon as both caps are full
    random.Random(a.seed).shuffle(rows)
    os.makedirs(os.path.join(a.out_dir, "masks"), exist_ok=True)
    ds = EvalDataset(rows, ra.img_size)
    dl = torch.utils.data.DataLoader(ds, batch_size=ra.eval_bs, shuffle=False, num_workers=ra.workers, collate_fn=eval_collate)
    keep, stats = [], defaultdict(int)
    model.eval()
    for x, ms, idx in dl:
        if a.max_pos and a.max_neg and stats["pos"] >= a.max_pos and stats["neg"] >= a.max_neg:
            stats["stopped_early"] = 1
            break
        x = x.to(device)
        with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=(device.type == "cuda")):
            _, pr, pp = predict_probs(model, x, use_presence=False, tta=bool(a.tta))
        for b in range(x.shape[0]):
            r = ds.rows[idx[b]]
            H, W = ms[b].shape
            p = F.interpolate(pr[b:b + 1].float(), size=(H, W), mode="bilinear", align_corners=False)[0, 0].cpu().numpy()
            pres = float(pp[b]) if pp is not None else float(p.max())
            area = float((p > 0.5).mean())
            fg = p > 0.5
            unc = float(((p > 0.3) & (p < 0.7)).sum()) / max(1.0, float(fg.sum()))
            stats["seen"] += 1
            if pres >= a.pos_tau and float(p.max()) >= a.peak_tau and area >= FA_AREA and unc <= a.uncertain_max:
                if a.max_pos and stats["pos"] >= a.max_pos:
                    continue
                mp = os.path.join(a.out_dir, "masks", f"pl_{stats['seen']:07d}.png")
                cv2.imwrite(mp, (fg * 255).astype(np.uint8))
                keep.append(dict(image=os.path.abspath(r["image"]), mask=os.path.abspath(mp), split=a.split_name,
                                 group=f"pseudo_{r.get('group') or stats['seen']}", presence=pres, area=area, uncertain=unc))
                stats["pos"] += 1
            elif pres <= a.neg_tau and area <= FA_AREA * 0.5:
                if a.max_neg and stats["neg"] >= a.max_neg:
                    continue
                keep.append(dict(image=os.path.abspath(r["image"]), mask="", split=a.split_name,
                                 group=f"pseudo_{r.get('group') or stats['seen']}", presence=pres, area=area, uncertain=0.0))
                stats["neg"] += 1
            else:
                stats["skipped_uncertain"] += 1
    out_csv = os.path.join(a.out_dir, "pseudo.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image", "mask", "split", "group", "presence", "area", "uncertain"])
        w.writeheader(); w.writerows(keep)
    if a.merge_with:  # labelled manifest + pseudo rows -> one manifest (train with --train-splits train <split_name>)
        import pandas as pd
        lab = pd.read_csv(a.merge_with, dtype=str, keep_default_na=False,
                          sep="\t" if a.merge_with.endswith(".tsv") else ",")
        # absolute paths for the labelled rows so the merged file works from any directory
        res = PathResolver(a.roots, a.path_map, os.path.dirname(os.path.abspath(a.merge_with)))
        ic, mc = _pick(lab.columns, IMG_COLS), _pick(lab.columns, MASK_COLS)
        absr = lambda p: os.path.abspath(res(p)) if res(p) else p
        lab[ic] = [absr(p) for p in lab[ic]]
        if mc:
            lab[mc] = [absr(p) if _norm(p) else "" for p in lab[mc]]
        pl = pd.DataFrame(keep)[["image", "mask", "split", "group"]] if keep else pd.DataFrame(columns=["image", "mask", "split", "group"])
        sc, gc = _pick(lab.columns, SPLIT_COLS), _pick(lab.columns, GROUP_COLS)   # reuse the labelled column names
        pl = pl.rename(columns={"image": ic, "mask": mc or "mask", "split": sc or "split", "group": gc or "group"})
        merged = pd.concat([lab, pl], ignore_index=True).fillna("")
        merged.to_csv(os.path.join(a.out_dir, "merged_manifest.csv"), index=False)
    json.dump(dict(stats), open(os.path.join(a.out_dir, "pseudo_stats.json"), "w"), indent=1)
    print(f"[pseudo] {dict(stats)} -> {out_csv}")


def cmd_fps(a):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = build_model(a).to(device)
    tot, trn = count_params(model)
    print(json.dumps(dict(arch=a.arch, backbone=a.backbone, img=a.img_size, params_M=tot / 1e6,
                          fps=benchmark_fps(model, a, device)), indent=1))


def cmd_compare(a):
    import pandas as pd
    A, B = pd.read_csv(a.a), pd.read_csv(a.b)
    col = f"{a.tag}_dice"
    rng = np.random.default_rng(0)
    print(f"{'split':28s} {'n':>5s} {'A':>7s} {'B':>7s} {'B-A':>7s}  95% paired bootstrap CI")
    for s in sorted(set(A.split) & set(B.split)):
        a_ = A[A.split == s].set_index("image"); b_ = B[B.split == s].set_index("image")
        idx = a_.index.intersection(b_.index)
        if col in a_ and a_.loc[idx, col].notna().any():
            x, y = a_.loc[idx, col].values.astype(float), b_.loc[idx, col].values.astype(float)
        else:
            c2 = f"{a.tag}_fa"
            x, y = a_.loc[idx, c2].values.astype(float), b_.loc[idx, c2].values.astype(float)
        ok = ~(np.isnan(x) | np.isnan(y)); x, y = x[ok], y[ok]
        if len(x) == 0:
            continue
        d = y - x
        bs = [rng.choice(d, len(d)).mean() for _ in range(a.boot)]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print(f"{s:28s} {len(x):5d} {x.mean():7.4f} {y.mean():7.4f} {d.mean():+7.4f}  [{lo:+.4f}, {hi:+.4f}]"
              + ("  *" if lo > 0 or hi < 0 else ""))


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(q):
        q.add_argument("--manifest", default="")
        q.add_argument("--roots", nargs="*", default=["/kaggle/input", "."])
        q.add_argument("--path-map", nargs="*", default=[], dest="path_map",
                       help="prefix rewrites, e.g. 'M:/chakramodelpro/leakbench/=/kaggle/input/chakra-leakbench-v1/'")
        q.add_argument("--train-splits", nargs="*", default=["train"], dest="train_splits")
        q.add_argument("--val-split", default="val", dest="val_split")
        q.add_argument("--test-prefixes", nargs="*", default=["test", "neg"], dest="test_prefixes")
        q.add_argument("--arch", default="v3vit", choices=["v3vit", "v3conv", "sam2unet"])
        q.add_argument("--backbone", default="vit_large_patch14_dinov2.lvd142m")
        q.add_argument("--pretrained", type=int, default=1)
        q.add_argument("--img-size", type=int, default=392, dest="img_size")
        q.add_argument("--dim", type=int, default=256)
        q.add_argument("--freeze", default="lora", choices=["full", "lora", "frozen"])
        q.add_argument("--lora-r", type=int, default=16, dest="lora_r")
        q.add_argument("--lora-alpha", type=int, default=32, dest="lora_alpha")
        q.add_argument("--cnn-branch", default="resnet34.a1_in1k", dest="cnn_branch",
                       help="timm name or 'none'")
        q.add_argument("--xattn-fuse", type=int, default=1, dest="xattn_fuse")
        q.add_argument("--presence", type=int, default=1)
        q.add_argument("--gate", default="hard", choices=["hard", "mult"])
        q.add_argument("--gate-tau", type=float, default=0.5, dest="gate_tau")
        q.add_argument("--aux", type=int, default=1)
        q.add_argument("--grad-ckpt", type=int, default=1, dest="grad_ckpt")
        q.add_argument("--drop-path", type=float, default=0.0, dest="drop_path", help="ViT stochastic depth")
        q.add_argument("--backbone-ckpt", default="", dest="backbone_ckpt",
                       help="in-domain ViT weights from ssl_continue.py (loaded before LoRA / freezing)")
        q.add_argument("--sam2unet-repo", default="SAM2-UNet", dest="sam2unet_repo")
        q.add_argument("--hiera-ckpt", default="sam2_hiera_large.pt", dest="hiera_ckpt")
        q.add_argument("--amp", type=int, default=1)
        q.add_argument("--tta", type=int, default=0)
        q.add_argument("--eval-bs", type=int, default=8, dest="eval_bs")
        q.add_argument("--workers", type=int, default=2)

    t = sub.add_parser("train"); common(t)
    t.add_argument("--seed", type=int, default=42)
    t.add_argument("--epochs", type=int, default=40)
    t.add_argument("--bs", type=int, default=8)
    t.add_argument("--accum", type=int, default=2)
    t.add_argument("--lr", type=float, default=2e-4, help="head / LoRA / adapter LR")
    t.add_argument("--lr-cnn", type=float, default=1e-4, dest="lr_cnn")
    t.add_argument("--lr-backbone", type=float, default=1e-4, dest="lr_backbone", help="v3conv deepest stage")
    t.add_argument("--llrd", type=float, default=0.8, help="layer/stage-wise LR decay")
    t.add_argument("--wd", type=float, default=1e-4)
    t.add_argument("--warmup-epochs", type=int, default=2, dest="warmup_epochs")
    t.add_argument("--clip", type=float, default=1.0)
    t.add_argument("--ms-rates", default="0.75,1,1.25", dest="ms_rates")
    t.add_argument("--deg-aug", type=float, default=0.0, dest="deg_aug",
                   help="probability of blur / motion / down-up / JPEG degradation (Part 3)")
    t.add_argument("--lab-aug", type=float, default=0.0, dest="lab_aug",
                   help="probability of Lab colour-distribution jitter (Part 3)")
    t.add_argument("--aux-w", type=float, default=0.5, dest="aux_w")
    t.add_argument("--presence-w", type=float, default=0.5, dest="presence_w")
    t.add_argument("--mask-loss-on-neg", type=int, default=1, dest="mask_loss_on_neg")
    t.add_argument("--eval-every", type=int, default=2, dest="eval_every")
    t.add_argument("--max-iters", type=int, default=0, dest="max_iters", help="debug: iters per epoch")
    t.add_argument("--max-epochs-time", type=float, default=0, dest="max_epochs_time", help="hours")
    t.add_argument("--save-full", type=int, default=0, dest="save_full")
    t.add_argument("--run-name", default="", dest="run_name")
    t.add_argument("--out", default="runs_v3")
    t.add_argument("--overwrite", type=int, default=0)

    au = sub.add_parser("audit"); common(au)
    f = sub.add_parser("fps"); common(f)
    ps = sub.add_parser("pseudo")
    ps.add_argument("--run", required=True)
    ps.add_argument("--manifest", required=True, help="unlabeled pool (e.g. ssl_pool/pool.csv)")
    ps.add_argument("--roots", nargs="*", default=["/kaggle/input", "."])
    ps.add_argument("--path-map", nargs="*", default=[], dest="path_map")
    ps.add_argument("--out-dir", default="pseudo", dest="out_dir")
    ps.add_argument("--pos-tau", type=float, default=0.9, dest="pos_tau", help="min presence for a pseudo-positive")
    ps.add_argument("--peak-tau", type=float, default=0.9, dest="peak_tau", help="min mask peak for a pseudo-positive")
    ps.add_argument("--neg-tau", type=float, default=0.05, dest="neg_tau", help="max presence for a pseudo-negative")
    ps.add_argument("--uncertain-max", type=float, default=0.3, dest="uncertain_max",
                    help="max (pixels with 0.3<p<0.7) / (pixels with p>0.5) for a pseudo-positive")
    ps.add_argument("--max-pos", type=int, default=0, dest="max_pos")
    ps.add_argument("--max-neg", type=int, default=0, dest="max_neg")
    ps.add_argument("--split-name", default="train_pseudo", dest="split_name")
    ps.add_argument("--merge-with", default="", dest="merge_with", help="labelled manifest to merge the pseudo rows into")
    ps.add_argument("--img-size", type=int, default=0, dest="img_size")
    ps.add_argument("--tta", type=int, default=1)
    ps.add_argument("--eval-bs", type=int, default=8, dest="eval_bs")
    ps.add_argument("--workers", type=int, default=2)
    ps.add_argument("--seed", type=int, default=0, help="shuffle order of the pool (which frames fill the caps)")
    op = sub.add_parser("ops")
    op.add_argument("--per-image", required=True, dest="per_image")
    op.add_argument("--tune-splits", nargs="*", default=[], dest="tune_splits",
                    help="negative splits used ONLY to pick thresholds (e.g. a held-out PolypGen set)")
    op.add_argument("--budgets", nargs="*", type=float, default=[0.01, 0.02, 0.05, 0.10])
    sm = sub.add_parser("summary")
    sm.add_argument("--out", default="runs_v3")
    sm.add_argument("--ref", default="", help="configuration name to compare everything against")
    sm.add_argument("--boot", type=int, default=5000)
    ev = sub.add_parser("eval")
    ev.add_argument("--run", required=True, help="run directory containing config.json and best.pt")
    ev.add_argument("--manifest", required=True)
    ev.add_argument("--roots", nargs="*", default=["/kaggle/input", "."])
    ev.add_argument("--path-map", nargs="*", default=[], dest="path_map")
    ev.add_argument("--test-prefixes", nargs="*", default=["test", "neg"], dest="test_prefixes")
    ev.add_argument("--tta", type=int, default=0)
    ev.add_argument("--eval-bs", type=int, default=8, dest="eval_bs")
    ev.add_argument("--workers", type=int, default=2)
    ev.add_argument("--tag", default="")
    ev.add_argument("--img-size", type=int, default=0, dest="img_size",
                    help="override the run's input size at test time (ViT: multiple of the patch size)")
    ev.add_argument("--gate", default="", choices=["", "hard", "mult"], help="override the presence-gate mode")
    ev.add_argument("--gate-tau", type=float, default=-1.0, dest="gate_tau", help="override the presence threshold")
    c = sub.add_parser("compare")
    c.add_argument("--a", required=True); c.add_argument("--b", required=True)
    c.add_argument("--tag", default="gated"); c.add_argument("--boot", type=int, default=5000)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    if a.cmd == "train":
        cmd_train(a)
    elif a.cmd == "audit":
        cmd_audit(a)
    elif a.cmd == "fps":
        cmd_fps(a)
    elif a.cmd == "eval":
        cmd_eval(a)
    elif a.cmd == "summary":
        cmd_summary(a)
    elif a.cmd == "ops":
        cmd_ops(a)
    elif a.cmd == "pseudo":
        cmd_pseudo(a)
    elif a.cmd == "compare":
        cmd_compare(a)


if __name__ == "__main__":
    main()
