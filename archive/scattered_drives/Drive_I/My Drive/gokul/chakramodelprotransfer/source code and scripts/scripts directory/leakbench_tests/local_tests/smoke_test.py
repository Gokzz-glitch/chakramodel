"""Pre-pitch smoke test. Run this first; everything else assumes it passed.

  python smoke_test.py

Checks, in order, and stops at the first hard failure:
  1  python / torch / cuda / GPU name and free VRAM
  2  the imports the other scripts need (cv2, timm, segmentation_models_pytorch)
  3  ChakraGuard checkpoint loads into ChakraXAttnUNet with zero missing keys
  4  one forward pass on a synthetic frame, fp16, and a plausible probability range
  5  the dataset root resolves and the eval manifest's files exist
  6  the published operating point reproduces on the two small splits:
     Kvasir-100 detection 0.990 and ClinicDB-62 detection 1.000 at peak>=0.995
     (these are the numbers in the model card; a mismatch means the wrong checkpoint
      or a changed preprocessing path, and nothing downstream should be trusted)
  7  chakraguard/predict.py runs end to end on a 20-frame folder
"""
import json, os, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
LEAK = os.path.dirname(HERE)
ROOT = os.path.dirname(LEAK)
sys.path.insert(0, LEAK); sys.path.insert(0, HERE)
OK, BAD = "  PASS", "  FAIL"
fails = []


def step(n, what):
    print(f"\n[{n}] {what}")


