"""
test_anatomy.py — per-image anatomy of polyp test sets (no model needed).

For every image+mask: polyp size (area fraction, equivalent diameter at 352 px and in ViT tokens),
multiplicity, border contact, centrality, sharpness (variance of Laplacian at 352 px), brightness,
black-border share, specular-highlight share, polyp-vs-surround colour contrast (CIE Lab ΔE) and
texture contrast. Writes anatomy.csv (one row per image) and anatomy_summary.md.

Usage: python test_anatomy.py --root TestDataset --out anatomy
       (expects <root>/<dataset>/images/* and <root>/<dataset>/masks/* with matching stems)
"""
import argparse, glob, json, math, os

import cv2
import numpy as np

S = 352  # PraNet-protocol network input


def stats(img_bgr, m):
    H, W = m.shape
    area = float(m.mean())
    n, lab, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    comps = [st[i, cv2.CC_STAT_AREA] for i in range(1, n) if st[i, cv2.CC_STAT_AREA] >= 0.001 * H * W]
    largest = max(comps) / (H * W) if comps else 0.0
    ys, xs = np.nonzero(m)
    if len(xs):
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        border = int(x0 <= 2 or y0 <= 2 or x1 >= W - 3 or y1 >= H - 3)
        cx, cy = xs.mean() / W - 0.5, ys.mean() / H - 0.5
        central = float(math.hypot(cx, cy) / math.hypot(0.5, 0.5))
    else:
        border, central = 0, float("nan")
    # everything below at the network resolution (352x352), like the model sees it
    im = cv2.resize(img_bgr, (S, S), interpolation=cv2.INTER_AREA)
    ms = cv2.resize(m.astype(np.uint8), (S, S), interpolation=cv2.INTER_NEAREST).astype(bool)
    d352 = math.sqrt(4 * ms.sum() / math.pi) if ms.any() else 0.0
    gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    v, s = hsv[..., 2].astype(np.float32), hsv[..., 1].astype(np.float32)
    valid = v > 15
    black = float(1 - valid.mean())
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    sharp = float(lap[valid].var()) if valid.any() else float("nan")
    spec = float(((v > 230) & (s < 40) & valid).sum() / max(1, valid.sum()))
    bright = float(v[valid].mean()) if valid.any() else float("nan")
    lab_im = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    k = max(3, int(round(0.06 * S)) | 1)
    ring = cv2.dilate(ms.astype(np.uint8), np.ones((k, k), np.uint8)).astype(bool) & ~ms & valid
    if ms.any() and ring.any():
        mi, mo = lab_im[ms].mean(0), lab_im[ring].mean(0)
        dE = float(np.linalg.norm(mi - mo))
        tex_in, tex_out = float(gray[ms].std()), float(gray[ring].std())
        sharp_in = float(lap[ms].var())
    else:
        dE = tex_in = tex_out = sharp_in = float("nan")
    return dict(H=H, W=W, area=area, n_polyps=len(comps), largest=largest, border=border,
                central=central, d352=d352, tok16_384=d352 * 384 / S / 16, tok14_392=d352 * 392 / S / 14,
                sharp=sharp, sharp_polyp=sharp_in, bright=bright, black=black, spec=spec,
                dE_lab=dE, tex_in=tex_in, tex_ring=tex_out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="TestDataset")
    ap.add_argument("--out", default="anatomy")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = []
    for ds in sorted(os.listdir(a.root)):
        idir, mdir = os.path.join(a.root, ds, "images"), os.path.join(a.root, ds, "masks")
        if not os.path.isdir(idir):
            continue
        masks = {os.path.splitext(os.path.basename(p))[0]: p for p in glob.glob(os.path.join(mdir, "*"))}
        for ip in sorted(glob.glob(os.path.join(idir, "*"))):
            stem = os.path.splitext(os.path.basename(ip))[0]
            if stem not in masks:
                continue
            img = cv2.imread(ip, cv2.IMREAD_COLOR)
            m = cv2.imread(masks[stem], cv2.IMREAD_GRAYSCALE)
            if img is None or m is None:
                continue
            if m.shape != img.shape[:2]:
                m = cv2.resize(m, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
            r = stats(img, m > 127)
            r.update(dataset=ds, image=stem)
            rows.append(r)
    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(a.out, "anatomy.csv"), index=False)
    print(len(df), "images")


if __name__ == "__main__":
    main()
