#!/usr/bin/env python3
"""
ssl_continue.py — ExPLoRA-style continued self-supervised pretraining of a DINOv2 / DINOv3 ViT on
unlabeled colonoscopy frames (Part 4), sized for Kaggle T4s.

ExPLoRA (Khanna et al., ICML 2025): keep the pretrained ViT, UNFREEZE the last 1-2 blocks, put LoRA on
all other blocks, and continue the original self-supervised objective on the new domain.
Here the objective is DINO (self-distillation with multi-crop, centring and an EMA teacher) on the
CLS token; the public DINOv2 checkpoints ship without their projection heads, so a fresh DINO head is
initialised and trained alone for --head-warmup iterations before the backbone parts are released.

Endoscopy-specific: the calibrated acquisition-degradation augmentation from chakraseg_v3 (Part 3:
blur is the largest test-set shift) is applied to crops with probability --deg-p, so the representation
is pushed to be invariant to exactly the shift we measured.

Outputs in --out: backbone_merged_<iter>.pth (the EMA teacher by default, LoRA merged into the weights;
loads into a plain timm model and into chakraseg_v3 via --backbone-ckpt), log.json. The log prints
teacher_entropy (per image) and teacher_batch_entropy (of the batch-mean distribution) as collapse checks.

Example (T4):
  python ssl_continue.py --pool ssl_pool/pool.csv --backbone vit_large_patch14_dinov2.lvd142m \
      --unfreeze 2 --lora-r 32 --iters 20000 --bs 32 --accum 2 --out ssl_vitl --save-every 2500
"""
import argparse, copy, json, math, os, random, sys, time

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chakraseg_v3 as C  # noqa: E402  (LoRALinear, degrade, manifest loader)

MEAN, STD = C.MEAN, C.STD


