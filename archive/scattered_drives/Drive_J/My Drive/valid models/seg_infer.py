"""PraNet / PVT-PraNet / ChakraNet video inference worker (runs on the Kaggle GPU, launched by backend.py).

Same contract as video_infer.py: reads --source, writes an annotated video to local scratch,
re-encodes to H.264, moves it to --output, prints `PROGRESS done/total` lines.

PraNet and PVT-PraNet mirror the project's evaluators (MyTest_med.py): BGR->RGB, resize to 352x352,
/255, ImageNet mean/std, take the LAST of the four outputs, resize the logits to the frame size,
sigmoid, threshold the RAW probability.

ChakraNet (adabn-chakranet notebook) uses the same preprocessing, a single logit map, and by default
test-time AdaBN first: all BatchNorm2d running statistics are reset (momentum=None, cumulative average)
and re-estimated by forward passes over unlabelled frames of the video being processed
(notebook defaults: 10 batches x 32 frames), with no backprop, then frozen for inference.
"""
import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
ARCHES = ("pranet", "pvt_pranet", "chakranet")


def build_model(arch, lib_parent):
    """Import <lib_parent>/lib as a package and construct the network without needing the
    pretrained-backbone files the constructors normally read (the checkpoint overwrites them)."""
    import warnings
    warnings.filterwarnings("ignore")     # the upstream lib triggers harmless timm deprecation noise
    import torch

    lib_parent = Path(lib_parent).resolve()
    need = "chakranet.py" if arch == "chakranet" else "PraNet_Res2Net.py"
    if not (lib_parent / "lib" / need).is_file():
        sys.exit(f"ERROR: {lib_parent / 'lib' / need} not found.")
    (lib_parent / "lib" / "__init__.py").touch()
    sys.path.insert(0, str(lib_parent))

    if arch == "chakranet":
        from lib.chakranet import PraNetResNet101
        return PraNetResNet101(channels=64, pretrained_backbone=False)

    from lib import PraNet_Res2Net as mod
    if arch == "pranet":
        real = mod.res2net50_v1b_26w_4s
        mod.res2net50_v1b_26w_4s = lambda pretrained=False, **kw: real(False, **kw)   # skip ImageNet weights download
        return mod.PraNet()
    # PVT_PraNet loads ./models/pvt_v2_b2.pth while being built: give it a random one in a temp dir.
    from lib.pvtv2 import pvt_v2_b2
    old = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(Path(tmp) / "models")
        torch.save(pvt_v2_b2().state_dict(), Path(tmp) / "models" / "pvt_v2_b2.pth")
        os.chdir(tmp)
        try:
            return mod.PVT_PraNet()
        finally:
            os.chdir(old)


def load_weights(model, path, device):
    import torch

    try:
        state = torch.load(path, map_location=device, weights_only=True)
    except Exception:  # noqa: BLE001 - older torch, or a checkpoint wrapper with non-tensor extras
        state = torch.load(path, map_location=device, weights_only=False)
    for key in ("model_state_dict", "state_dict"):      # ChakraNet saves {'epoch','model_state_dict',...}
        if isinstance(state, dict) and key in state:
            state = state[key]
            break
    state = {(k[7:] if k.startswith("module.") else k): v for k, v in state.items()}
    model.load_state_dict(state)          # strict
    return model.to(device).eval()


def preprocess(rgb, size, device, mean, std):
    import cv2
    import numpy as np
    import torch

    x = cv2.resize(rgb, (size, size)).astype(np.float32) / 255.0
    x = torch.from_numpy(x).permute(2, 0, 1).unsqueeze(0).to(device)
    return (x - mean) / std


