"""Motion-blur robustness sweep for ChakraGuard v1 (and any leakbench checkpoint).

Why this exists: the pitch will be asked what happens when the scope is moving. Our
published numbers are all on sharp still frames, so until this runs we have no answer.
This measures, at a fixed decision rule, how detection and false alarms move as the
frame gets blurrier -- separately for linear (scope motion) and defocus (out-of-focus) blur.

  python blur_robustness.py                      # 798 polyp test frames + 2000 sampled negatives
  python blur_robustness.py --full               # all 8,020 frames, ~5x slower
  python blur_robustness.py --kinds linear       # motion blur only

Kernel sizes are given at 352 px scale and rescaled to each frame's own height, so
"L=15" means the same perceived blur on a 384 px ETIS frame and a 1080 px PolypGen frame.

Output: local_tests/out/blur_<tag>.json + printed table. Writes example blurred frames
with --dump-examples so the deck can show what L=15 actually looks like.
"""
import argparse, csv, json, os, random, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LEAK = os.path.dirname(HERE)
ROOT = os.path.dirname(LEAK)
sys.path.insert(0, LEAK)

import cv2, torch, torch.nn.functional as F

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
POS = ["test_kvasir", "test_clinicdb", "test_colondb", "test_etis", "test_cvc300"]
NEG = ["neg_polypgen", "neg_hyperkvasir"]


