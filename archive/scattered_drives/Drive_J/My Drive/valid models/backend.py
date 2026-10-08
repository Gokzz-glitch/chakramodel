#!/usr/bin/env python3
"""Polyp evaluation backend.

Serves the UI in ui/index.html and a small JSON API on http://127.0.0.1:8000.

Design notes
  * Models are discovered from models/<name>/model.json. Weights, library parent and
    evaluator paths are resolved from the manifest, so selecting a model in the UI
    auto-configures everything. Readiness (weights present, lib source present,
    Python packages installed) is reported per model before a job can be started.
  * Input drive (dataset, e.g. I:) and output drive (e.g. J:) are discovered from the
    Google Drive for Desktop mounts, so a changed drive letter does not break anything.
    Override with config.json {"input_root": "...", "output_root": "..."} or the
    POLYP_INPUT_ROOT / POLYP_OUTPUT_ROOT environment variables.
  * Every filesystem path received from the browser is checked against an allow-list
    of roots. The server binds to 127.0.0.1 and rejects foreign Host/Origin headers.
  * Jobs run on a worker pool (1 by default, so GPU jobs never overlap). Download,
    frame extraction and inference all happen off the HTTP threads and report progress.
"""
import ctypes
import importlib.util
import ipaddress
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

# --------------------------------------------------------------------------- config
ROOT = Path(__file__).resolve().parent
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
LOCAL_ONLY = HOST in ("127.0.0.1", "localhost", "::1")
MODELS_DIR = ROOT / "models"
UI_FILE = ROOT / "ui" / "index.html"
SCRATCH = Path(os.environ.get("POLYP_SCRATCH") or Path(tempfile.gettempdir()) / "polyp_eval")
UPLOAD_DIR = SCRATCH / "uploads"      # local disk on purpose: never stream temp files through Drive
FRAMES_DIR = SCRATCH / "frames"
MAX_UPLOAD = int(float(os.environ.get("POLYP_MAX_UPLOAD_GB", "8")) * (1 << 30))
MAX_JOBS = max(1, int(os.environ.get("POLYP_MAX_JOBS", "1")))
KEEP_SECONDS = 24 * 3600
CHUNK = 1 << 20
VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpeg", ".mpg", ".m4v", ".wmv"}
WEIGHT_EXT = {".pt", ".pth"}
CTYPE_EXT = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
             "video/x-msvideo": ".avi", "video/x-matroska": ".mkv", "video/mpeg": ".mpg"}
STREAM_HOSTS = ("youtube.com", "youtu.be", "vimeo.com", "dailymotion.com")
MODEL_ORDER = ["pranet_v1", "pvt_pranet_v1", "yolo_root", "yolovit_vit", "yolovit_yolo", "chakranet"]
PIP_NAME = {"cv2": "opencv-python", "ultralytics": "ultralytics", "torch": "torch"}
PROGRESS_RE = re.compile(r"^PROGRESS\s+(\d+)\s*/\s*(\d+)")
YTDLP_RE = re.compile(r"\[download\]\s+([\d.]+)%")

mimetypes.add_type("video/x-matroska", ".mkv")
mimetypes.add_type("video/x-msvideo", ".avi")


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class Cancelled(Exception):
    pass