def adabn_adapt(model, source, device, size, mean, std, batches, batch_size, amp):
    """Test-time AdaBN exactly as the notebook's AdaBNAdapter: reset BN stats, momentum=None
    (cumulative average), forward unlabelled target batches in train mode under no_grad, then eval."""
    import cv2
    import torch
    import torch.nn as nn

    cap = cv2.VideoCapture(source)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    want = batches * batch_size
    step = max(1, total // want) if total else 1
    frames, i = [], 0
    while len(frames) < want:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            frames.append(cv2.cvtColor(cv2.resize(frame, (size, size)), cv2.COLOR_BGR2RGB))
        i += 1
    cap.release()
    if not frames:
        sys.exit("AdaBN: could not read any frames to adapt on.")

    bn = [m for m in model.modules() if isinstance(m, nn.BatchNorm2d)]
    for m in bn:
        m.reset_running_stats()
        m.momentum = None
    model.train()
    t0 = time.time()
    used = 0
    with torch.no_grad():
        for s in range(0, len(frames), batch_size):
            chunk = frames[s:s + batch_size]
            batch = preprocess_batch(chunk, device, mean, std)
            with torch.autocast(device_type="cuda", enabled=amp):
                model(batch)
            used += 1
    model.eval()
    print(f"[AdaBN] reset {len(bn)} BatchNorm2d layers; adapted on {len(frames)} frames "
          f"({used} batches of up to {batch_size}) in {time.time() - t0:.1f}s", flush=True)


def preprocess_batch(frames_rgb, device, mean, std):
    import numpy as np
    import torch

    x = torch.from_numpy(np.stack(frames_rgb).astype(np.float32) / 255.0).permute(0, 3, 1, 2).to(device)
    return (x - mean) / std


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", required=True, choices=ARCHES)
    ap.add_argument("--weights", required=True)
    ap.add_argument("--lib-parent", default=".")
    ap.add_argument("--source", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--testsize", type=int, default=352)
    ap.add_argument("--strict-device", action="store_true")
    ap.add_argument("--adabn", choices=("on", "off"), default="on", help="ChakraNet only: test-time AdaBN on the video's own frames")
    ap.add_argument("--adapt-batches", type=int, default=10)
    ap.add_argument("--adapt-batch-size", type=int, default=32)
    args = ap.parse_args()

    import cv2
    import numpy as np
    import torch
    import torch.nn.functional as F
    from video_infer import finalize, pick_device

    device = pick_device(args.device, args.strict_device)
    cap = cv2.VideoCapture(args.source)
    if not cap.isOpened():
        sys.exit(f"Unable to open video: {args.source}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Device: {device} | arch {args.arch} | {w}x{h} @ {fps:.1f} fps | {total} frames", flush=True)

    model = load_weights(build_model(args.arch, args.lib_parent), args.weights, device)
    mean = torch.tensor(IMAGENET_MEAN, device=device).view(1, 3, 1, 1)
    std = torch.tensor(IMAGENET_STD, device=device).view(1, 3, 1, 1)
    amp = device != "cpu"       # the notebook ran adaptation and evaluation under autocast
    if args.arch == "chakranet":
        if args.adabn == "on":
            adabn_adapt(model, args.source, device, args.testsize, mean, std, args.adapt_batches, args.adapt_batch_size, amp)
        else:
            print("[AdaBN] off: using the checkpoint's source-domain BatchNorm statistics", flush=True)

    scratch = Path(tempfile.mkdtemp(prefix="seg_"))
    raw = scratch / "raw.mp4"
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        sys.exit("Unable to create the output video writer.")
    done = flagged = 0
    area_sum = 0.0
    t0 = time.time()
    with torch.no_grad():
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            x = preprocess(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), args.testsize, device, mean, std)
            if args.arch == "chakranet":
                with torch.autocast(device_type="cuda", enabled=amp):
                    out = model(x)
                logits = (out[0] if isinstance(out, (tuple, list)) else out).float()
            else:
                logits = model(x)[-1]                                       # lateral_map_2
            prob = F.interpolate(logits, size=(h, w), mode="bilinear", align_corners=False).sigmoid()[0, 0]
            mask = (prob > args.threshold).cpu().numpy().astype(np.uint8)
            if mask.any():
                flagged += 1
                area_sum += float(mask.mean())
                tint = frame.copy()
                tint[mask > 0] = (0.55 * tint[mask > 0] + 0.45 * np.array((0, 255, 0))).astype(np.uint8)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(tint, contours, -1, (0, 255, 0), 2)
                frame = tint
            writer.write(frame)
            done += 1
            if done % 10 == 0 or done == total:
                print(f"PROGRESS {done}/{total or done}", flush=True)
    cap.release()
    writer.release()
    if done == 0:
        sys.exit("No frames could be read from the video.")
    print(f"PROGRESS {done}/{done}", flush=True)
    print(f"Frames with a predicted region: {flagged}/{done} ({100 * flagged / done:.1f}%)"
          + (f", mean area {100 * area_sum / flagged:.2f}% of the frame" if flagged else "")
          + f" | {done / max(time.time() - t0, 1e-6):.1f} fps", flush=True)
    finalize(raw, Path(args.output))
    print(f"Saved annotated video: {args.output}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
