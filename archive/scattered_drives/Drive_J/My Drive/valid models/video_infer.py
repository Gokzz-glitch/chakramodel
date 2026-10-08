"""YOLO video inference worker, launched by backend.py.

Writes the annotated video to LOCAL scratch first, re-encodes to H.264 (+faststart) when
ffmpeg is available so the result plays in browsers and uploads cleanly to YouTube, then
moves it to --output (which may live on a Google Drive mount). Prints `PROGRESS done/total`
lines that the backend turns into a progress bar.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def pick_device(requested, strict=False):
    try:
        import torch
        cuda = torch.cuda.is_available()
    except Exception:  # noqa: BLE001 - torch missing or broken -> CPU
        cuda = False
    if requested in (None, "", "auto"):
        return "cuda" if cuda else "cpu"
    if requested.startswith("cuda") and not cuda:
        if strict:
            print("ERROR: CUDA was requested but PyTorch cannot see a GPU here; refusing to fall back to the CPU.", flush=True)
            sys.exit(3)
        print("WARNING: CUDA requested but not available; falling back to CPU.", flush=True)
        return "cpu"
    return requested


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - optional dependency
        return None


def finalize(raw, output):
    """Re-encode raw (mp4v) to H.264 when possible, then move to the final location."""
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    if ffmpeg:
        encoded = raw.with_name("h264.mp4")
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(raw), "-an", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(encoded)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0 and encoded.is_file() and encoded.stat().st_size > 0:
            raw = encoded
        else:
            print("WARNING: H.264 re-encode failed, keeping mp4v output.\n" + result.stderr[-500:], flush=True)
    else:
        print("WARNING: ffmpeg not found; output is mp4v and may not play in browsers/YouTube. "
              "Install it with: pip install imageio-ffmpeg", flush=True)
    shutil.move(str(raw), str(output))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weights", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--strict-device", action="store_true", help="exit instead of falling back to the CPU when CUDA is requested")
    parser.add_argument("--half", action="store_true", help="FP16 inference (CUDA only; test on your checkpoint first)")
    args = parser.parse_args()

    import cv2
    from ultralytics import YOLO

    source, output = Path(args.source), Path(args.output)
    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise SystemExit(f"Unable to open video: {source}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()

    device = pick_device(args.device, args.strict_device)
    print(f"Device: {device} | {width}x{height} @ {fps:.1f} fps | {total or '?'} frames", flush=True)
    model = YOLO(args.weights)

    scratch = Path(tempfile.mkdtemp(prefix="polyp_infer_"))
    raw = scratch / "raw.mp4"
    writer = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise SystemExit("Could not open a video writer for the output.")
    try:
        done, last = 0, 0.0
        # stream=True lets Ultralytics read frames lazily instead of loading the whole video
        for result in model.predict(source=str(source), stream=True, conf=args.threshold, device=device,
                                    half=args.half and device != "cpu", verbose=False):
            writer.write(result.plot())
            done += 1
            now = time.monotonic()
            if now - last > 0.5:
                print(f"PROGRESS {done}/{total}", flush=True)
                last = now
        writer.release()
        print(f"PROGRESS {done}/{done}", flush=True)
        if done == 0:
            raise SystemExit("No frames were processed.")
        finalize(raw, output)
        print(f"Saved annotated video: {output}", flush=True)
    finally:
        writer.release()
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