# --------------------------------------------------------------------------- drives and paths
def load_config():
    try:
        return json.loads((ROOT / "config.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


_mount_cache = (0.0, [])


def drive_mounts():
    """Google Drive for Desktop mounts = drive letters that contain a 'My Drive' folder.
    Uses GetLogicalDrives so absent/network letters are never probed (no hangs)."""
    global _mount_cache
    if time.monotonic() - _mount_cache[0] < 5:
        return _mount_cache[1]
    mounts = []
    override = os.environ.get("POLYP_MOUNTS")
    if override:
        mounts = [Path(p) for p in override.split(os.pathsep) if p]
    elif os.name == "nt":
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(2, 26):  # skip A: and B:
            if mask >> i & 1:
                candidate = Path(f"{chr(65 + i)}:\\My Drive")
                if candidate.is_dir():
                    mounts.append(candidate)
    _mount_cache = (time.monotonic(), mounts)
    return mounts


def input_root():
    raw = os.environ.get("POLYP_INPUT_ROOT") or load_config().get("input_root")
    if raw:
        return Path(raw)
    for mount in drive_mounts():
        for rel in ("colon cancer/colon_cancer_dataset", "colon cancer"):
            if (mount / rel).is_dir():
                return mount / rel
    return None


def output_root():
    raw = os.environ.get("POLYP_OUTPUT_ROOT") or load_config().get("output_root")
    return Path(raw) if raw else ROOT / "outputs"


def allowed_roots():
    roots = [ROOT, UPLOAD_DIR, output_root(), *drive_mounts()]
    src = input_root()
    if src:
        roots.append(src)
    return roots


def under(path, root):
    try:
        p = os.path.normcase(os.path.realpath(path))
        r = os.path.normcase(os.path.realpath(root))
    except (OSError, ValueError):
        return False
    return p == r or p.startswith(r.rstrip("\\/") + os.sep)


def checked_path(raw, kind):
    """Validate a browser-supplied path: absolute, inside an allowed root, right type."""
    if not isinstance(raw, str) or not raw or "\0" in raw:
        raise ApiError(400, "Missing path.")
    p = Path(raw)
    if not p.is_absolute():
        raise ApiError(400, f"Path must be absolute: {raw}")
    if not any(under(p, r) for r in allowed_roots()):
        raise ApiError(403, f"Path is outside the mounted drives and project folders: {raw}")
    if not (p.is_file() if kind == "file" else p.is_dir()):
        raise ApiError(404, f"{'File' if kind == 'file' else 'Folder'} not found: {raw}")
    return p


def drive_label(p):
    return os.path.splitdrive(str(p))[0] or str(p)


def free_gb(p):
    p = Path(p)
    while not p.exists() and p.parent != p:
        p = p.parent
    try:
        return round(shutil.disk_usage(p).free / (1 << 30), 1)
    except OSError:
        return None


def clean_name(name, default="video.mp4"):
    name = re.sub(r"[^\w.\- ]", "_", Path(name).name).strip(" .")[:120]
    return name or default


def clean_stem(path):
    return re.sub(r"[^\w\-]", "_", re.sub(r"^[0-9a-f]{8,12}__", "", Path(path).stem))[:60] or "video"


# --------------------------------------------------------------------------- models
def has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def locate_lib_parent(folder, hint, required):
    """Folder that CONTAINS lib/ with the model source files. Searches a few known spots."""
    primary = (folder / hint).resolve() if hint else folder
    for cand in (primary, folder, folder / "binary_seg", ROOT / "binary_seg", ROOT):
        if all((cand / "lib" / f).is_file() for f in required):
            return cand
    return primary


# Set by run_all.py when a Kaggle session is requested: nothing may run on this PC's CPU/GPU.
REMOTE_ONLY = os.environ.get("POLYP_REMOTE_ONLY") == "1"
REMOTE_ONLY_NOTE = "Remote-only mode: inference runs on the Kaggle GPU, never on this PC."


def remote_arch(key, meta_arch=None):
    """Architecture name seg_infer.py knows, or None. A manifest may set "arch"; otherwise it is inferred from the key."""
    if meta_arch in ("pranet", "pvt_pranet", "chakranet"):
        return meta_arch
    k = key.lower()
    if k.startswith("chakranet"):
        return "chakranet"
    if k.startswith("pvt"):
        return "pvt_pranet"
    return "pranet" if k.startswith("pranet") else None


def check_model(m, weights, lib_parent):
    issues = []
    if m["engine"] == "unsupported":
        return [m["note"]]
    if m.get("arch") == "chakranet":
        return ["ChakraNet runs on the Kaggle GPU only (no local runner)."]
    if not weights.is_file():
        issues.append(f"Weights not found: {weights}")
    elif weights.suffix.lower() not in WEIGHT_EXT:
        issues.append(f"Weights must be .pt or .pth: {weights.name}")
    if m["engine"] == "yolo":
        if not (ROOT / "video_infer.py").is_file():
            issues.append("video_infer.py is missing next to backend.py")
        deps = ["cv2", "ultralytics"]
    else:
        if not m["evaluator"] or not m["evaluator"].is_file():
            issues.append(f"Evaluator script not found: {m['evaluator']}")
        missing = [f for f in m["lib_files"] if not (lib_parent / "lib" / f).is_file()]
        if missing:
            issues.append(f"Model source missing: put the original repo's lib/ folder ({', '.join(missing)}) "
                          f"in {lib_parent} (the folder that CONTAINS lib).")
        deps = ["cv2", "torch"]
    for dep in deps:
        if not has_module(dep):
            issues.append(f"Python package '{dep}' is not installed (pip install {PIP_NAME.get(dep, dep)}).")
    return issues


def load_models():
    models = {}
    for manifest in MODELS_DIR.glob("*/model.json"):
        try:
            meta = json.loads(manifest.read_text("utf-8"))
        except (OSError, ValueError):
            continue
        folder, key = manifest.parent, manifest.parent.name
        engine = {"segmentation": "segmentation", "ultralytics": "yolo"}.get(meta.get("engine"), "unsupported")
        lib_files = meta.get("library_files") or (["PraNet_Res2Net.py", "Res2Net_v1b.py"] +
                                                  (["pvtv2.py"] if "pvt" in key.lower() else []))
        m = {
            "key": key, "label": meta.get("name", key), "engine": engine,
            "inputs": ["video"] if engine == "yolo" else ["video", "dataset"],
            "weights": folder / meta.get("weights", "weights.pth"),
            "evaluator": folder / meta["evaluator"] if meta.get("evaluator") else None,
            "lib_files": lib_files, "lib_parent": None,
            "arch": remote_arch(key, meta.get("arch")) if engine == "segmentation" else None,
            "note": "No inference runner for this model yet: " + str(meta.get("status", "unsupported engine"))
                    + (f" (extract one from {meta['architecture_source']})" if meta.get("architecture_source") else ""),
        }
        if engine == "segmentation":
            m["lib_parent"] = locate_lib_parent(folder, meta.get("library_parent"), lib_files)
        m["issues"] = check_model(m, m["weights"], m["lib_parent"])
        models[key] = m
    order = {k: i for i, k in enumerate(MODEL_ORDER)}
    return dict(sorted(models.items(), key=lambda kv: (order.get(kv[0], 99), kv[0])))


def remote_model_issues(m):
    """What stops this model running on the Kaggle GPU (empty list = it can)."""
    if m["engine"] == "yolo":
        return []
    if m["engine"] == "segmentation" and m.get("arch"):
        lib = m["lib_parent"]
        need = ("chakranet.py",) if m["arch"] == "chakranet" else ("PraNet_Res2Net.py", "Res2Net_v1b.py", "pvtv2.py")
        missing = [f for f in need if not (lib and (lib / "lib" / f).is_file())]
        return [f"Model source missing locally: {', '.join(missing)} (binary_seg/lib)."] if missing else []
    return ["Not supported on Kaggle: no remote runner for this model yet."]


def public_model(m):
    try:
        size_mb = round(m["weights"].stat().st_size / (1 << 20), 1)
    except OSError:
        size_mb = None
    issues = m["issues"]
    remote_issues = remote_model_issues(m)
    if REMOTE_ONLY:   # local readiness (cv2/torch) is irrelevant: only the remote requirements count
        issues = remote_issues
    return {"key": m["key"], "label": m["label"], "engine": m["engine"], "inputs": m["inputs"],
            "ready": not issues, "issues": issues, "remote": not remote_issues, "remote_issues": remote_issues, "arch": m.get("arch"), "weights": str(m["weights"]), "weights_mb": size_mb,
            "lib_parent": str(m["lib_parent"]) if m["lib_parent"] else None,
            "evaluator": str(m["evaluator"]) if m["evaluator"] else None}


# --------------------------------------------------------------------------- jobs
class Job:
    def __init__(self, spec, source_desc):
        self.id = uuid.uuid4().hex[:8]
        self.model, self.label, self.source = spec["key"], spec["label"], source_desc
        self.status, self.stage, self.detail, self.progress = "queued", "queued", "", None
        self.log = deque(maxlen=500)
        self.command, self.error = None, None
        self.created, self.started, self.finished = time.time(), None, None
        self.out_dir, self.output_file = spec["out_dir"], None
        self.cancel, self.proc = threading.Event(), None

    def add_log(self, line):
        with JOBS_LOCK:
            self.log.append(line)

    def public(self, with_log=True):
        with JOBS_LOCK:
            log = list(self.log)[-200:] if with_log else []
        out = self.output_file
        return {"id": self.id, "model": self.model, "label": self.label, "source": self.source,
                "status": self.status, "stage": self.stage, "detail": self.detail, "progress": self.progress,
                "error": self.error, "created": self.created, "started": self.started, "finished": self.finished,
                "now": time.time(), "out_dir": str(self.out_dir), "output_file": str(out) if out else None,
                "has_video": bool(out and Path(out).suffix.lower() == ".mp4" and Path(out).is_file()),
                "command": self.command, "log": log}


JOBS = {}
JOBS_LOCK = threading.Lock()
EXECUTOR = ThreadPoolExecutor(max_workers=MAX_JOBS, thread_name_prefix="job")


def find_upload(upload_id):
    if not isinstance(upload_id, str) or not re.fullmatch(r"[0-9a-f]{12}", upload_id):
        raise ApiError(400, "Invalid upload id.")
    matches = list(UPLOAD_DIR.glob(f"{upload_id}__*"))
    if not matches:
        raise ApiError(404, "Uploaded file no longer exists. Upload it again.")
    return matches[0]


def submit_job(body):
    models = load_models()
    m = models.get(body.get("model"))
    if m is None:
        raise ApiError(400, "Unknown model.")
    weights, lib_parent = m["weights"], m["lib_parent"]
    overrides = body.get("overrides") or {}
    if overrides.get("weights"):
        weights = checked_path(overrides["weights"], "file")
    if overrides.get("lib_parent") and m["engine"] == "segmentation":
        lib_parent = checked_path(overrides["lib_parent"], "dir")
    target = body.get("target") or ("kaggle" if REMOTE_ONLY else "local")
    if target not in ("local", "kaggle"):
        raise ApiError(400, "Run target must be local or kaggle.")
    if REMOTE_ONLY and target != "kaggle":
        raise ApiError(400, REMOTE_ONLY_NOTE + " Connect a Kaggle session and run there.")
    if target == "kaggle":
        problems = remote_model_issues(m)
        if problems:
            raise ApiError(400, " ".join(problems))
        if kaggle_session() is None:
            raise ApiError(400, "Connect a Kaggle session first.")
        issues = []  # weights come from the Kaggle copy, the shared Drive folder, or are uploaded from this PC
    else:
        issues = check_model(m, weights, lib_parent)
    if issues:
        raise ApiError(400, "Model is not ready: " + " ".join(issues))

    src = body.get("source") or {}
    kind = src.get("type")
    if kind == "upload":
        source_desc, source = "Upload: " + re.sub(r"^[0-9a-f]{12}__", "", find_upload(src.get("id")).name), {"type": "upload", "id": src["id"]}
    elif kind == "library":
        path = checked_path(src.get("path"), "file")
        if path.suffix.lower() not in VIDEO_EXT:
            raise ApiError(400, "Not a supported video file.")
        source_desc, source = f"Drive: {path}", {"type": "library", "path": path}
    elif kind == "url":
        url = str(src.get("url", "")).strip()
        if not re.match(r"^https?://", url, re.I) or len(url) > 2048:
            raise ApiError(400, "Enter a valid http(s) video URL.")
        source_desc, source = f"URL: {url}", {"type": "url", "url": url}
    elif kind == "dataset":
        if "dataset" not in m["inputs"] or target == "kaggle":
            raise ApiError(400, "Dataset folders are only supported by segmentation models running on this PC.")
        path = checked_path(src.get("path"), "dir")
        source_desc, source = f"Dataset: {path}", {"type": "dataset", "path": path}
    else:
        raise ApiError(400, "Choose an input first.")

    try:
        threshold = float(body.get("threshold", 0.5))
        stride = int(body.get("frame_stride", 1))
    except (TypeError, ValueError):
        raise ApiError(400, "Threshold must be a number and frame stride an integer.")
    if not 0 <= threshold <= 1:
        raise ApiError(400, "Threshold must be between 0 and 1.")
    device = body.get("device", "auto")
    if device not in ("auto", "cuda", "cpu"):
        raise ApiError(400, "Device must be auto, cuda or cpu.")
    if target == "kaggle" and device != "cpu":
        device = "cuda"      # the Kaggle job must use the Kaggle GPU; it fails instead of silently using the CPU
    elif REMOTE_ONLY:
        raise ApiError(400, "CPU is disabled in remote-only mode. Use the Kaggle GPU.")

    sub = "/".join(clean_name(p, "") for p in re.split(r"[\\/]+", str(body.get("out_subdir", ""))) if p.strip(" ."))
    out_dir = output_root() / sub if sub else output_root()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        probe = out_dir / f".write_test_{uuid.uuid4().hex[:6]}"
        probe.write_bytes(b"x")
        probe.unlink()
    except OSError as e:
        raise ApiError(400, f"Output folder is not writable ({out_dir}). Is the output drive mounted? {e}")
    free = free_gb(out_dir)
    if free is not None and free < 1:
        raise ApiError(400, f"Only {free} GB free on the output drive.")

    spec = {"key": m["key"], "label": m["label"], "engine": m["engine"], "weights": weights, "lib_parent": lib_parent,
            "evaluator": m["evaluator"], "arch": m.get("arch"), "adabn": bool(body.get("adabn", True)), "source": source, "threshold": threshold, "device": device,
            "stride": max(1, min(stride, 60)), "out_dir": out_dir, "target": target,
            "compress": bool(body.get("compress_upload", True))}
    job = Job(spec, source_desc)
    with JOBS_LOCK:
        JOBS[job.id] = job
        finished = sorted((j for j in JOBS.values() if j.finished), key=lambda j: j.finished)
        for old in finished[:-40]:
            JOBS.pop(old.id, None)
    EXECUTOR.submit(run_job, job, spec)
    return job


def run_job(job, spec):
    if job.cancel.is_set():
        job.status, job.stage, job.finished = "cancelled", "cancelled", time.time()
        return
    job.status, job.started = "running", time.time()
    temp_dirs = []
    try:
        if REMOTE_ONLY and spec["target"] != "kaggle":
            raise RuntimeError(REMOTE_ONLY_NOTE)
        kind, src = prepare_source(job, spec)
        if spec["target"] == "kaggle":
            run_remote(job, spec, src, temp_dirs)
        else:
            cmd = build_command(job, spec, kind, src, temp_dirs)
            job.command = cmd
            code = execute(job, cmd)
            if code != 0:
                raise RuntimeError(f"Process exited with code {code}. See the log below.")
        if job.output_file and not Path(job.output_file).is_file():
            raise RuntimeError("The run finished but produced no output file.")
        if job.output_file:
            mirror_output(job)
        job.status, job.stage, job.progress = "completed", "done", 1.0
    except Cancelled:
        job.status, job.stage = "cancelled", "cancelled"
    except Exception as e:  # noqa: BLE001 - surface any failure to the UI
        job.status, job.stage, job.error = "failed", "failed", str(e) or e.__class__.__name__
        job.add_log("ERROR: " + job.error)
        if not isinstance(e, (RuntimeError, ApiError, OSError)):
            job.add_log(traceback.format_exc())
    finally:
        for d in temp_dirs:
            shutil.rmtree(d, ignore_errors=True)
        job.finished, job.proc = time.time(), None


def prepare_source(job, spec):
    src = spec["source"]
    if src["type"] == "upload":
        return "video", find_upload(src["id"])
    if src["type"] == "library":
        return "video", src["path"]
    if src["type"] == "dataset":
        return "dataset", src["path"]
    job.stage = "downloading"
    return "video", download(job, src["url"])


def build_command(job, spec, kind, src, temp_dirs):
    py, ts, stem = sys.executable, datetime.now().strftime("%Y%m%d-%H%M%S"), clean_stem(src)
    if spec["engine"] == "yolo":
        out = spec["out_dir"] / f"{stem}_{spec['key']}_{ts}_{job.id[:4]}.mp4"
        job.output_file = out
        return [py, str(ROOT / "video_infer.py"), "--weights", str(spec["weights"]), "--source", str(src),
                "--output", str(out), "--device", spec["device"], "--threshold", str(spec["threshold"])]
    dataset = src
    if kind == "video":  # segmentation evaluators read PolypGen-style image folders
        dataset = FRAMES_DIR / job.id
        temp_dirs.append(dataset)
        job.stage, job.progress = "extracting frames", 0.0
        extract_frames(job, src, dataset / "data_C1" / "images_C1", spec["stride"])
    job.out_dir = spec["out_dir"] / f"{spec['key']}_{stem}_{ts}_{job.id[:4]}"
    cmd = [py, str(spec["evaluator"]), "--dataset", str(dataset), "--weights", str(spec["weights"]),
           "--lib_parent", str(spec["lib_parent"]), "--out", str(job.out_dir), "--thresh", str(spec["threshold"])]
    if spec["device"] != "auto":
        cmd += ["--device", spec["device"]]
    return cmd


def extract_frames(job, video, dest, stride):
    import cv2
    dest.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {video}")
    total, i, saved = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0), 0, 0
    try:
        while cap.grab():  # grab() skips decoding-to-array work for frames we drop
            if job.cancel.is_set():
                raise Cancelled()
            if i % stride == 0:
                ok, frame = cap.retrieve()
                if not ok:
                    break
                cv2.imwrite(str(dest / f"frame_{i:06d}.jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                saved += 1
            i += 1
            if total and i % 25 == 0:
                job.progress, job.detail = min(i / total, 1.0), f"{i}/{total} frames read, {saved} kept"
    finally:
        cap.release()
    if saved == 0:
        raise RuntimeError("The video did not contain readable frames.")
    job.add_log(f"Extracted {saved} frames (stride {stride}).")


def execute(job, cmd):
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    job.stage, job.progress, job.detail = "running model", None, ""
    # stdin=DEVNULL: the evaluators fall back to input() when an argument is missing; never hang on that.
    job.proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                env=env, bufsize=1)
    for line in job.proc.stdout:
        handle_line(job, line.rstrip())
    job.proc.wait()
    if job.cancel.is_set():
        raise Cancelled()
    return job.proc.returncode


def handle_line(job, line):
    """Turn `PROGRESS done/total` lines into the progress bar; keep everything else as log."""
    m = PROGRESS_RE.match(line)
    if m:
        done, total = int(m.group(1)), int(m.group(2))
        job.progress = done / total if total else None
        job.detail = f"{done}/{total} frames" if total else f"{done} frames"
    elif line:
        job.add_log(line)


# --------------------------------------------------------------------------- Kaggle GPU target
KAGGLE = {"session": None}
KAGGLE_LOCK = threading.Lock()


def kaggle_session():
    s = KAGGLE["session"]
    return s if s is not None and s.state != "disconnected" else None


def kaggle_status():
    s = KAGGLE["session"]
    return {"connected": s is not None and s.state != "disconnected", **(s.public() if s else {"state": "disconnected"})}


def kaggle_connect(url):
    """The link contains an access token: kept in memory only, never logged or written."""
    if not isinstance(url, str) or not url.strip() or len(url) > 4096:
        raise ApiError(400, "Paste the Kaggle Jupyter-server link.")
    import kaggle_remote as kr
    with KAGGLE_LOCK:
        if KAGGLE["session"] is not None:
            KAGGLE["session"].close()
            KAGGLE["session"] = None
        try:
            session = kr.KaggleSession(url, ROOT)
            session.connect()
        except kr.RemoteError as e:
            raise ApiError(400, str(e))
        except Exception as e:  # noqa: BLE001 - never echo the exception text: it may contain the link
            raise ApiError(500, f"Unexpected error while connecting ({e.__class__.__name__}).")
        KAGGLE["session"] = session
    return kaggle_status()


def kaggle_disconnect():
    with KAGGLE_LOCK:
        if KAGGLE["session"] is not None:
            KAGGLE["session"].close()
            KAGGLE["session"] = None
    return kaggle_status()


def compress_for_upload(job, src, temp_dirs):
    """Re-encode a big AVI to H.264 before uploading (typically 10-20x smaller). Visually
    near-lossless (CRF 18) but not bit-exact, so detections can differ slightly."""
    from video_infer import find_ffmpeg
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        job.add_log("ffmpeg not found on this PC; uploading the original file (pip install imageio-ffmpeg).")
        return src
    if src.suffix.lower() == ".mp4" and src.stat().st_size < (64 << 20):
        return src
    work = SCRATCH / "remote" / job.id
    work.mkdir(parents=True, exist_ok=True)
    temp_dirs.append(work)
    dest = work / "upload.mp4"
    probe = subprocess.run([ffmpeg, "-hide_banner", "-i", str(src)], capture_output=True, text=True, errors="replace")
    d = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", probe.stderr)
    duration = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0
    job.stage, job.progress = "compressing video for upload", 0.0
    proc = subprocess.Popen([ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-an", "-c:v", "libx264", "-preset", "veryfast",
                             "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(dest)],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    job.proc = proc
    for line in proc.stdout:
        if job.cancel.is_set():
            proc.terminate()
            raise Cancelled()
        k, _, v = line.strip().partition("=")
        if k in ("out_time_us", "out_time_ms") and v.lstrip("-").isdigit() and duration:
            job.progress = max(0.0, min(int(v) / 1e6 / duration, 1.0))
    proc.wait()
    if proc.returncode != 0 or not dest.is_file():
        job.add_log("Compression failed, uploading the original: " + proc.stderr.read()[-300:])
        return src
    job.add_log(f"Compressed {src.stat().st_size >> 20} MB -> {dest.stat().st_size >> 20} MB before upload.")
    return dest


def run_remote(job, spec, src, temp_dirs):
    import kaggle_remote as kr
    session = kaggle_session()
    if session is None:
        raise RuntimeError("The Kaggle session was disconnected. Reconnect and run again.")

    def progress(label):
        def cb(done, total):
            job.progress = done / total if total else None
            job.detail = f"{label}: {done >> 20} / {total >> 20} MB"
        return cb

    key, stem, ts = spec["key"], clean_stem(src), datetime.now().strftime("%Y%m%d-%H%M%S")
    rin = rout = None
    try:
        job.stage, job.progress = "preparing Kaggle session", None
        session.wait_ready(job.cancel)
        if spec["device"] != "cpu" and (not session.gpu or session.gpu == "no GPU"):
            raise RuntimeError("This Kaggle session has no GPU. In the notebook: Settings > Accelerator > pick a GPU "
                               "(T4/P100), restart the session, and connect again. Nothing was run on this PC.")
        job.add_log("Kaggle GPU: " + str(session.gpu).splitlines()[0])
        job.stage = "checking weights on Kaggle"
        session.ensure_weights(key, spec["weights"], progress("weights"), job.cancel)
        if spec["engine"] == "segmentation":
            job.stage = "uploading model source to Kaggle"
            session.ensure_lib(spec["lib_parent"], spec["arch"])
        upload_src = compress_for_upload(job, src, temp_dirs) if spec["compress"] else src
        rin, rout = f"inputs/{job.id}_{stem}{upload_src.suffix.lower()}", f"outputs/{job.id}.mp4"
        job.output_file = spec["out_dir"] / f"{stem}_{key}_{ts}_{job.id[:4]}.mp4"
        job.stage = "uploading video to Kaggle"
        session.upload(upload_src, rin, progress("upload"), job.cancel)
        job.stage, job.progress, job.detail = "running on Kaggle GPU", None, ""
        rweights = f"models/{key}/{spec['weights'].name}"
        script = "seg_infer.py" if spec["engine"] == "segmentation" else "video_infer.py"
        job.command = ["[kaggle]", script, "--weights", rweights, "--source", rin,
                       "--output", rout, "--device", spec["device"], "--threshold", str(spec["threshold"])]
        if spec["engine"] == "segmentation":
            code = session.infer_seg(spec["arch"], rweights, rin, rout, spec["device"], spec["threshold"],
                                     lambda line: handle_line(job, line), job.cancel, adabn=spec["adabn"])
        else:
            code = session.infer(key, spec["weights"].name, rin, rout, spec["device"], spec["threshold"],
                                 lambda line: handle_line(job, line), job.cancel)
        if code != 0:
            raise RuntimeError(f"Remote inference exited with code {code}. See the log below.")
        job.stage, job.progress = "downloading result from Kaggle", 0.0
        work = SCRATCH / "remote" / job.id
        temp_dirs.append(work)
        session.download(rout, work / "result.mp4", progress("download"), job.cancel)
        job.output_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(work / "result.mp4"), str(job.output_file))   # lands on the output drive only once complete
    except kr.RemoteCancelled:
        raise Cancelled()
    except kr.RemoteError as e:
        raise RuntimeError(str(e))
    finally:
        if rin and rout:
            session.remove(rin, rout)


def mirror_output(job):
    """Copy the finished video into every folder listed under "mirror_dirs" in config.json."""
    for raw in load_config().get("mirror_dirs", []):
        d = Path(raw)
        try:
            if not d.is_dir():
                job.add_log(f"Mirror folder not found, skipped: {d}")
                continue
            shutil.copy2(job.output_file, d / Path(job.output_file).name)
            job.add_log(f"Also copied to {d}")
        except OSError as e:
            job.add_log(f"Mirror copy to {d} failed: {e}")


# --------------------------------------------------------------------------- URL download
class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_public_url(url):
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise RuntimeError("Only http(s) URLs are supported.")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80))
    except socket.gaierror as e:
        raise RuntimeError(f"Cannot resolve {u.hostname}: {e}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise RuntimeError("That URL points to a private/local address; only public URLs are allowed.")


def download(job, url):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    drive = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:export=\w+&)?id=)([\w-]+)", url)
    if drive:
        url = f"https://drive.google.com/uc?export=download&id={drive.group(1)}"
    check_public_url(url)
    host = (urlparse(url).hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in STREAM_HOSTS):
        return download_ytdlp(job, url)
    return download_http(job, url)


