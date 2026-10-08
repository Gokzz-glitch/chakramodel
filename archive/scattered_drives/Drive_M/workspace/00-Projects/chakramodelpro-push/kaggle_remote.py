"""Run the YOLO video job on a Kaggle GPU session through its Jupyter-server link.

The link looks like  https://<host>.kaggle.net/k/<id>/<token>/proxy  and is a normal
Jupyter server whose access token is embedded in the URL. Everything here uses only the
standard Jupyter REST + WebSocket API (no extension needed on the Kaggle side):

    contents API  -> upload the video / download the annotated result
    kernel API    -> run pip, fetch weights, run video_infer.py and stream its output

SECURITY: the link grants code execution on your Kaggle session. It is held in memory
only, is never written to disk, and is stripped from every error message.
"""
import base64
import hashlib
import json
import os
import re
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

# Folder "models" inside the shared Drive project folder (see README). Override with the env var.
DEFAULT_MODELS_FOLDER = os.environ.get("POLYP_DRIVE_MODELS_FOLDER", "1gj1Rzy1yMGFb1dFQb1OVz1K6W0yCzfqD")
REMOTE_DIR = "polyp_remote"
UP_CHUNK = 4 << 20
KERNEL_CHUNK = 512 << 10        # kernel-path upload block (input to the kernel, no rate limit)
KERNEL_DL_CHUNK = 192 << 10     # kernel-path download block (base64 stays well under 1 MB/s)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
EXIT_RE = re.compile(r"__EXIT_CODE__=(-?\d+)")
PIP_NAMES = {"ultralytics": "ultralytics", "gdown": "gdown", "imageio_ffmpeg": "imageio-ffmpeg"}


class RemoteError(RuntimeError):
    pass


class RemoteCancelled(Exception):
    pass


def _deps():
    try:
        import requests
        import websocket
    except ImportError:
        raise RemoteError("Kaggle mode needs two small packages: pip install requests websocket-client")
    return requests, websocket


_sha_cache = {}


def sha256_file(path):
    path = Path(path)
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key not in _sha_cache:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        _sha_cache[key] = h.hexdigest()
    return _sha_cache[key]


