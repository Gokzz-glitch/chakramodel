"""
registry.py — the password-protected list of projects/datasets/scripts.

WHY PASSWORD-PROTECTED:
An agent that only has access to a PROJECT folder (e.g. M:\\chakramodel)
cannot reach this toolkit at all, since it lives outside any project
folder (C:\\Users\\<you>\\ANTI_FABRICATION\\...). That folder boundary is
your FIRST and strongest protection.

The password is a SECOND layer, for cases where an agent has broader
file access than expected (e.g. a full computer-use agent, or you
running commands inside this folder yourself by mistake while an agent
session is active). Registering or editing a project requires the
password. RUNNING an existing, already-registered check does not
require the password every time — but it does verify the registry
file's signature first, and refuses to run against a tampered registry.
"""

import os
import json
import hmac
import hashlib
import getpass
import secrets

TOOLKIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(TOOLKIT_ROOT, "config")
REGISTRY_PATH = os.path.join(CONFIG_DIR, "projects.json")
KEYFILE_PATH = os.path.join(CONFIG_DIR, "master.key")  # never share/copy this out of this folder
SALT_PATH = os.path.join(CONFIG_DIR, "master.salt")
LOCKOUT_PATH = os.path.join(CONFIG_DIR, "lockout.json")

MAX_ATTEMPTS = 5
LOCKOUT_SECONDS = 15 * 60  # 15 minutes


def _check_lockout():
    import time
    if not os.path.exists(LOCKOUT_PATH):
        return
    with open(LOCKOUT_PATH) as f:
        state = json.load(f)
    if state.get("failures", 0) >= MAX_ATTEMPTS:
        elapsed = time.time() - state.get("last_failure_epoch", 0)
        if elapsed < LOCKOUT_SECONDS:
            remaining = int((LOCKOUT_SECONDS - elapsed) / 60) + 1
            print(f"[REGISTRY] LOCKED OUT after {MAX_ATTEMPTS} failed password attempts. "
                  f"Try again in ~{remaining} minute(s).")
            raise SystemExit(1)
        else:
            _reset_lockout()


def _record_failure():
    import time
    state = {"failures": 0, "last_failure_epoch": 0}
    if os.path.exists(LOCKOUT_PATH):
        with open(LOCKOUT_PATH) as f:
            state = json.load(f)
    state["failures"] = state.get("failures", 0) + 1
    state["last_failure_epoch"] = time.time()
    with open(LOCKOUT_PATH, "w") as f:
        json.dump(state, f)
    remaining = MAX_ATTEMPTS - state["failures"]
    if remaining > 0:
        print(f"[REGISTRY] Wrong password. {remaining} attempt(s) left before lockout.")


def _reset_lockout():
    if os.path.exists(LOCKOUT_PATH):
        os.remove(LOCKOUT_PATH)


def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)


def is_initialized() -> bool:
    return os.path.exists(KEYFILE_PATH) and os.path.exists(SALT_PATH)


def init_password():
    if is_initialized():
        print("[REGISTRY] Already initialized. If you've lost the password, "
              "delete config/master.key and config/master.salt manually and "
              "re-run init (this will require re-registering all projects).")
        return
    os.makedirs(CONFIG_DIR, exist_ok=True)
    pw1 = getpass.getpass("Set a master password for this toolkit: ")
    pw2 = getpass.getpass("Confirm password: ")
    if pw1 != pw2:
        print("[REGISTRY] Passwords didn't match. Try again.")
        return
    salt = secrets.token_bytes(16)
    key = _derive_key(pw1, salt)
    with open(SALT_PATH, "wb") as f:
        f.write(salt)
    with open(KEYFILE_PATH, "wb") as f:
        f.write(key)
    # start with an empty, signed registry
    _write_registry({}, key)
    print("[REGISTRY] Initialized. Use `verifyai add-project` to register projects.")


def _load_key_with_prompt() -> bytes:
    if not is_initialized():
        print("[REGISTRY] Not initialized yet. Run `verifyai init` first.")
        raise SystemExit(1)
    _check_lockout()
    with open(SALT_PATH, "rb") as f:
        salt = f.read()
    with open(KEYFILE_PATH, "rb") as f:
        correct_key = f.read()
    pw = getpass.getpass("Master password: ")
    entered_key = _derive_key(pw, salt)
    if not hmac.compare_digest(entered_key, correct_key):
        _record_failure()
        raise SystemExit(1)
    _reset_lockout()
    return correct_key


def _load_stored_key() -> bytes:
    """Used for read/run operations that don't prompt for a password —
    only works because this file never leaves this machine's protected
    folder, which itself is outside any project an agent can reach."""
    with open(KEYFILE_PATH, "rb") as f:
        return f.read()


def _write_registry(data: dict, key: bytes):
    payload = json.dumps(data, sort_keys=True).encode()
    sig = hmac.new(key, payload, hashlib.sha256).hexdigest()
    blob = {"data": data, "signature": sig}
    with open(REGISTRY_PATH, "w") as f:
        json.dump(blob, f, indent=2)


def _read_registry_verified(key: bytes) -> dict:
    if not os.path.exists(REGISTRY_PATH):
        return {}
    with open(REGISTRY_PATH) as f:
        blob = json.load(f)
    payload = json.dumps(blob["data"], sort_keys=True).encode()
    expected = hmac.new(key, payload, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, blob["signature"]):
        print("=" * 60)
        print("TAMPER DETECTED: config/projects.json signature does not match.")
        print("Someone or something edited the registry outside of `verifyai`.")
        print("Refusing to use this registry. Re-run `verifyai add-project`")
        print("with the master password to rebuild trusted entries.")
        print("=" * 60)
        raise SystemExit(1)
    return blob["data"]


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def add_project(project: str, dataset: str, dataset_root: str, script: str, section_label: str = ""):
    key = _load_key_with_prompt()
    data = _read_registry_verified(key)
    data.setdefault(project, {})
    data[project][dataset] = {
        "dataset_root": dataset_root,
        "script": script,
        "section_label": section_label,
        "script_sha256": _sha256_file(script),
        "registered_at_epoch": __import__("time").time(),
    }
    _write_registry(data, key)
    print(f"[REGISTRY] Registered {project}/{dataset}.")
    print(f"[REGISTRY] Pinned script hash: {data[project][dataset]['script_sha256'][:16]}...")
    print("[REGISTRY] If this script is edited later, `verifyai run` will refuse to "
          "run it until you re-register with the password (confirming you reviewed the change).")


def get_entry(project: str, dataset: str) -> dict:
    key = _load_stored_key()
    data = _read_registry_verified(key)
    if project not in data or dataset not in data[project]:
        print(f"[REGISTRY] No entry for {project}/{dataset}. "
              f"Run: verifyai add-project {project} {dataset} --dataset-root <path> --script <path>")
        raise SystemExit(1)
    return data[project][dataset]


def list_all():
    key = _load_stored_key()
    data = _read_registry_verified(key)
    if not data:
        print("[REGISTRY] No projects registered yet.")
        return
    for project, datasets in data.items():
        print(f"{project}:")
        for ds, cfg in datasets.items():
            print(f"  - {ds}: root={cfg['dataset_root']}  script={cfg['script']}")
