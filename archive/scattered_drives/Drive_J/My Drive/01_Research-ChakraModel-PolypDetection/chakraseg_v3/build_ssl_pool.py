#!/usr/bin/env python3
"""
build_ssl_pool.py — build a clean, deduplicated, leakage-checked pool of unlabeled colonoscopy frames
for in-domain self-supervised pretraining (Part 4) or pseudo-labelling.

Sources (any mix): folders of images (e.g. HyperKvasir unlabeled / labeled lower-GI classes, LDPolypVideo
frames, REAL-Colon JPEG frames) and/or video files (LDPolypVideo polyp-free videos, REAL-Colon videos).

Steps
  1. collect  images recursively; decode videos at --fps frames per second
  2. filter   uninformative frames: mostly-black, over-exposed, extreme blur (keep ordinary blur on
              purpose: Part 3 found acquisition blur is the largest test-set shift)
  3. dedupe   64-bit difference hash; near-duplicates (Hamming <= --dup-radius) within the pool are
              collapsed, and anything within --test-radius of ANY test / held-out image is REMOVED
              (HyperKvasir contains Kvasir-SEG; pretraining on test frames is contamination too)
  4. write    <out>/frames/*.jpg (resized so the short side is --short), <out>/pool.csv
              (image, split='unlabeled', source), and <out>/pool_report.json with every count

Usage
  python build_ssl_pool.py --src hk_unlabeled=/data/hyperkvasir/unlabeled-images \
      --src ld_neg=/data/ldpolyp/videos_without_polyp --src realcolon=/data/realcolon/frames \
      --src ld_labeled=/data/ldpolyp/labeled_frames --src-cap ld_labeled=4000 \
      --test-manifest v2.csv --test-manifest r6_mixneg.csv --out ssl_pool --fps 1
"""
import argparse, glob, hashlib, json, os, random, sys
from collections import defaultdict

import cv2
import numpy as np

IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")
VID_EXT = (".mp4", ".avi", ".mov", ".mkv", ".mpg", ".wmv", ".m4v")


def dhash(img, k=8):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = cv2.resize(g, (k + 1, k), interpolation=cv2.INTER_AREA)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


class BandIndex:
    """Exact Hamming-radius search for 64-bit hashes via 8 bands of 8 bits (pigeonhole: radius <= 7)."""

    def __init__(self):
        self.bands = [defaultdict(list) for _ in range(8)]
        self.h = []

    def add(self, h):
        i = len(self.h); self.h.append(h)
        for b in range(8):
            self.bands[b][(h >> (8 * b)) & 0xFF].append(i)
        return i

    def near(self, h, r):
        seen = set()
        for b in range(8):
            for i in self.bands[b].get((h >> (8 * b)) & 0xFF, ()):
                if i not in seen:
                    seen.add(i)
                    if bin(self.h[i] ^ h).count("1") <= r:
                        return i
        return None