def download_http(job, url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (PolypEval)"})
    with build_opener(SafeRedirect()).open(req, timeout=30) as resp:
        ctype = resp.headers.get_content_type()
        if ctype in ("text/html", "application/xhtml+xml"):
            raise RuntimeError("That URL is a web page, not a video file. Use a direct video link, "
                               "install yt-dlp for YouTube/Vimeo, or pick large Google Drive files "
                               "from the Google Drive tab (Drive blocks direct download of big files).")
        total = int(resp.headers.get("Content-Length") or 0)
        if total > MAX_UPLOAD:
            raise RuntimeError(f"File is larger than the {MAX_UPLOAD >> 30} GB limit.")
        name = resp.headers.get_filename() or unquote(Path(urlparse(resp.geturl()).path).name) or "video"
        name = clean_name(name, "video")
        ext = Path(name).suffix.lower()
        if ext not in VIDEO_EXT:
            ext = CTYPE_EXT.get(ctype)
            if not ext:
                raise RuntimeError(f"Unsupported content type '{ctype}'. Expected a video file.")
            name = Path(name).stem + ext
        dest = UPLOAD_DIR / f"{job.id}__{name}"
        done = 0
        try:
            with open(dest, "wb") as f:
                while True:
                    if job.cancel.is_set():
                        raise Cancelled()
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > MAX_UPLOAD:
                        raise RuntimeError(f"Download exceeded the {MAX_UPLOAD >> 30} GB limit.")
                    f.write(chunk)
                    job.progress = done / total if total else None
                    job.detail = f"{done >> 20} MB" + (f" / {total >> 20} MB" if total else "")
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
    return dest


def download_ytdlp(job, url):
    if not has_module("yt_dlp"):
        raise RuntimeError("yt-dlp is not installed. Run: pip install yt-dlp")
    template = str(UPLOAD_DIR / f"{job.id}__%(title).80s.%(ext)s")
    cmd = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--newline", "--windows-filenames",
           "--max-filesize", str(MAX_UPLOAD), "-f", "b[ext=mp4]/b", "-o", template, url]
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    job.proc = proc
    for line in proc.stdout:
        m = YTDLP_RE.search(line)
        if m:
            job.progress, job.detail = float(m.group(1)) / 100, line.strip()[:80]
        elif line.strip():
            job.add_log(line.strip())
    proc.wait()
    if job.cancel.is_set():
        raise Cancelled()
    files = [p for p in UPLOAD_DIR.glob(f"{job.id}__*") if p.suffix.lower() in VIDEO_EXT]
    if proc.returncode != 0 or not files:
        raise RuntimeError("yt-dlp could not download that URL. See the log below.")
    return files[0]


