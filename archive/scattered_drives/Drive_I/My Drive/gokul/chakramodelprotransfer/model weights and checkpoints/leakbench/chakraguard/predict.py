"""ChakraGuard v1 — run the calibrated polyp detector on a video or a folder of frames.

  python predict.py --input clip.mp4 --out out/          # video -> annotated video + per-frame CSV
  python predict.py --input frames/ --out out/           # folder of images -> overlays + CSV
  python predict.py --input clip.mp4 --out out/ --persist 5   # only alarm after 5 consecutive frames

Needs: torch, timm, opencv-python, numpy, and xattn_unet.py from the leakbench folder beside this file.
The decision rule and the checkpoint are fixed in operating_point.json / the .pt file; --tau and --min-area
override them only for experiments, and any number you report must say which rule produced it.
"""
import argparse, csv, json, os, sys, time
import cv2, numpy as np, torch, torch.nn.functional as F

HERE = os.path.dirname(os.path.abspath(__file__))
MEAN = np.array([0.485, 0.456, 0.406], np.float32); STD = np.array([0.229, 0.224, 0.225], np.float32)

def build(ckpt, device, size=352):
    sys.path.insert(0, os.path.dirname(HERE))          # leakbench/, for xattn_unet.py
    from xattn_unet import ChakraXAttnUNet
    m = ChakraXAttnUNet(pretrained=False, image_size=size)
    sd = torch.load(ckpt, map_location=device)
    m.load_state_dict(sd); m.eval().to(device)
    return m

@torch.no_grad()
def probs(model, frame_bgr, device, size=352):
    """-> probability map at the frame's own resolution."""
    h, w = frame_bgr.shape[:2]
    x = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    x = cv2.resize(x, (size, size), interpolation=cv2.INTER_LINEAR)
    x = ((x.astype(np.float32) / 255 - MEAN) / STD).transpose(2, 0, 1)[None]
    with torch.autocast(device_type=device.split(":")[0], enabled=device.startswith("cuda")):
        o = model(torch.from_numpy(x).to(device))
        o = o["mask"] if isinstance(o, dict) else o
    p = torch.sigmoid(o.float())
    return F.interpolate(p, size=(h, w), mode="bilinear", align_corners=False)[0, 0].cpu().numpy()

def regions(p, tau, min_area, thr=0.5):
    """Regions the rule keeps: p>0.5 components whose peak probability >= tau and area >= min_area."""
    n, lab, st, cen = cv2.connectedComponentsWithStats((p > thr).astype(np.uint8), connectivity=8)
    keep = []
    for c in range(1, n):
        mk = lab == c; a = int(st[c, cv2.CC_STAT_AREA]); pk = float(p[mk].max())
        if pk >= tau and a >= min_area:
            keep.append(dict(area=a, peak=pk, box=[int(st[c, cv2.CC_STAT_LEFT]), int(st[c, cv2.CC_STAT_TOP]),
                                                   int(st[c, cv2.CC_STAT_WIDTH]), int(st[c, cv2.CC_STAT_HEIGHT])], mask=mk))
    return keep

def draw(frame, keep, alarm):
    out = frame.copy()
    for r in keep:
        col = (32, 180, 60) if alarm else (150, 150, 150)
        out[r["mask"]] = (0.75 * out[r["mask"]] + 0.25 * np.array(col)).astype(np.uint8)
        x, y, w, h = r["box"]; cv2.rectangle(out, (x, y), (x + w, y + h), col, 2)
        cv2.putText(out, f"{r['peak']:.2f}", (x, max(18, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, .6, col, 2)
    cv2.putText(out, "POLYP" if alarm else "", (16, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (32, 180, 60), 2)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="video file or folder of images")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ckpt", default=None, help="default: the checkpoint named in operating_point.json")
    ap.add_argument("--tau", type=float, default=None); ap.add_argument("--min-area", type=int, default=None)
    ap.add_argument("--persist", type=int, default=1, help="video only: alarm after N consecutive frames")
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    op = json.load(open(os.path.join(HERE, "operating_point.json")))
    tau = a.tau if a.tau is not None else op["rule"]["tau"]
    min_area = a.min_area if a.min_area is not None else op["rule"]["area"]
    ckpt = a.ckpt or os.path.join(HERE, f"e4_negtrain__xattn__s{op['chosen_seed']}.pt")
    model = build(ckpt, a.device)
    print(f"ChakraGuard v1 | {os.path.basename(ckpt)} | rule: peak>={tau}, area>={min_area}px (at 352), persist={a.persist}")
    rows = []; run = 0; t0 = time.time(); writer = None
    if os.path.isdir(a.input):
        files = sorted(f for f in os.listdir(a.input) if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif")))
        src = ((f, cv2.imread(os.path.join(a.input, f))) for f in files); total = len(files)
    else:
        cap = cv2.VideoCapture(a.input); total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        def gen():
            i = 0
            while True:
                ok, fr = cap.read()
                if not ok: break
                yield f"{i:06d}", fr; i += 1
        src = gen()
    for name, frame in src:
        if frame is None: continue
        p = probs(model, frame, a.device)
        keep = regions(p, tau, min_area)
        run = run + 1 if keep else 0
        alarm = bool(keep) and run >= a.persist
        rows.append(dict(frame=name, alarm=int(alarm), n_regions=len(keep),
                         peak=round(max([r["peak"] for r in keep], default=float(p.max())), 4),
                         area_frac=round(float((p > .5).mean()), 5)))
        if not a.no_video:
            vis = draw(frame, keep, alarm)
            if os.path.isdir(a.input): cv2.imwrite(os.path.join(a.out, name), vis)
            else:
                if writer is None:
                    writer = cv2.VideoWriter(os.path.join(a.out, "annotated.mp4"),
                                             cv2.VideoWriter_fourcc(*"mp4v"), fps, (frame.shape[1], frame.shape[0]))
                writer.write(vis)
    if writer is not None: writer.release()
    with open(os.path.join(a.out, "frames.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    n = len(rows); al = sum(r["alarm"] for r in rows); dt = time.time() - t0
    print(f"{n} frames in {dt:.1f}s ({n/max(dt,1e-6):.1f} fps) | alarms on {al} frames ({al/max(n,1):.1%}) | wrote {a.out}")

if __name__ == "__main__":
    main()