# --------------------------------------------------------------------------- Jupyter client
class Jupyter:
    def __init__(self, url):
        requests, _ = _deps()
        u = urlparse(url.strip())
        host = (u.hostname or "").lower()
        insecure_ok = os.environ.get("POLYP_ALLOW_INSECURE_JUPYTER") == "1"   # local testing only
        if u.scheme != "https" and not (insecure_ok and u.scheme == "http"):
            raise RemoteError("The Kaggle link must start with https://")
        if not insecure_ok and not (host == "kaggle.net" or host.endswith(".kaggle.net")):
            raise RemoteError("Only *.kaggle.net links are accepted.")
        self.origin = f"{u.scheme}://{u.netloc}"
        self.base = u.path.rstrip("/")
        self.token = (parse_qs(u.query).get("token") or [None])[0]
        self.host = host
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "PolypEval/2"
        if self.token:
            self.s.headers["Authorization"] = "token " + self.token
        self.session_id = uuid.uuid4().hex
        self._secrets = [x for x in (self.base, self.token) if x and len(x) > 6]

    # -- helpers
    def scrub(self, text):
        text = str(text)
        for secret in self._secrets:
            text = text.replace(secret, "<hidden>")
        return text

    def url(self, path):
        return f"{self.origin}{self.base}{path}"

    def req(self, method, path, retries=3, **kw):
        kw.setdefault("timeout", 120)
        headers = kw.pop("headers", {})
        last = None
        for attempt in range(retries):
            xsrf = self.s.cookies.get("_xsrf")
            if xsrf:
                headers = dict(headers, **{"X-XSRFToken": xsrf})
            try:
                r = self.s.request(method, self.url(path), headers=headers, **kw)
            except Exception as e:  # noqa: BLE001 - network errors are retried
                last = self.scrub(e)
                time.sleep(1.5 * (attempt + 1))
                continue
            if r.status_code in (502, 503, 504) and attempt < retries - 1:
                last = f"HTTP {r.status_code}"
                time.sleep(1.5 * (attempt + 1))
                continue
            return r
        raise RemoteError(f"{method} {self.scrub(path)} failed: {last}")

    def check(self, r, what):
        if r.status_code >= 400:
            raise RemoteError(f"{what} failed: HTTP {r.status_code} {self.scrub(r.text[:200])}")
        return r

    def probe(self):
        """Find the Jupyter API root. The link usually ends in /proxy; try it, then its parent."""
        original, tried = self.base, []
        for cand in dict.fromkeys([original, re.sub(r"/proxy$", "", original)]):
            self.base = cand
            r = self.req("GET", "/api/status", retries=2)
            tried.append(r.status_code)
            if r.status_code == 200 and "json" in r.headers.get("Content-Type", ""):
                self._get_xsrf()
                return r.json()
        self.base = original
        raise RemoteError(f"Could not reach a Jupyter server at that link (HTTP {tried}). "
                          "The Kaggle session may have ended or the link has expired - copy a fresh one.")

    def _get_xsrf(self):
        """Jupyter only issues its _xsrf cookie on HTML pages; writes (PUT/POST) are rejected without it."""
        for page in ("/", "/lab", "/tree", "/login"):
            if self.s.cookies.get("_xsrf"):
                return
            try:
                self.s.get(self.url(page), timeout=30)
            except Exception:  # noqa: BLE001 - best effort; some servers disable the check
                pass

    # -- contents API
    @staticmethod
    def cpath(rel):
        return "/api/contents/" + "/".join(quote(p) for p in rel.strip("/").split("/"))

    def mkdir(self, rel):
        built = ""
        for part in rel.strip("/").split("/"):
            built = f"{built}/{part}".strip("/")
            self.check(self.req("PUT", self.cpath(built), json={"type": "directory"}), f"mkdir {built}")

    def size(self, rel):
        r = self.req("GET", self.cpath(rel), params={"content": 0})
        return r.json().get("size") if r.status_code == 200 else None

    def delete(self, rel):
        self.req("DELETE", self.cpath(rel), retries=1)

    def put_text(self, rel, text):
        self.check(self.req("PUT", self.cpath(rel), json={"type": "file", "format": "text", "content": text}), f"upload {rel}")

    # -- kernels
    def start_kernel(self):
        spec = self.check(self.req("GET", "/api/kernelspecs"), "kernelspecs").json()
        r = self.check(self.req("POST", "/api/kernels", json={"name": spec.get("default", "python3")}), "start kernel")
        return r.json()["id"]

    def stop_kernel(self, kid):
        try:
            self.req("DELETE", f"/api/kernels/{kid}", retries=1)
        except RemoteError:
            pass

    def interrupt(self, kid):
        try:
            self.req("POST", f"/api/kernels/{kid}/interrupt", retries=1)
        except RemoteError:
            pass

    def _ws(self, kid):
        _, websocket = _deps()
        scheme = "wss" if self.origin.startswith("https") else "ws"
        url = f"{scheme}://{self.origin.split('://', 1)[1]}{self.base}/api/kernels/{kid}/channels?session_id={self.session_id}"
        if self.token:
            url += "&token=" + quote(self.token)
        headers = ["Cookie: " + "; ".join(f"{c.name}={c.value}" for c in self.s.cookies)] if self.s.cookies else []
        if self.token:
            headers.append("Authorization: token " + self.token)
        try:
            return websocket.create_connection(url, timeout=20, origin=self.origin, header=headers, enable_multithread=True)
        except Exception as e:  # noqa: BLE001
            raise RemoteError("WebSocket connection to the Kaggle kernel failed: " + self.scrub(e))

    def exec(self, kid, code, on_text=None, cancel=None, timeout=None):
        """Execute code in the kernel, stream stdout/stderr to on_text, return all text.
        timeout (seconds) guards short calls: Jupyter silently drops output above its iopub rate
        limit (default 1 MB/s), which would otherwise leave us waiting forever."""
        _, websocket = _deps()
        deadline = time.monotonic() + timeout if timeout else None
        ws = self._ws(kid)
        msg_id = uuid.uuid4().hex
        ws.send(json.dumps({
            "header": {"msg_id": msg_id, "username": "polyp", "session": self.session_id, "msg_type": "execute_request",
                       "version": "5.3", "date": datetime.now(timezone.utc).isoformat()},
            "parent_header": {}, "metadata": {}, "buffers": [], "channel": "shell",
            "content": {"code": code, "silent": False, "store_history": False, "user_expressions": {},
                        "allow_stdin": False, "stop_on_error": True}}))
        ws.settimeout(1.0)
        out, error, interrupted, last_ping, got_reply, idle = [], None, False, time.monotonic(), False, False
        try:
            while True:
                if cancel is not None and cancel.is_set() and not interrupted:
                    interrupted = True
                    self.interrupt(kid)
                if deadline and time.monotonic() > deadline:
                    self.interrupt(kid)
                    raise RemoteError("Timed out waiting for Kaggle (output may have hit Jupyter's rate limit).")
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    if time.monotonic() - last_ping > 20:   # keep proxies from dropping a quiet connection
                        try:
                            ws.ping()
                        except Exception:  # noqa: BLE001
                            pass
                        last_ping = time.monotonic()
                    continue
                except websocket.WebSocketConnectionClosedException:
                    raise RemoteError("Connection to Kaggle was lost. The remote job may still be running.")
                if not raw:
                    continue
                m = json.loads(raw)
                if m.get("parent_header", {}).get("msg_id") != msg_id:
                    continue
                kind, c = m["header"]["msg_type"], m.get("content", {})
                if kind == "stream":
                    out.append(c["text"])
                    if on_text:
                        on_text(c["text"])
                elif kind == "error":
                    error = ANSI.sub("", f"{c.get('ename', 'Error')}: {c.get('evalue', '')}")[:500]   # not the traceback: it echoes our code
                elif kind == "execute_reply":
                    got_reply = True
                elif kind == "status" and c.get("execution_state") == "idle":
                    idle = True
                if got_reply and idle:   # the two arrive on different channels, in either order
                    break
        finally:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass
        if interrupted:
            raise RemoteCancelled()
        if error and "KeyboardInterrupt" not in error:
            raise RemoteError(self.scrub(error[-1500:]))
        return "".join(out)