def cleanup_scratch():
    cutoff = time.time() - KEEP_SECONDS
    for d in (UPLOAD_DIR, FRAMES_DIR):
        for p in d.glob("*"):
            try:
                if p.stat().st_mtime < cutoff:
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
            except OSError:
                pass


# --------------------------------------------------------------------------- browsing
def browse(raw, kind):
    if not raw:
        entries, seen = [], set()
        for label, p in [("Input dataset", input_root()), *[(f"Google Drive {drive_label(m)}", m) for m in drive_mounts()],
                         ("Outputs", output_root()), ("Project folder", ROOT)]:
            if p and str(p) not in seen and p.is_dir():
                seen.add(str(p))
                entries.append({"name": f"{label}  ({p})", "path": str(p), "type": "dir"})
        return {"path": "", "parent": None, "entries": entries}
    p = checked_path(raw, "dir")
    dirs, files = [], []
    try:
        with os.scandir(p) as it:
            for e in it:
                if e.name.startswith((".", "$")) or e.name.lower() == "desktop.ini":
                    continue
                try:
                    if e.is_dir():
                        dirs.append({"name": e.name, "path": e.path, "type": "dir"})
                    elif kind == "video" and Path(e.name).suffix.lower() in VIDEO_EXT:
                        files.append({"name": e.name, "path": e.path, "type": "video", "size": e.stat().st_size})
                except OSError:
                    continue
    except OSError as e:
        raise ApiError(500, f"Cannot read folder: {e}")
    key = lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", x["name"])]  # noqa: E731
    parent = p.parent if p.parent != p and any(under(p.parent, r) for r in allowed_roots()) else None
    return {"path": str(p), "parent": str(parent) if parent else "", "entries": (sorted(dirs, key=key) + sorted(files, key=key))[:3000]}