def informative(img, black_max=0.6, bright_max=0.5, sharp_min=5.0):
    """Reject frames that are mostly black (out of body / lens covered), over-exposed (flare, touching
    mucosa), or featureless. Returns (ok, reason)."""
    small = cv2.resize(img, (224, 224), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    v = hsv[..., 2]
    if (v < 20).mean() > black_max:
        return False, "black"
    if (v > 245).mean() > bright_max:
        return False, "overexposed"
    lap = cv2.Laplacian(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    if lap < sharp_min:
        return False, "featureless"
    return True, "ok"


def iter_source(path, fps, shuffle_seed=None):
    """Yield (frame_id, bgr) from a folder of images and/or videos. With shuffle_seed the file order is
    shuffled, so a per-source cap takes a random sample instead of the first files in sorted order."""
    files = sorted(glob.glob(os.path.join(path, "**", "*"), recursive=True)) if os.path.isdir(path) else [path]
    if shuffle_seed is not None:
        random.Random(shuffle_seed).shuffle(files)
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext in IMG_EXT:
            im = cv2.imread(f, cv2.IMREAD_COLOR)
            if im is not None:
                yield os.path.relpath(f, path) if os.path.isdir(path) else os.path.basename(f), im
        elif ext in VID_EXT:
            cap = cv2.VideoCapture(f)
            vfps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            step = max(1, int(round(vfps / fps)))
            i = 0
            while True:
                ok = cap.grab()
                if not ok:
                    break
                if i % step == 0:
                    ok, im = cap.retrieve()
                    if ok and im is not None:
                        yield f"{os.path.basename(f)}#f{i:07d}", im
                i += 1
            cap.release()


def test_hashes(manifests, roots, path_map=()):
    """dHash every image listed in the given manifests (all splits except train) -> index.
    Returns (index, n_hashed, n_unresolved): an unresolved test image cannot be excluded from the pool."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import chakraseg_v3 as C
    idx, n, miss = BandIndex(), 0, 0
    for m in manifests:
        rows, _, _ = C.load_manifest(m, roots, path_map)
        for r in rows:
            if r["split"].lower().startswith("train"):
                continue
            im = cv2.imread(r["image"], cv2.IMREAD_COLOR) if r["image"] is not None else None
            if im is None:
                miss += 1; continue
            idx.add(dhash(im)); n += 1
    return idx, n, miss


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", action="append", required=True, help="name=path (folder of images/videos)")
    ap.add_argument("--test-manifest", action="append", default=[], help="manifests whose non-train images must be excluded")
    ap.add_argument("--test-dir", action="append", default=[], help="extra folders of held-out images to exclude")
    ap.add_argument("--roots", nargs="*", default=["/kaggle/input", "."])
    ap.add_argument("--path-map", nargs="*", default=[], dest="path_map", help="prefix rewrites for the test manifests")
    ap.add_argument("--allow-missing-test", type=int, default=0, dest="allow_missing_test",
                    help="1 = continue even if some test/val images cannot be found (they could then leak into the pool)")
    ap.add_argument("--out", default="ssl_pool")
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--short", type=int, default=448, help="resize so the short side is this many px")
    ap.add_argument("--dup-radius", type=int, default=4)
    ap.add_argument("--test-radius", type=int, default=7, help="stricter (larger) radius against test images")
    ap.add_argument("--max-per-source", type=int, default=0)
    ap.add_argument("--src-cap", action="append", default=[], dest="src_cap",
                    help="name=N: cap for one source (random sample of its files; overrides --max-per-source)")
    ap.add_argument("--src-fps", action="append", default=[], dest="src_fps",
                    help="name=F: video sampling rate for one source (overrides --fps)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sharp-min", type=float, default=5.0,
                    help="featureless threshold (Laplacian var at 224 px); real test frames are all >= 68")
    a = ap.parse_args()
    random.seed(a.seed)
    os.makedirs(os.path.join(a.out, "frames"), exist_ok=True)
    tidx, n_test, n_miss = test_hashes(a.test_manifest, a.roots, a.path_map) if a.test_manifest else (BandIndex(), 0, 0)
    if n_miss and not a.allow_missing_test:
        raise SystemExit(f"[pool] {n_miss} test/val images in the manifests could not be read, so they cannot be "
                         f"excluded from the pool. Fix --roots/--path-map (or pass --allow-missing-test 1).")
    for d in a.test_dir:
        for f in glob.glob(os.path.join(d, "**", "*"), recursive=True):
            if f.lower().endswith(IMG_EXT):
                im = cv2.imread(f, cv2.IMREAD_COLOR)
                if im is not None:
                    tidx.add(dhash(im)); n_test += 1
    pool = BandIndex()
    report = dict(test_images_hashed=n_test, test_images_unresolved=n_miss, sources={})
    rows = []
    caps = {k: int(v) for k, v in (x.split("=", 1) for x in a.src_cap)}
    fpss = {k: float(v) for k, v in (x.split("=", 1) for x in a.src_fps)}
    for spec in a.src:
        name, path = spec.split("=", 1)
        cap = caps.get(name, a.max_per_source)
        c = defaultdict(int)
        for fid, im in iter_source(path, fpss.get(name, a.fps), shuffle_seed=a.seed if name in caps else None):
            c["seen"] += 1
            ok, why = informative(im, sharp_min=a.sharp_min)
            if not ok:
                c["drop_" + why] += 1; continue
            h = dhash(im)
            if tidx.near(h, a.test_radius) is not None:
                c["drop_test_collision"] += 1; continue
            if pool.near(h, a.dup_radius) is not None:
                c["drop_duplicate"] += 1; continue
            pool.add(h)
            H, W = im.shape[:2]; s = a.short / min(H, W)
            if s < 1:
                im = cv2.resize(im, (int(round(W * s)), int(round(H * s))), interpolation=cv2.INTER_AREA)
            fn = f"{name}_{hashlib.md5(fid.encode()).hexdigest()[:12]}.jpg"
            cv2.imwrite(os.path.join(a.out, "frames", fn), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
            rows.append(dict(image=f"frames/{fn}", mask="", split="unlabeled", source=name, origin=fid))
            c["kept"] += 1
            if cap and c["kept"] >= cap:
                break
        report["sources"][name] = dict(c)
        print(f"[pool] {name}: {dict(c)}", flush=True)
    import csv
    with open(os.path.join(a.out, "pool.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image", "mask", "split", "source", "origin"]); w.writeheader(); w.writerows(rows)
    report["kept_total"] = len(rows)
    json.dump(report, open(os.path.join(a.out, "pool_report.json"), "w"), indent=1)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