# ------------------------------------------------------------------ crops ----
def rrc(im, size, scale):
    H, W = im.shape[:2]
    for _ in range(10):
        area = H * W * random.uniform(*scale)
        ar = math.exp(random.uniform(math.log(3 / 4), math.log(4 / 3)))
        w, h = int(round(math.sqrt(area * ar))), int(round(math.sqrt(area / ar)))
        if 0 < w <= W and 0 < h <= H:
            x, y = random.randint(0, W - w), random.randint(0, H - h)
            return cv2.resize(im[y:y + h, x:x + w], (size, size), interpolation=cv2.INTER_LINEAR)
    s = min(H, W)
    return cv2.resize(im[(H - s) // 2:(H - s) // 2 + s, (W - s) // 2:(W - s) // 2 + s], (size, size))


def color_aug(im, p_gray=0.1):
    im = im.astype(np.float32)
    if random.random() < 0.8:
        im = im * random.uniform(0.6, 1.4)
        m = im.mean()
        im = (im - m) * random.uniform(0.6, 1.4) + m
        g = im.mean(axis=2, keepdims=True)
        im = g + (im - g) * random.uniform(0.8, 1.2)
        hsv = cv2.cvtColor(np.clip(im, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.int16)
        hsv[..., 0] = (hsv[..., 0] + random.randint(-9, 9)) % 180
        im = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
    if random.random() < p_gray:
        im = np.repeat(im.mean(axis=2, keepdims=True), 3, axis=2)
    return np.clip(im, 0, 255).astype(np.uint8)


def view(im, size, scale, blur_p, sol_p, deg_p):
    v = rrc(im, size, scale)
    if random.random() < 0.5:
        v = v[:, ::-1]
    v = color_aug(np.ascontiguousarray(v))
    if random.random() < deg_p:
        v = C.degrade(v)
    elif random.random() < blur_p:
        v = cv2.GaussianBlur(v, (0, 0), random.uniform(0.1, 2.0))
    if random.random() < sol_p:
        v = np.where(v < 128, v, 255 - v).astype(np.uint8)
    v = (v.astype(np.float32) / 255.0 - MEAN) / STD
    return torch.from_numpy(np.ascontiguousarray(v.transpose(2, 0, 1)))


class MultiCrop(torch.utils.data.Dataset):
    def __init__(self, paths, gsize, lsize, n_local, deg_p):
        self.paths, self.g, self.l, self.n, self.deg = paths, gsize, lsize, n_local, deg_p

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        im = cv2.imread(self.paths[i], cv2.IMREAD_COLOR)
        if im is None:
            im = np.zeros((self.g, self.g, 3), np.uint8)
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        crops = [view(im, self.g, (0.32, 1.0), 1.0, 0.0, self.deg),
                 view(im, self.g, (0.32, 1.0), 0.1, 0.2, self.deg)]
        crops += [view(im, self.l, (0.05, 0.32), 0.5, 0.0, self.deg) for _ in range(self.n)]
        return crops


def collate(batch):
    return [torch.stack([b[k] for b in batch]) for k in range(len(batch[0]))]


# ------------------------------------------------------------------ model ----
class DINOHead(nn.Module):
    def __init__(self, din, out_dim=8192, hidden=2048, bottleneck=256):
        super().__init__()
        self.mlp = nn.Sequential(nn.Linear(din, hidden), nn.GELU(), nn.Linear(hidden, hidden), nn.GELU(),
                                 nn.Linear(hidden, bottleneck))
        self.last = nn.utils.parametrizations.weight_norm(nn.Linear(bottleneck, out_dim, bias=False))
        self.last.parametrizations.weight.original0.data.fill_(1.0)
        self.last.parametrizations.weight.original0.requires_grad = False

    def forward(self, x):
        x = F.normalize(self.mlp(x), dim=-1)
        return self.last(x)


class Student(nn.Module):
    def __init__(self, a):
        super().__init__()
        import timm
        self.vit = timm.create_model(a.backbone, pretrained=bool(a.pretrained), num_classes=0,
                                     dynamic_img_size=True, img_size=a.gsize, drop_path_rate=a.drop_path)
        for p in self.vit.parameters():
            p.requires_grad = False
        L = len(self.vit.blocks)
        self.free = list(range(L - a.unfreeze, L))
        lora_blocks = [i for i in range(L) if i not in self.free]
        for i in lora_blocks:
            blk = self.vit.blocks[i]
            blk.attn.qkv = C.LoRALinear(blk.attn.qkv, a.lora_r, a.lora_alpha)
        self.lora_blocks = lora_blocks
        if a.grad_ckpt:
            self.vit.set_grad_checkpointing(True)
        self.head = DINOHead(self.vit.embed_dim, a.out_dim)

    def backbone_params(self):
        ps = []
        for i in self.free:
            ps += list(self.vit.blocks[i].parameters())
        ps += list(self.vit.norm.parameters())
        for i in self.lora_blocks:
            q = self.vit.blocks[i].attn.qkv
            ps += [q.A, q.B]
        return ps

    def set_backbone_trainable(self, flag):
        for p in self.backbone_params():
            p.requires_grad = flag

    def forward(self, crops):
        # group crops of equal size so each resolution is one forward pass
        out, i = [], 0
        while i < len(crops):
            j = i
            while j < len(crops) and crops[j].shape[-1] == crops[i].shape[-1]:
                j += 1
            x = torch.cat(crops[i:j])
            f = self.vit.forward_features(x)
            cls = f[:, 0] if f.ndim == 3 else f
            out.append(self.head(cls).chunk(j - i))
            i = j
        return [t for grp in out for t in grp]


def dino_loss(s_out, t_out, center, s_temp, t_temp, n_global):
    t = [F.softmax((o - center) / t_temp, dim=-1).detach() for o in t_out]
    loss, n = 0.0, 0
    for ti, tq in enumerate(t):
        for si, so in enumerate(s_out):
            if si == ti:
                continue
            loss = loss + torch.sum(-tq * F.log_softmax(so / s_temp, dim=-1), dim=-1).mean()
            n += 1
    return loss / n


def export_merged(model, a, path):
    """LoRA merged into plain timm weights of `model` (the EMA teacher by default) -> loadable with strict=True into timm.create_model(a.backbone)."""
    import timm
    clean = timm.create_model(a.backbone, pretrained=False, num_classes=0, dynamic_img_size=True, img_size=a.gsize)
    sd = {}
    for k, v in model.vit.state_dict().items():
        if k.endswith(".A") or k.endswith(".B"):
            continue
        sd[k.replace(".qkv.base.", ".qkv.")] = v.detach().float().cpu().clone()
    for i in model.lora_blocks:
        q = model.vit.blocks[i].attn.qkv
        sd[f"blocks.{i}.attn.qkv.weight"] = (q.base.weight + q.scale * (q.B @ q.A)).detach().float().cpu()
    # pos_embed stays frozen during SSL but was resampled to the SSL crop grid; drop it so the downstream model
    # keeps its own pretrained pos_embed at its own resolution (exact, since it never changed)
    sd.pop("pos_embed", None)
    res = clean.load_state_dict(sd, strict=False)
    assert not res.unexpected_keys, res.unexpected_keys
    assert all(k == "pos_embed" for k in res.missing_keys), res.missing_keys
    torch.save(sd, path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pool", required=True, help="pool.csv from build_ssl_pool.py (or any manifest)")
    ap.add_argument("--roots", nargs="*", default=[".", "/kaggle/input"])
    ap.add_argument("--backbone", default="vit_large_patch14_dinov2.lvd142m")
    ap.add_argument("--pretrained", type=int, default=1)
    ap.add_argument("--unfreeze", type=int, default=2, help="last N blocks fully trainable (ExPLoRA: 1-2)")
    ap.add_argument("--lora-r", type=int, default=32, dest="lora_r")
    ap.add_argument("--lora-alpha", type=int, default=64, dest="lora_alpha")
    ap.add_argument("--out-dim", type=int, default=8192, dest="out_dim")
    ap.add_argument("--gsize", type=int, default=224)
    ap.add_argument("--lsize", type=int, default=98)
    ap.add_argument("--n-local", type=int, default=6, dest="n_local")
    ap.add_argument("--deg-p", type=float, default=0.3, dest="deg_p")
    ap.add_argument("--iters", type=int, default=20000)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--accum", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lr-head", type=float, default=5e-4, dest="lr_head")
    ap.add_argument("--wd", type=float, default=0.05)
    ap.add_argument("--head-warmup", type=int, default=1000, dest="head_warmup")
    ap.add_argument("--warmup", type=int, default=1000)
    ap.add_argument("--s-temp", type=float, default=0.1, dest="s_temp")
    ap.add_argument("--t-temp", type=float, default=0.04, dest="t_temp")
    ap.add_argument("--momentum", type=float, default=0.994)
    ap.add_argument("--center-m", type=float, default=0.9, dest="center_m")
    ap.add_argument("--clip", type=float, default=3.0)
    ap.add_argument("--drop-path", type=float, default=0.1, dest="drop_path")
    ap.add_argument("--grad-ckpt", type=int, default=1, dest="grad_ckpt")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--save-every", type=int, default=2500, dest="save_every")
    ap.add_argument("--export", default="teacher", choices=["teacher", "student"],
                    help="weights to export; DINO evaluates the EMA teacher, which it reports as the better network")
    ap.add_argument("--max-hours", type=float, default=11.0, dest="max_hours")
    ap.add_argument("--out", default="ssl_out")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    os.makedirs(a.out, exist_ok=True)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    rows, hits, _ = C.load_manifest(a.pool, a.roots)
    paths = [r["image"] for r in rows if r["image"]]
    print(f"[ssl] {len(paths)} frames (resolution {hits})")
    ds = MultiCrop(paths, a.gsize, a.lsize, a.n_local, a.deg_p)
    dl = torch.utils.data.DataLoader(ds, batch_size=a.bs, shuffle=True, num_workers=a.workers, drop_last=True,
                                     collate_fn=collate, pin_memory=(dev.type == "cuda"), persistent_workers=a.workers > 0)
    student = Student(a).to(dev)
    teacher = copy.deepcopy(student).to(dev)
    for p in teacher.parameters():
        p.requires_grad = False
    student.set_backbone_trainable(False)  # head warm-up first
    n_tr = sum(p.numel() for p in student.backbone_params())
    print(f"[ssl] backbone trainable (after warm-up) {n_tr / 1e6:.2f}M of {sum(p.numel() for p in student.vit.parameters()) / 1e6:.1f}M; "
          f"unfrozen blocks {student.free}; LoRA r={a.lora_r} on {len(student.lora_blocks)} blocks")
    opt = torch.optim.AdamW([dict(params=student.backbone_params(), lr=a.lr, base=a.lr),
                             dict(params=[p for p in student.head.parameters() if p.requires_grad], lr=a.lr_head, base=a.lr_head)],
                            weight_decay=a.wd)
    scaler = torch.amp.GradScaler("cuda", enabled=(dev.type == "cuda"))
    center = torch.zeros(1, a.out_dim, device=dev)
    it, t0, log = 0, time.time(), []
    student.train(); teacher.eval()  # as in DINO/DINOv2 the teacher has no stochastic depth; eval() disables it
    while it < a.iters:
        for crops in dl:
            crops = [c.to(dev, non_blocking=True) for c in crops]
            if it == a.head_warmup:
                student.set_backbone_trainable(True)
            for g in opt.param_groups:
                g["lr"] = g["base"] * (min(1.0, (it + 1) / a.warmup) * (0.5 * (1 + math.cos(math.pi * it / a.iters))))
            with torch.autocast(device_type=dev.type, dtype=torch.float16, enabled=(dev.type == "cuda")):
                with torch.no_grad():
                    t_out = teacher(crops[:2])
                s_out = student(crops)
            t_out, s_out = [t.float() for t in t_out], [s.float() for s in s_out]
            loss = dino_loss(s_out, t_out, center, a.s_temp, a.t_temp, 2) / a.accum
            scaler.scale(loss).backward()
            if (it + 1) % a.accum == 0:
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_([p for p in student.parameters() if p.requires_grad], a.clip)
                scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
                m = 1 - (1 - a.momentum) * (math.cos(math.pi * it / a.iters) + 1) / 2
                with torch.no_grad():
                    for ps, pt in zip(student.parameters(), teacher.parameters()):
                        if ps.requires_grad or it < 1:
                            pt.mul_(m).add_(ps.detach(), alpha=1 - m)
                    batch_center = torch.cat(t_out).mean(0, keepdim=True)
                    center.mul_(a.center_m).add_(batch_center, alpha=1 - a.center_m)
            if it % 50 == 0:
                with torch.no_grad():
                    p = F.softmax((t_out[0] - center) / a.t_temp, -1)
                    ent = float(-(p * torch.log(p + 1e-12)).sum(-1).mean())       # per image
                    pm = p.mean(0)
                    bent = float(-(pm * torch.log(pm + 1e-12)).sum())              # of the batch-mean distribution
                # collapse checks: teacher_entropy -> ln(out_dim) = uniform collapse;
                # teacher_batch_entropy -> teacher_entropy (both small) = every image on the same prototype
                rec = dict(it=it, loss=float(loss.detach()) * a.accum, teacher_entropy=ent, teacher_batch_entropy=bent,
                           lr=opt.param_groups[0]["lr"], hours=(time.time() - t0) / 3600)
                log.append(rec); print(json.dumps(rec), flush=True)
            it += 1
            if a.save_every and it % a.save_every == 0:
                export_merged(teacher if a.export == "teacher" else student, a, os.path.join(a.out, f"backbone_merged_{it:06d}.pth"))
            if it >= a.iters or (time.time() - t0) / 3600 > a.max_hours:
                break
        if (time.time() - t0) / 3600 > a.max_hours:
            print("[ssl] time budget reached"); break
    p = export_merged(teacher if a.export == "teacher" else student, a, os.path.join(a.out, f"backbone_merged_{it:06d}.pth"))
    json.dump(dict(args=vars(a), log=log), open(os.path.join(a.out, "log.json"), "w"), indent=1)
    print("[ssl] saved", p)


if __name__ == "__main__":
    main()
