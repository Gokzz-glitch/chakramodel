"""Latency + VRAM benchmark for the pitch's "model latency" question.

Run on the RTX 3050 (4 GB). Measures, per model, at 352x352 batch 1:
  - pure forward pass: p50 / p95 / mean ms, FPS
  - end-to-end frame pipeline: BGR frame in -> decision out (resize, normalise,
    forward, sigmoid, upsample to native res, connected components, rule) which is
    the number that decides whether we keep up with a 25-30 fps endoscope feed
  - peak VRAM for the forward pass

  python bench_latency.py --models xattn unet_r34 segformer_b2 fpn_pvtv2b2 --precision fp16 fp32
  python bench_latency.py --models xattn --precision fp16 --native 1080   # 1080p frames

Output: local_tests/out/latency_<gpu>.json  +  a printed table.
Nothing here needs the datasets; a synthetic frame is used so the number is pure compute.
"""
import argparse, json, os, platform, statistics, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LEAK = os.path.dirname(HERE)
sys.path.insert(0, LEAK)

import cv2, torch, torch.nn.functional as F

MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
CKPT = os.path.join(LEAK, "chakraguard", "e4_negtrain__xattn__s43.pt")


def build(name, size=352, ckpt=None):
    """Same constructors as leakbench/train.py, so the numbers are comparable to the paper's."""
    if name == "xattn":
        from xattn_unet import ChakraXAttnUNet
        m = ChakraXAttnUNet(pretrained=False, image_size=size)
        if ckpt and os.path.exists(ckpt):
            m.load_state_dict(torch.load(ckpt, map_location="cpu"))
        return m
    import segmentation_models_pytorch as smp
    if name == "unet_r34":
        return smp.Unet("resnet34", encoder_weights=None, classes=1)
    if name == "segformer_b2":
        return smp.Segformer("mit_b2", encoder_weights=None, classes=1)
    if name == "fpn_pvtv2b2":
        return smp.FPN("tu-pvt_v2_b2", encoder_weights=None, classes=1)
    raise SystemExit(f"unknown model {name}")


def sync(dev):
    if dev.startswith("cuda"):
        torch.cuda.synchronize()


def time_forward(model, dev, size, half, warm=20, iters=200):
    x = torch.randn(1, 3, size, size, device=dev, dtype=torch.float16 if half else torch.float32)
    if dev.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()
    with torch.no_grad():
        for _ in range(warm):
            o = model(x)
        sync(dev)
        ts = []
        for _ in range(iters):
            t0 = time.perf_counter()
            o = model(x)
            sync(dev)
            ts.append((time.perf_counter() - t0) * 1000)
    peak = torch.cuda.max_memory_allocated() / 2**20 if dev.startswith("cuda") else None
    return ts, peak


def time_pipeline(model, dev, size, half, native_h, native_w, warm=10, iters=100):
    """Full per-frame cost the product actually pays, including the decision rule."""
    frame = (np.random.rand(native_h, native_w, 3) * 255).astype(np.uint8)
    dt = torch.float16 if half else torch.float32
    ts = []
    with torch.no_grad():
        for i in range(warm + iters):
            t0 = time.perf_counter()
            x = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            x = cv2.resize(x, (size, size), interpolation=cv2.INTER_LINEAR)
            x = ((x.astype(np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)[None]
            t = torch.from_numpy(x).to(dev, dtype=dt, non_blocking=True)
            o = model(t)
            o = o["mask"] if isinstance(o, dict) else o
            p = torch.sigmoid(o.float())
            p = F.interpolate(p, size=(native_h, native_w), mode="bilinear", align_corners=False)
            pm = p[0, 0].cpu().numpy()
            n, lab, st, _ = cv2.connectedComponentsWithStats((pm > 0.5).astype(np.uint8), 8)
            for c in range(1, n):
                _ = float(pm[lab == c].max()), int(st[c, cv2.CC_STAT_AREA])
            sync(dev)
            if i >= warm:
                ts.append((time.perf_counter() - t0) * 1000)
    return ts


def stat(ts):
    ts = sorted(ts)
    return dict(mean_ms=round(statistics.mean(ts), 2), p50_ms=round(ts[len(ts) // 2], 2),
                p95_ms=round(ts[int(.95 * len(ts))], 2), fps=round(1000 / statistics.mean(ts), 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["xattn", "unet_r34", "segformer_b2", "fpn_pvtv2b2"])
    ap.add_argument("--precision", nargs="+", default=["fp16", "fp32"], choices=["fp16", "fp32"])
    ap.add_argument("--size", type=int, default=352)
    ap.add_argument("--native", type=int, default=1080, help="native frame height for the pipeline test")
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--ckpt", default=CKPT)
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    a = ap.parse_args()

    dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    gpu = torch.cuda.get_device_name(0) if dev.startswith("cuda") else platform.processor() or "cpu"
    total_vram = round(torch.cuda.get_device_properties(0).total_memory / 2**20) if dev.startswith("cuda") else None
    nh, nw = a.native, int(round(a.native * 16 / 9))
    print(f"device: {gpu}  vram: {total_vram} MiB  torch {torch.__version__}  cuda {torch.version.cuda}")
    print(f"input {a.size}x{a.size} batch 1 | pipeline frame {nw}x{nh}\n")

    res = dict(gpu=gpu, total_vram_mib=total_vram, torch=torch.__version__, cuda=torch.version.cuda,
               size=a.size, native=[nh, nw], iters=a.iters, models={})
    rows = []
    for name in a.models:
        try:
            base = build(name, a.size, a.ckpt if name == "xattn" else None)
        except Exception as e:
            print(f"{name}: SKIP ({type(e).__name__}: {e})")
            continue
        res["models"][name] = {}
        for prec in a.precision:
            half = prec == "fp16"
            m = base.half() if half else base.float()
            m = m.eval().to(dev)
            try:
                ts, peak = time_forward(m, dev, a.size, half, iters=a.iters)
                fwd = stat(ts); fwd["peak_vram_mib"] = round(peak, 1) if peak else None
                pts = time_pipeline(m, dev, a.size, half, nh, nw, iters=max(50, a.iters // 4))
                pipe = stat(pts)
            except torch.cuda.OutOfMemoryError:
                print(f"{name} {prec}: OOM")
                torch.cuda.empty_cache(); continue
            res["models"][name][prec] = dict(forward=fwd, pipeline=pipe)
            rows.append((name, prec, fwd, pipe))
            m.to("cpu")
            if dev.startswith("cuda"):
                torch.cuda.empty_cache()
        del base

    w = "{:<14}{:<6}{:>10}{:>10}{:>9}{:>11}{:>11}{:>10}{:>9}"
    print(w.format("model", "prec", "fwd p50", "fwd p95", "fwd fps", "pipe p50", "pipe p95", "pipe fps", "VRAM"))
    print("-" * 90)
    for name, prec, f, p in rows:
        print(w.format(name, prec, f["p50_ms"], f["p95_ms"], f["fps"], p["p50_ms"], p["p95_ms"], p["fps"],
                       f["peak_vram_mib"] or "-"))
    print("\npipe fps is the honest product number: a 25-30 fps feed needs pipe p95 below 33-40 ms.")

    os.makedirs(a.out, exist_ok=True)
    tag = "".join(c if c.isalnum() else "_" for c in gpu.lower())[:40]
    fp = os.path.join(a.out, f"latency_{tag}.json")
    json.dump(res, open(fp, "w"), indent=1)
    print("wrote", fp)


if __name__ == "__main__":
    main()