def source_signature():
    """Hash of the code files, so the launcher can tell a stale backend (old code still running) from a current one."""
    import hashlib
    h = hashlib.sha1()
    for name in ("backend.py", "kaggle_remote.py", "seg_infer.py", "video_infer.py"):
        try:
            h.update((ROOT / name).read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:12]


SIGNATURE = source_signature()


def app_state():
    src, out = input_root(), output_root()
    return {
        "models": [public_model(m) for m in load_models().values()],
        "input": {"root": str(src) if src else None, "ok": bool(src and src.is_dir()),
                  "drive": drive_label(src) if src else None},
        "output": {"root": str(out), "ok": out.is_dir() or out.parent.is_dir(), "drive": drive_label(out), "free_gb": free_gb(out)},
        "mounts": [str(m) for m in drive_mounts()],
        "kaggle": kaggle_status(),
        "remote_only": REMOTE_ONLY,
        "build": SIGNATURE,
        "caps": {"ytdlp": has_module("yt_dlp"), "ffmpeg": bool(shutil.which("ffmpeg")) or has_module("imageio_ffmpeg")},
        "limits": {"max_upload_mb": MAX_UPLOAD >> 20},
        "video_ext": sorted(VIDEO_EXT),
    }


# --------------------------------------------------------------------------- HTTP
JOB_ROUTE = re.compile(r"^/api/jobs/([0-9a-f]{8})(?:/(cancel|output))?$")