# --------------------------------------------------------------------------- session
RUN_TEMPLATE = '''
import os, subprocess, sys
_cmd = [sys.executable if c == "__PY__" else c for c in {cmd!r}]
_p = subprocess.Popen(_cmd, cwd={cwd!r}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                      env=dict(os.environ, PYTHONUNBUFFERED="1"))
try:
    for _l in _p.stdout:
        print(_l, end="", flush=True)
    _p.wait()
except BaseException:
    _p.terminate()
    raise
print("\\n__EXIT_CODE__=%d" % _p.returncode, flush=True)
'''


class KaggleSession:
    def __init__(self, url, project_root, models_folder=DEFAULT_MODELS_FOLDER):
        self.j = Jupyter(url)
        self.project_root = Path(project_root)
        self.models_folder = models_folder
        self.state, self.step, self.error, self.gpu = "connecting", "", None, None
        self.log = deque(maxlen=120)
        self.kernel, self.abs = None, None
        self.ready = threading.Event()
        self._exec_lock = threading.Lock()

    # -- status
    def public(self):
        return {"state": self.state, "step": self.step, "error": self.error, "gpu": self.gpu,
                "host": self.j.host, "log": list(self.log)[-12:]}

    def _note(self, text):
        self.step = text
        self.log.append(text)

    def _exec(self, code, on_text=None, cancel=None, timeout=None):
        with self._exec_lock:
            return self.j.exec(self.kernel, code, on_text, cancel, timeout)

    # -- lifecycle
    def connect(self):
        """Fast, synchronous part: reach the server, find the working dir, start a kernel."""
        self.j.probe()
        self.j.mkdir(REMOTE_DIR)
        self.kernel = self.j.start_kernel()
        probe_name = f"probe_{uuid.uuid4().hex[:8]}.txt"
        self.j.put_text(f"{REMOTE_DIR}/{probe_name}", "x")
        try:
            found = self._exec(
                "import os\n"
                f"for c in (os.getcwd(), '/kaggle/working', '/kaggle', os.path.expanduser('~'), '/'):\n"
                f"    if os.path.exists(os.path.join(c, {REMOTE_DIR!r}, {probe_name!r})):\n"
                "        print('ROOT=' + c); break\n").strip()
        finally:
            self.j.delete(f"{REMOTE_DIR}/{probe_name}")
        if not found.startswith("ROOT="):
            raise RemoteError("Could not map the Jupyter file tree to the kernel's filesystem.")
        self.abs = found[5:].rstrip("/") + "/" + REMOTE_DIR
        self.gpu = self._exec(
            "import subprocess\n"
            "try:\n"
            "    r = subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader'], capture_output=True, text=True)\n"
            "    print(r.stdout.strip() or 'no GPU')\n"
            "except Exception:\n"
            "    print('no GPU')\n").strip()
        self.state = "preparing"
        self._note("connected" + ("" if self.gpu != "no GPU" else " (WARNING: this session has no GPU)"))
        threading.Thread(target=self._prepare, daemon=True).start()

    def close(self):
        if self.kernel:
            self.j.stop_kernel(self.kernel)
        self.state, self.kernel = "disconnected", None

    def _prepare(self):
        try:
            self._note("checking Python packages on Kaggle")
            missing = self._exec("import importlib.util as u\n"
                                 f"print('MISSING=' + ','.join(m for m in {list(PIP_NAMES)!r} if u.find_spec(m) is None))").strip()
            missing = [m for m in missing.removeprefix("MISSING=").split(",") if m]
            if missing:
                self._note("installing " + ", ".join(missing) + " (needs Internet ON in the Kaggle notebook)")
                code = self.run(["__PY__", "-m", "pip", "install", "--disable-pip-version-check"] + [PIP_NAMES[m] for m in missing],
                                on_line=lambda l: l.startswith(("Collecting", "Successfully", "ERROR")) and self.log.append(l[:120]))
                if code != 0:
                    raise RemoteError("pip install failed on Kaggle - make sure Internet is enabled in the notebook settings.")
            self._note("uploading video_infer.py")
            self.j.put_text(f"{REMOTE_DIR}/video_infer.py", (self.project_root / "video_infer.py").read_text("utf-8"))
            self.state = "ready"
            self._note("ready")
            self.ready.set()
        except Exception as e:  # noqa: BLE001
            self.state, self.error = "error", self.j.scrub(e)
            self.log.append("ERROR: " + self.error)

    def wait_ready(self, cancel=None, timeout=1200):
        end = time.monotonic() + timeout
        while not self.ready.wait(1.0):
            if cancel is not None and cancel.is_set():
                raise RemoteCancelled()
            if self.state == "error":
                raise RemoteError("Kaggle session is not ready: " + (self.error or "unknown error"))
            if self.state == "disconnected" or time.monotonic() > end:
                raise RemoteError("Kaggle session is not ready (disconnected or timed out).")

    # -- commands and files
    def run(self, cmd, on_line=None, cancel=None):
        buf = ""
        code_holder = {"code": None}

        def feed(text):
            nonlocal buf
            buf += text.replace("\r", "\n")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                m = EXIT_RE.search(line)
                if m:
                    code_holder["code"] = int(m.group(1))
                elif line.strip() and on_line:
                    on_line(line.rstrip())

        self._exec(RUN_TEMPLATE.format(cmd=list(cmd), cwd=self.abs), feed, cancel)
        if buf.strip():
            feed("\n")
        return code_holder["code"] if code_holder["code"] is not None else 1

    def remote_size(self, rel):
        return int(self._exec(f"import os\np = {self.abs + '/' + rel!r}\nprint(os.path.getsize(p) if os.path.isfile(p) else -1)", timeout=60).strip())

    def remote_sha256(self, rel):
        return self._exec("import hashlib\nh = hashlib.sha256()\n"
                          f"with open({self.abs + '/' + rel!r}, 'rb') as f:\n"
                          "    for b in iter(lambda: f.read(1 << 20), b''): h.update(b)\n"
                          "print(h.hexdigest())", timeout=600).strip()

    def remove(self, *rels):
        for rel in rels:
            try:
                self.j.delete(f"{REMOTE_DIR}/{rel}")
            except RemoteError:
                pass

    def upload(self, local, rel, progress=None, cancel=None):
        local, total = Path(local), Path(local).stat().st_size
        self.j.mkdir(f"{REMOTE_DIR}/{rel.rsplit('/', 1)[0]}") if "/" in rel else None
        cpath = f"{REMOTE_DIR}/{rel}"
        try:
            sent, idx = 0, 0
            with open(local, "rb") as f:
                while True:
                    block = f.read(UP_CHUNK)
                    if not block and idx:
                        break
                    if cancel is not None and cancel.is_set():
                        raise RemoteCancelled()
                    idx += 1
                    last = f.tell() >= total
                    body = {"type": "file", "format": "base64", "content": base64.b64encode(block).decode()}
                    if total > UP_CHUNK:
                        body["chunk"] = -1 if (last and idx > 1) else idx
                    self.j.check(self.j.req("PUT", self.j.cpath(cpath), json=body), "upload")
                    sent += len(block)
                    if progress:
                        progress(sent, total)
                    if last:
                        break
            if self.j.size(cpath) != total:
                raise RemoteError("size mismatch after upload")
        except RemoteCancelled:
            raise
        except RemoteError:   # server without chunk support, or proxy limit: slower but universal path
            self._upload_via_kernel(local, rel, progress, cancel)

    def _upload_via_kernel(self, local, rel, progress, cancel):
        total, sent, first = Path(local).stat().st_size, 0, True
        dest = f"{self.abs}/{rel}"
        with open(local, "rb") as f:
            while True:
                block = f.read(KERNEL_CHUNK)
                if not block and not first:
                    break
                if cancel is not None and cancel.is_set():
                    raise RemoteCancelled()
                self._exec("import base64, os\n"
                           f"p = {dest!r}\nos.makedirs(os.path.dirname(p), exist_ok=True)\n"
                           f"with open(p, {('wb' if first else 'ab')!r}) as f:\n    f.write(base64.b64decode({base64.b64encode(block).decode()!r}))\n", timeout=120)
                first, sent = False, sent + len(block)
                if progress:
                    progress(sent, total)
                if not block:
                    break
        if self.remote_size(rel) != total:
            raise RemoteError("Upload to Kaggle failed (size mismatch).")

    def download(self, rel, local, progress=None, cancel=None):
        local = Path(local)
        local.parent.mkdir(parents=True, exist_ok=True)
        part = local.with_suffix(local.suffix + ".part")
        total = self.remote_size(rel)
        if total < 0:
            raise RemoteError(f"Result file not found on Kaggle: {rel}")
        try:
            r = self.j.req("GET", "/files/" + "/".join(quote(p) for p in f"{REMOTE_DIR}/{rel}".split("/")), stream=True)
            if r.status_code != 200:
                raise RemoteError("no /files endpoint")
            done = 0
            with open(part, "wb") as f:
                for block in r.iter_content(1 << 20):
                    if cancel is not None and cancel.is_set():
                        raise RemoteCancelled()
                    f.write(block)
                    done += len(block)
                    if progress:
                        progress(done, total)
            if done != total:
                raise RemoteError("size mismatch")
        except RemoteCancelled:
            part.unlink(missing_ok=True)
            raise
        except RemoteError:
            self._download_via_kernel(rel, part, total, progress, cancel)
        part.replace(local)

    def _download_via_kernel(self, rel, part, total, progress, cancel):
        src, done = f"{self.abs}/{rel}", 0
        with open(part, "wb") as f:
            while done < total:
                if cancel is not None and cancel.is_set():
                    raise RemoteCancelled()
                started = time.monotonic()
                text = self._exec(f"import base64\nwith open({src!r}, 'rb') as f:\n    f.seek({done})\n"
                                  f"    print('B64:' + base64.b64encode(f.read({KERNEL_DL_CHUNK})).decode())", timeout=60)
                if not text.strip().startswith("B64:"):
                    raise RemoteError("Download from Kaggle failed (no data received).")
                data = base64.b64decode(text.strip()[4:])
                if not data:
                    break
                time.sleep(max(0.0, 0.7 - (time.monotonic() - started)))   # stay under Jupyter's 1 MB/s iopub limit
                f.write(data)
                done += len(data)
                if progress:
                    progress(done, total)
        if done != total:
            raise RemoteError("Download from Kaggle failed (size mismatch).")

    # -- model weights
    def ensure_weights(self, key, local_weights, progress=None, cancel=None):
        """Weights on Kaggle: reuse -> pull from the shared Drive folder -> upload from this PC.
        If the local copy exists, every route is verified against its SHA-256."""
        local = Path(local_weights) if local_weights and Path(local_weights).is_file() else None
        name = Path(local_weights).name if local_weights else "weights.pt"
        rel = f"models/{key}/{name}"
        want = sha256_file(local) if local else None
        if self.remote_size(rel) > 0 and (want is None or self.remote_sha256(rel) == want):
            self._note(f"weights for {key} already on Kaggle")
            return
        self._note(f"fetching {key} weights from Google Drive")
        try:
            self._exec(
                "import gdown, os\n"
                f"files = gdown.download_folder(id={self.models_folder!r}, skip_download=True, quiet=True, use_cookies=False)\n"
                f"hit = [f for f in files if str(f.path).replace(chr(92), '/').endswith({key + '/' + name!r})]\n"
                "assert hit, 'weights not found in the Drive folder'\n"
                f"dest = {self.abs + '/' + rel!r}\nos.makedirs(os.path.dirname(dest), exist_ok=True)\n"
                "gdown.download(id=hit[0].id, output=dest, quiet=True)\n", cancel=cancel)
            if self.remote_size(rel) <= 0:
                raise RemoteError("empty download")
            if want is None:
                self._note("WARNING: no local copy to verify the Drive weights against")
                return
            if self.remote_sha256(rel) == want:
                return
            self.log.append("Drive copy failed the integrity check; replacing it with your local file")
        except RemoteCancelled:
            raise
        except Exception as e:  # noqa: BLE001
            self.log.append("Drive download failed (" + self.j.scrub(e)[:120] + ")")
        if local is None:
            raise RemoteError(f"No usable weights for {key}: not on Drive and no local file to upload.")
        self._note(f"uploading {key} weights from this PC")
        self.upload(local, rel, progress, cancel)
        if self.remote_sha256(rel) != want:
            raise RemoteError("Uploaded weights failed the integrity check.")

    def infer(self, key, weights_name, rel_in, rel_out, device, threshold, on_line, cancel):
        cmd = ["__PY__", "video_infer.py", "--weights", f"models/{key}/{weights_name}", "--source", rel_in,
               "--output", rel_out, "--device", device, "--threshold", str(threshold)]
        if device != "cpu":
            cmd.append("--strict-device")   # never fall back to the CPU silently
        return self.run(cmd, on_line, cancel)
