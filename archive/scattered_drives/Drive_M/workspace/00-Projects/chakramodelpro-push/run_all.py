#!/usr/bin/env python3
"""One command to run everything.

    python run_all.py                  check the setup, start the backend, open the UI
    python run_all.py --kaggle         ... and also connect a Kaggle GPU session (asks for the link).
                                       Remote-only: inference runs ONLY on the Kaggle GPU, never on this PC.
    python run_all.py --gradio         ... and also open a Gradio results viewer for the output folder
    python run_all.py --check          only check the setup and print a report
    python run_all.py --install        install missing Python packages without asking

What it does, in order
  1. Verifies Python and the project files (backend.py, video_infer.py, kaggle_remote.py, ui/index.html).
  2. Unpacks model_packages/*.zip into models/ for any model whose files are missing (never overwrites).
  3. Reports packages, GPU, drives (input I:, output J:) and each model's readiness.
  4. Starts backend.py, waits until it answers, optionally connects Kaggle, opens the browser.
Every finished video is written to the output root (J:), see "output_root" in config.json.
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REQUIRED_FILES = ["backend.py", "video_infer.py", "kaggle_remote.py", "ui/index.html"]
# module -> (pip name, why)
PACKAGES = {
    "cv2": ("opencv-python", "video reading/writing (required)"),
    "ultralytics": ("ultralytics", "YOLO models (required for local YOLO runs; installs PyTorch)"),
    "imageio_ffmpeg": ("imageio-ffmpeg", "H.264 output that plays in browsers and uploads to YouTube"),
    "requests": ("requests", "Kaggle GPU mode"),
    "websocket": ("websocket-client", "Kaggle GPU mode"),
    "yt_dlp": ("yt-dlp", "optional: YouTube/Vimeo URLs"),
    "gradio": ("gradio", "optional: Gradio results viewer"),
}


def say(msg=""):
    print(msg, flush=True)


def has(mod):
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


# --------------------------------------------------------------------------- preflight
def check_files():
    missing = [f for f in REQUIRED_FILES if not (HERE / f).is_file()]
    if missing:
        say("ERROR: missing project files: " + ", ".join(missing))
        say("       Copy them next to run_all.py (they live in the 'valid models' folder).")
        sys.exit(1)


def unpack_models():
    """Extract manifests/evaluators from model_packages/ where models/ lacks them. Never overwrites."""
    pkg_dir, restored = HERE / "model_packages", 0
    archives = [pkg_dir / "all_model_sources.zip"] if (pkg_dir / "all_model_sources.zip").is_file() else sorted(pkg_dir.glob("*_source.zip"))
    for archive in archives:
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                dest = (HERE / info.filename).resolve()
                if HERE not in dest.parents:       # zip-slip guard
                    continue
                if not dest.exists():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(z.read(info))
                    restored += 1
    if restored:
        say(f"Restored {restored} missing file(s) from model_packages/ (weights are never in those archives).")


def pip_install(names):
    say("Installing: " + ", ".join(names))
    return subprocess.call([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", *names]) == 0


def check_packages(args):
    need_kaggle = args.kaggle is not None
    required = (["requests", "websocket"] if need_kaggle else ["cv2", "ultralytics"]) + (["gradio"] if args.gradio else [])
    recommended = ["imageio_ffmpeg"]
    say("Python packages")
    missing_required = []
    for mod, (pip_name, why) in PACKAGES.items():
        ok = has(mod)
        tag = "ok " if ok else ("MISSING" if mod in required else "absent")
        say(f"  [{tag:^7}] {pip_name:<16} {why}")
        if not ok and mod in required + recommended and mod not in missing_required:
            missing_required.append(mod)
    if missing_required and not args.check:
        names = [PACKAGES[m][0] for m in missing_required]
        do = args.install or (sys.stdin.isatty() and input(f"\nInstall {', '.join(names)} now? [y/N] ").strip().lower() == "y")
        if do and pip_install(names):
            importlib.invalidate_caches()
        elif any(m in required for m in missing_required):
            say("Some required packages are still missing; those features will report an error until installed.")
    # GPU: a CPU-only PyTorch is the usual reason 'CUDA does not work' on Windows
    if has("torch") and os.environ.get("POLYP_REMOTE_ONLY") != "1":
        try:
            out = subprocess.run([sys.executable, "-c", "import torch;print(torch.__version__, torch.cuda.is_available())"],
                                 capture_output=True, text=True, timeout=120).stdout.strip()
        except subprocess.TimeoutExpired:
            out = ""
        say(f"\nPyTorch: {out or 'could not be imported'}")
        if out.endswith("False") and shutil.which("nvidia-smi"):
            say("  NVIDIA GPU found but this PyTorch is CPU-only. Install a CUDA build, e.g.:")
            say("  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121")


def report_environment():
    import backend
    say("\nDrives")
    mounts = backend.drive_mounts()
    say("  Google Drive mounts : " + (", ".join(map(str, mounts)) or "none detected"))
    src, out = backend.input_root(), backend.output_root()
    no_src = 'NOT FOUND - no mounted Drive has a "colon cancer" folder'
    say(f"  Input  (dataset)    : {src or no_src}")
    try:
        out.mkdir(parents=True, exist_ok=True)
        say(f"  Output (videos)     : {out}   [{backend.free_gb(out)} GB free]")
    except OSError as e:
        say(f"  Output (videos)     : {out}   NOT WRITABLE ({e})")
    if backend.REMOTE_ONLY:
        say("\nMode: REMOTE-ONLY - inference runs on the Kaggle GPU; this PC's CPU/GPU is never used.")
    say("\nModels")
    for m in (backend.public_model(x) for x in backend.load_models().values()):
        say(f"  [{'ready' if m['ready'] else 'unavailable' if backend.REMOTE_ONLY else 'setup needed':^12}] {m['label']}")
        for issue in m["issues"]:
            say(f"                   - {issue}")


# --------------------------------------------------------------------------- runtime
def port_in_use(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def get_json(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def post_json(url, payload, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(json.loads(e.read() or b"{}").get("error", f"HTTP {e.code}"))


def start_backend(port, remote_only=False):
    if port_in_use(port):
        try:
            state = get_json(f"http://127.0.0.1:{port}/api/state")
            if "models" in state and (not remote_only or state.get("remote_only")):
                say(f"\nBackend already running on port {port}; reusing it.")
                return None, port
            if "models" in state:
                say(f"\nA backend on port {port} is not in remote-only mode (it could run on this PC); starting a new one.")
        except Exception:  # noqa: BLE001
            pass
        free = next((p for p in range(port + 1, port + 30) if not port_in_use(p)), None)
        if free is None:
            say(f"ERROR: port {port} is in use and no free port found nearby.")
            sys.exit(1)
        say(f"\nPort {port} is busy (another program); using {free} instead.")
        port = free
    # The Kaggle link must never reach child processes through the environment.
    env = {k: v for k, v in os.environ.items() if k != "KAGGLE_JUPYTER_URL"}
    env["PORT"] = str(port)
    proc = subprocess.Popen([sys.executable, str(HERE / "backend.py")], cwd=HERE, env=env)
    for _ in range(60):
        if proc.poll() is not None:
            say("ERROR: the backend exited during startup (see the message above).")
            sys.exit(1)
        try:
            get_json(f"http://127.0.0.1:{port}/api/state", timeout=1)
            return proc, port
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    proc.terminate()
    say("ERROR: the backend did not become ready within 30 seconds.")
    sys.exit(1)


KAGGLE_LINK = re.compile(r"https://[A-Za-z0-9.-]+\.kaggle\.net/\S+")


def read_clipboard():
    """Text on the clipboard, or ''. Used so the link can be taken without typing or pasting into a console."""
    cmds = []
    if os.name == "nt":
        cmds.append(["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-Clipboard -Raw"])
    elif sys.platform == "darwin":
        cmds.append(["pbpaste"])
    else:
        cmds += [["wl-paste", "-n"], ["xclip", "-selection", "clipboard", "-o"]]
    for cmd in cmds:
        if not shutil.which(cmd[0]):
            continue
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        if out and out.strip():
            return out.strip()
    return ""


def link_host(url):
    return re.sub(r"^https://([^/]+)/.*$", r"\1", url)


def ask_kaggle_link():
    """Returns the Kaggle link, or '' to skip (then paste it in the web UI). Input is VISIBLE so typing and
    pasting work in cmd (Ctrl+V or right-click). The line is erased from the screen afterwards."""
    say("\nKaggle link: Kaggle notebook > Run > 'Connect to VS Code / Jupyter server' > copy the URL.")
    clip = KAGGLE_LINK.search(read_clipboard())
    if clip:
        host = link_host(clip.group(0))
        try:
            ans = input(f"A Kaggle link is on your clipboard ({host}/...). Use it? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return ""
        if ans in ("", "y", "yes"):
            return clip.group(0)
    say("Paste the link below (Ctrl+V or right-click in cmd) and press Enter.")
    say("Or just press Enter to skip, then paste it into the 'Kaggle GPU' card in the web page.")
    for _ in range(3):
        try:
            line = input("Kaggle link> ").strip().strip("\"'")
        except (EOFError, KeyboardInterrupt):
            say("")
            return ""
        if sys.stdout.isatty() and os.name != "nt":
            sys.stdout.write("\x1b[1A\x1b[2K")        # erase the echoed token (best effort)
        if not line:
            return ""
        m = KAGGLE_LINK.search(line)
        if m:
            return m.group(0)
        say("  That is not a Kaggle link (expected https://<host>.kaggle.net/k/<id>/<token>/proxy). Try again.")
    return ""


def connect_kaggle(base, url):
    say("\nConnecting to Kaggle ...")
    try:
        status = post_json(f"{base}/api/kaggle/connect", {"url": url})
    except RuntimeError as e:
        say(f"  Kaggle connection failed: {e}")
        return False
    say(f"  Connected. GPU: {status.get('gpu')}")
    last = ""
    for _ in range(900):                      # up to ~15 min for the first pip install
        status = get_json(f"{base}/api/kaggle")
        if status["step"] != last:
            last = status["step"]
            say(f"  {last}")
        if status["state"] == "ready":
            say("  Kaggle session is ready.")
            return True
        if status["state"] == "error":
            say(f"  Kaggle preparation failed: {status.get('error')}")
            return False
        time.sleep(1)
    return False


def serve_gradio(base, port, share):
    """Small results viewer: lists the finished videos in the output folder and plays them."""
    import gradio as gr
    out_root = Path(get_json(f"{base}/api/state")["output"]["root"])

    def videos():
        files = sorted(out_root.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)[:300] if out_root.is_dir() else []
        return [(f"{p.relative_to(out_root)}  ({p.stat().st_size >> 20} MB)", str(p)) for p in files]

    def refresh():
        choices = videos()
        return gr.update(choices=choices, value=choices[0][1] if choices else None)

    with gr.Blocks(title="Polyp results") as demo:
        gr.Markdown(f"### Annotated videos in `{out_root}`")
        pick = gr.Dropdown(choices=videos(), label="Video", value=(videos() or [(None, None)])[0][1])
        player = gr.Video(label="Result", interactive=False)
        path_box = gr.Textbox(label="File path (use this for YouTube upload / ffmpeg live)", interactive=False)
        gr.Button("Refresh list").click(refresh, outputs=pick)
        pick.change(lambda p: (p, p), pick, [player, path_box])
        demo.load(lambda p: (p, p), pick, [player, path_box])
    demo.launch(server_name="127.0.0.1", server_port=port, allowed_paths=[str(out_root)], share=share,
                prevent_thread_lock=True, inbrowser=False, quiet=True)
    return f"http://127.0.0.1:{port}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--check", action="store_true", help="only report the setup, do not start anything")
    ap.add_argument("--install", action="store_true", help="install missing packages without asking")
    ap.add_argument("--kaggle", nargs="?", const="", default=None, metavar="URL",
                    help="connect a Kaggle session and run ONLY on its GPU; without a value the link is read from KAGGLE_JUPYTER_URL, the clipboard, or typed")
    ap.add_argument("--allow-local", action="store_true",
                    help="with --kaggle: still allow runs on this PC (default: Kaggle GPU only)")
    ap.add_argument("--gradio", action="store_true", help="also serve a Gradio results viewer")
    ap.add_argument("--gradio-port", type=int, default=7860)
    ap.add_argument("--share", action="store_true", help="make the Gradio viewer public via gradio.live (anyone with the link can watch)")
    args = ap.parse_args()

    if sys.version_info < (3, 9):
        say("ERROR: Python 3.9 or newer is required.")
        sys.exit(1)
    remote_only = args.kaggle is not None and not args.allow_local
    if remote_only:
        os.environ["POLYP_REMOTE_ONLY"] = "1"          # backend refuses to run anything on this PC
    elif args.allow_local:
        os.environ.pop("POLYP_REMOTE_ONLY", None)
    say(f"Polyp evaluation launcher - Python {sys.version.split()[0]} - {HERE}\n")
    check_files()
    unpack_models()
    check_packages(args)
    report_environment()
    if args.check:
        return

    url = None
    if args.kaggle is not None:
        url = args.kaggle or os.environ.get("KAGGLE_JUPYTER_URL") or ask_kaggle_link()
        os.environ.pop("KAGGLE_JUPYTER_URL", None)

    if remote_only and not url:
        say("\nNo link entered: the backend starts in remote-only mode. Paste the link into the web page's Kaggle card; "
            "nothing will run until a Kaggle GPU session is connected.")
    proc, port = start_backend(args.port, remote_only)
    base = f"http://127.0.0.1:{port}"
    try:
        if url:
            connect_kaggle(base, url)
            url = None
        ui = base + "/"
        say(f"\nUI              : {ui}")
        if args.gradio:
            try:
                say(f"Gradio viewer   : {serve_gradio(base, args.gradio_port, args.share)}")
            except ImportError:
                say("Gradio is not installed: pip install gradio")
        say("Press Ctrl+C to stop.\n")
        if not args.no_browser:
            webbrowser.open(ui)
        while proc is None or proc.poll() is None:
            time.sleep(1)
        say("The backend stopped.")
    except KeyboardInterrupt:
        say("\nStopping ...")
    finally:
        try:
            post_json(f"{base}/api/kaggle/disconnect", {}, timeout=10)   # close the remote kernel politely
        except Exception:  # noqa: BLE001
            pass
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