def main():
    step(1, "environment")
    print(f"  python {sys.version.split()[0]}  {sys.platform}")
    import torch
    print(f"  torch {torch.__version__}  cuda build {torch.version.cuda}  available {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        p = torch.cuda.get_device_properties(0)
        free, total = torch.cuda.mem_get_info()
        print(f"  gpu {p.name}  {total/2**20:.0f} MiB total, {free/2**20:.0f} MiB free, cc {p.major}.{p.minor}")
        if total / 2**20 < 3500:
            print("  note: under 4 GB of VRAM, use --precision fp16 only")
    else:
        print("  no CUDA: everything still runs on CPU, roughly 30x slower")
    print(OK)

    step(2, "imports")
    for mod in ["cv2", "numpy", "timm", "segmentation_models_pytorch"]:
        try:
            m = __import__(mod)
            print(f"  {mod:30s} {getattr(m, '__version__', '?')}")
        except Exception as e:
            print(f"  {mod:30s} MISSING ({e})")
            if mod in ("cv2", "numpy", "timm"):
                fails.append(f"import {mod}")
            else:
                print("  (only needed to benchmark the baseline models, not ChakraGuard)")
    print(BAD if fails else OK)
    if fails:
        return done()

    step(3, "checkpoint")
    ck = os.path.join(LEAK, "chakraguard", "e4_negtrain__xattn__s43.pt")
    if not os.path.exists(ck):
        fails.append("checkpoint missing"); print(f"  {ck} not found"); print(BAD); return done()
    from xattn_unet import ChakraXAttnUNet
    model = ChakraXAttnUNet(pretrained=False, image_size=352)
    sd = torch.load(ck, map_location="cpu")
    miss, extra = model.load_state_dict(sd, strict=False)
    n = sum(p.numel() for p in model.parameters())
    print(f"  {os.path.basename(ck)}  {os.path.getsize(ck)/2**20:.0f} MiB  params {n/1e6:.1f}M")
    print(f"  missing keys {len(miss)}  unexpected {len(extra)}")
    if miss or extra:
        fails.append("state_dict mismatch"); print(BAD); return done()
    print(OK)

    step(4, "forward pass")
    import numpy as np, torch
    dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    half = dev.startswith("cuda")
    m = (model.half() if half else model.float()).eval().to(dev)
    x = torch.randn(1, 3, 352, 352, device=dev, dtype=torch.float16 if half else torch.float32)
    t0 = time.perf_counter()
    with torch.no_grad():
        o = m(x)
    o = o["mask"] if isinstance(o, dict) else o
    p = torch.sigmoid(o.float())
    if dev.startswith("cuda"):
        torch.cuda.synchronize()
    print(f"  out {tuple(o.shape)}  prob range {p.min():.3f}..{p.max():.3f}  first call {(time.perf_counter()-t0)*1000:.0f} ms")
    if not (0 <= float(p.min()) and float(p.max()) <= 1):
        fails.append("probabilities out of range")
    print(BAD if "probabilities out of range" in fails else OK)

    step(5, "dataset")
    import csv
    mf = os.path.join(LEAK, "manifests", "r2_e4_eval.csv")
    rows = list(csv.DictReader(open(mf)))
    missing = [r for r in rows[::37] if not os.path.exists(os.path.join(ROOT, r["image"]))]
    print(f"  manifest {os.path.basename(mf)}  {len(rows)} rows  root {ROOT}")
    print(f"  spot-checked {len(rows[::37])} paths, {len(missing)} missing")
    if missing:
        print("   e.g.", missing[0]["image"]); fails.append("dataset paths")
    print(BAD if missing else OK)

    step(6, "operating point reproduces (Kvasir-100, ClinicDB-62)")
    if not missing:
        from blur_robustness import prob_map, decide
        import cv2
        tau, area = 0.995, 1
        exp = {"test_kvasir": 0.990, "test_clinicdb": 1.000}
        for sp, want in exp.items():
            sub = [r for r in rows if r["split"] == sp]
            hit = 0
            for r in sub:
                img = cv2.imread(os.path.join(ROOT, r["image"]), cv2.IMREAD_COLOR)
                gt = cv2.imread(os.path.join(ROOT, r["mask"]), cv2.IMREAD_GRAYSCALE)
                pm = prob_map(m, img, dev, 352, half)
                al, keep = decide(pm, tau, area)
                if gt.shape != img.shape[:2]:
                    gt = cv2.resize(gt, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
                hit += int(al and (keep & (gt > 127)).any())
            got = hit / len(sub)
            d = abs(got - want)
            print(f"  {sp:15s} n={len(sub):4d}  detection {got:.3f}  expected {want:.3f}  delta {d:.3f}"
                  f"  {'ok' if d <= 0.02 else 'MISMATCH'}")
            if d > 0.02:
                fails.append(f"{sp} detection {got:.3f} != {want:.3f}")
        print(BAD if any("detection" in f for f in fails) else OK)
    else:
        print("  skipped (dataset paths failed)")

    step(7, "predict.py end to end")
    sub = [r for r in rows if r["split"] == "test_kvasir"][:20]
    with tempfile.TemporaryDirectory() as td:
        fr = os.path.join(td, "frames"); os.makedirs(fr)
        import shutil
        for r in sub:
            shutil.copy(os.path.join(ROOT, r["image"]), fr)
        cmd = [sys.executable, os.path.join(LEAK, "chakraguard", "predict.py"),
               "--input", fr, "--out", os.path.join(td, "out")]
        pr = subprocess.run(cmd, capture_output=True, text=True)
        print("  " + " ".join(cmd[1:]))
        print("  exit", pr.returncode)
        if pr.returncode != 0:
            print("  " + (pr.stderr or pr.stdout).strip()[-800:]); fails.append("predict.py")
        else:
            outs = os.listdir(os.path.join(td, "out"))
            print(f"  produced {len(outs)} items: {outs[:5]}")
    print(BAD if "predict.py" in fails else OK)
    return done()


def done():
    print("\n" + "=" * 60)
    if fails:
        print("SMOKE TEST FAILED:")
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("SMOKE TEST PASSED - bench_latency.py and blur_robustness.py are safe to run.")


if __name__ == "__main__":
    import torch  # noqa: F401  (imported inside main too; here so a bad install fails loudly)
    main()