def linear_kernel(L, angle):
    L = max(3, int(L) | 1)
    k = np.zeros((L, L), np.float32)
    k[L // 2, :] = 1.0
    M = cv2.getRotationMatrix2D((L / 2 - .5, L / 2 - .5), angle, 1.0)
    k = cv2.warpAffine(k, M, (L, L), flags=cv2.INTER_LINEAR)
    s = k.sum()
    return k / s if s > 0 else None


def disk_kernel(L):
    L = max(3, int(L) | 1)
    y, x = np.ogrid[:L, :L]
    c = L // 2
    k = (((x - c) ** 2 + (y - c) ** 2) <= (L / 2) ** 2).astype(np.float32)
    return k / k.sum()


def blur(img, kind, L352, rng):
    """L352 is the kernel length at 352 px; scale to this frame's height."""
    if L352 <= 0:
        return img
    h = img.shape[0]
    L = max(3, int(round(L352 * h / 352.0)) | 1)
    k = disk_kernel(L) if kind == "defocus" else linear_kernel(L, rng.uniform(0, 180))
    return cv2.filter2D(img, -1, k, borderType=cv2.BORDER_REFLECT101)


@torch.no_grad()
def prob_map(model, bgr, dev, size, half):
    h, w = bgr.shape[:2]
    x = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    x = cv2.resize(x, (size, size), interpolation=cv2.INTER_LINEAR)
    x = ((x.astype(np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)[None]
    t = torch.from_numpy(x).to(dev, dtype=torch.float16 if half else torch.float32)
    o = model(t)
    o = o["mask"] if isinstance(o, dict) else o
    p = torch.sigmoid(o.float())
    return F.interpolate(p, size=(h, w), mode="bilinear", align_corners=False)[0, 0].cpu().numpy()


def decide(p, tau, min_area):
    """Returns (alarm, kept_mask). Same rule as chakraguard/predict.py."""
    n, lab, st, _ = cv2.connectedComponentsWithStats((p > 0.5).astype(np.uint8), 8)
    keep = np.zeros(p.shape, bool)
    for c in range(1, n):
        m = lab == c
        if float(p[m].max()) >= tau and int(st[c, cv2.CC_STAT_AREA]) >= min_area:
            keep |= m
    return keep.any(), keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=os.path.join(LEAK, "chakraguard", "e4_negtrain__xattn__s43.pt"))
    ap.add_argument("--model", default="xattn")
    ap.add_argument("--manifest", default=os.path.join(LEAK, "manifests", "r2_e4_eval.csv"))
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--op", default=os.path.join(LEAK, "chakraguard", "operating_point.json"))
    ap.add_argument("--tau", type=float, default=None)
    ap.add_argument("--min-area", type=int, default=None)
    ap.add_argument("--size", type=int, default=352)
    ap.add_argument("--levels", nargs="+", type=int, default=[0, 5, 9, 15, 21, 31])
    ap.add_argument("--kinds", nargs="+", default=["linear", "defocus"])
    ap.add_argument("--neg-sample", type=int, default=2000)
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--fp32", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dump-examples", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    a = ap.parse_args()

    op = json.load(open(a.op))["rule"] if os.path.exists(a.op) else {"tau": 0.995, "area": 1}
    tau = a.tau if a.tau is not None else op["tau"]
    min_area = a.min_area if a.min_area is not None else op["area"]

    dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    half = (not a.fp32) and dev.startswith("cuda")
    sys.path.insert(0, HERE)
    from bench_latency import build
    model = build(a.model, a.size, a.ckpt if a.model == "xattn" else None)
    model = (model.half() if half else model.float()).eval().to(dev)

    rows = [r for r in csv.DictReader(open(a.manifest)) if r["split"] in POS + NEG]
    pos = [r for r in rows if r["split"] in POS]
    neg = [r for r in rows if r["split"] in NEG]
    if not a.full and a.neg_sample and len(neg) > a.neg_sample:
        rnd = random.Random(a.seed)
        by = {}
        for r in neg:
            by.setdefault(r["split"], []).append(r)
        neg = []
        for k, v in by.items():                      # proportional stratified sample
            n = max(1, round(a.neg_sample * len(v) / sum(len(x) for x in by.values())))
            neg += rnd.sample(v, min(n, len(v)))
    work = pos + neg
    print(f"rule: peak>={tau} area>={min_area} | device {dev} {'fp16' if half else 'fp32'}")
    print(f"frames: {len(pos)} polyp, {len(neg)} polyp-free ({'FULL' if a.full else 'sampled'})")
    print(f"levels {a.levels} x kinds {a.kinds} -> {len(work)*((len(a.levels)-1)*len(a.kinds)+1)} inferences\n")

    conds = [("sharp", 0)] + [(k, L) for k in a.kinds for L in a.levels if L > 0]
    res = dict(ckpt=os.path.basename(a.ckpt), model=a.model, rule=dict(tau=tau, area=min_area),
               n_pos=len(pos), n_neg=len(neg), full=a.full, conditions={})
    ex_dir = os.path.join(a.out, "examples")
    if a.dump_examples:
        os.makedirs(ex_dir, exist_ok=True)

    cache = {}
    for kind, L in conds:
        key = f"{kind}_L{L}" if L else "sharp"
        rng = random.Random(a.seed)
        agg = {}
        t0 = time.time(); dumped = 0
        for i, r in enumerate(work):
            ip = os.path.join(a.root, r["image"])
            img = cache.get(ip)
            if img is None:
                img = cv2.imread(ip, cv2.IMREAD_COLOR)
                if img is None:
                    continue
                if len(cache) < 400:
                    cache[ip] = img
            b = blur(img, kind, L, rng) if L else img
            if a.dump_examples and dumped < a.dump_examples and r["split"] == "test_kvasir":
                cv2.imwrite(os.path.join(ex_dir, f"{key}__{os.path.basename(r['image'])}"), b); dumped += 1
            p = prob_map(model, b, dev, a.size, half)
            alarm, keep = decide(p, tau, min_area)
            s = agg.setdefault(r["split"], dict(n=0, hit=0, dice=0.0))
            s["n"] += 1
            if r["split"] in NEG:
                s["hit"] += int(alarm)
            else:
                gt = cv2.imread(os.path.join(a.root, r["mask"]), cv2.IMREAD_GRAYSCALE)
                gt = (cv2.resize(gt, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST) > 127) \
                    if gt is not None and gt.shape != img.shape[:2] else (gt > 127)
                s["hit"] += int(alarm and (keep & gt).any())
                inter = float((keep & gt).sum()); den = float(keep.sum() + gt.sum())
                s["dice"] += (2 * inter / den) if den else 1.0
            if (i + 1) % 500 == 0:
                print(f"  {key}: {i+1}/{len(work)}  {time.time()-t0:.0f}s", flush=True)
        out = {}
        for sp, s in agg.items():
            out[sp] = dict(n=s["n"], rate=round(s["hit"] / s["n"], 4),
                           dice=round(s["dice"] / s["n"], 4) if sp in POS else None)
        pn = sum(s["n"] for k, s in agg.items() if k in POS)
        ph = sum(s["hit"] for k, s in agg.items() if k in POS)
        out["_pos_detection"] = round(ph / pn, 4) if pn else None
        for k in NEG:
            out[f"_fa_{k}"] = out.get(k, {}).get("rate")
        res["conditions"][key] = out
        print(f"{key:14s} detection {out['_pos_detection']}  FA_pg {out.get('_fa_neg_polypgen')}"
              f"  FA_hk {out.get('_fa_neg_hyperkvasir')}  ({time.time()-t0:.0f}s)", flush=True)

    print("\n{:<14}{:>11}{:>10}{:>10}{:>9}{:>9}".format("condition", "detection", "FA pg", "FA hk", "Dice K", "Dice E"))
    print("-" * 65)
    for k, v in res["conditions"].items():
        print("{:<14}{:>11}{:>10}{:>10}{:>9}{:>9}".format(
            k, v["_pos_detection"], v.get("_fa_neg_polypgen") or "-", v.get("_fa_neg_hyperkvasir") or "-",
            (v.get("test_kvasir") or {}).get("dice") or "-", (v.get("test_etis") or {}).get("dice") or "-"))

    os.makedirs(a.out, exist_ok=True)
    fp = os.path.join(a.out, f"blur_{a.model}_{'full' if a.full else 'sample'}.json")
    json.dump(res, open(fp, "w"), indent=1)
    print("\nwrote", fp)


if __name__ == "__main__":
    main()