class Handler(BaseHTTPRequestHandler):
    server_version = "PolypEval/2"

    # -- helpers
    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > (1 << 20):
            raise ApiError(413, "Request too large.")
        try:
            return json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            raise ApiError(400, "Invalid JSON.")

    def guard(self, method):
        if LOCAL_ONLY:
            host = self.headers.get("Host", "")
            if re.sub(r":\d+$", "", host) not in ("127.0.0.1", "localhost", "[::1]"):
                raise ApiError(403, "Unexpected Host header.")  # blocks DNS-rebinding
        if method == "POST":
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host"):
                raise ApiError(403, "Cross-origin request rejected.")

    def serve_file(self, path):
        size = path.stat().st_size
        start, end, status = 0, size - 1, 200
        rng = self.headers.get("Range")
        if rng:
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
            if m and (m.group(1) or m.group(2)):
                a, b = m.groups()
                if a:
                    start, end = int(a), min(int(b), size - 1) if b else size - 1
                else:
                    start = max(0, size - int(b))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
                status = 206
        self.send_response(status)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(CHUNK, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    # -- dispatch
    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def dispatch(self, method):
        try:
            self.guard(method)
            url = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            route = url.path
            if method == "GET":
                self.route_get(route, query)
            else:
                self.route_post(route)
        except ApiError as e:
            self.close_connection = True
            try:
                self.send_json({"error": e.message}, e.status)
            except OSError:
                pass
        except (ConnectionError, TimeoutError):
            pass
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            try:
                self.send_json({"error": f"Internal error: {e}"}, 500)
            except OSError:
                pass

    def route_get(self, route, query):
        if route in ("/", "/index.html"):
            if not UI_FILE.is_file():
                raise ApiError(500, f"UI file missing: {UI_FILE}")
            body = UI_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif route == "/api/state":
            self.send_json(app_state())
        elif route == "/api/kaggle":
            self.send_json(kaggle_status())
        elif route == "/api/browse":
            self.send_json(browse(query.get("path", ""), query.get("kind", "video")))
        elif route == "/api/media":
            path = checked_path(query.get("path"), "file")
            if path.suffix.lower() not in VIDEO_EXT:
                raise ApiError(400, "Not a video file.")
            self.serve_file(path)
        elif route == "/api/jobs":
            with JOBS_LOCK:
                jobs = sorted(JOBS.values(), key=lambda j: j.created, reverse=True)
            self.send_json({"jobs": [j.public(with_log=False) for j in jobs]})
        else:
            m = JOB_ROUTE.match(route)
            if not m:
                raise ApiError(404, "Not found.")
            job = JOBS.get(m.group(1))
            if job is None:
                raise ApiError(404, "Job not found (the backend may have restarted).")
            if m.group(2) == "output":
                if not job.output_file or not Path(job.output_file).is_file():
                    raise ApiError(404, "This job has no video output.")
                self.serve_file(Path(job.output_file))
            elif m.group(2) is None:
                self.send_json(job.public())
            else:
                raise ApiError(404, "Not found.")

    def route_post(self, route):
        if route == "/api/upload":
            self.api_upload()
        elif route == "/api/run":
            self.send_json(submit_job(self.read_json()).public(with_log=False), 201)
        elif route == "/api/kaggle/connect":
            self.send_json(kaggle_connect(self.read_json().get("url")))
        elif route == "/api/kaggle/disconnect":
            self.send_json(kaggle_disconnect())
        else:
            m = JOB_ROUTE.match(route)
            if not (m and m.group(2) == "cancel"):
                raise ApiError(404, "Not found.")
            job = JOBS.get(m.group(1))
            if job is None:
                raise ApiError(404, "Job not found.")
            job.cancel.set()
            proc = job.proc
            if proc and proc.poll() is None:
                proc.terminate()
            self.send_json(job.public(with_log=False))

    def api_upload(self):
        """Raw-body upload (not multipart) streamed to local disk in 1 MB chunks."""
        length = int(self.headers.get("Content-Length") or 0)
        name = clean_name(unquote(self.headers.get("X-Filename", "video.mp4")))
        if Path(name).suffix.lower() not in VIDEO_EXT:
            raise ApiError(400, f"Unsupported file type. Allowed: {', '.join(sorted(VIDEO_EXT))}")
        if length <= 0:
            raise ApiError(411, "Empty upload.")
        if length > MAX_UPLOAD:
            raise ApiError(413, f"File exceeds the {MAX_UPLOAD >> 30} GB limit.")
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        upload_id = uuid.uuid4().hex[:12]
        dest = UPLOAD_DIR / f"{upload_id}__{name}"
        try:
            remaining = length
            with open(dest, "wb") as f:
                while remaining > 0:
                    chunk = self.rfile.read(min(CHUNK, remaining))
                    if not chunk:
                        raise ConnectionError("Upload interrupted.")
                    f.write(chunk)
                    remaining -= len(chunk)
        except BaseException:
            dest.unlink(missing_ok=True)
            raise
        self.send_json({"upload_id": upload_id, "name": name, "size": length}, 201)

    def log_message(self, fmt, *args):
        if "/api/jobs" in self.path or "/api/media" in self.path:
            return  # polling and range requests would flood the console
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    for d in (UPLOAD_DIR, FRAMES_DIR):
        d.mkdir(parents=True, exist_ok=True)
    cleanup_scratch()
    try:
        output_root().mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"WARNING: output folder unavailable ({e}). Jobs will fail until the output drive is mounted.")
    src = input_root()
    no_src = 'NOT FOUND (no Drive mount contains a "colon cancer" folder)'
    print(f"Input  : {src or no_src}")
    print(f"Output : {output_root()}")
    print(f"Mounts : {', '.join(map(str, drive_mounts())) or 'none detected'}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print(f"Backend listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for job in list(JOBS.values()):
            job.cancel.set()
            if job.proc and job.proc.poll() is None:
                job.proc.terminate()
        kaggle_disconnect()
        server.server_close()


if __name__ == "__main__":
    main()
