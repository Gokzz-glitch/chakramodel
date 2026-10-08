#!/usr/bin/env python3
"""
Paper 1 sec 5.3 re-verification -- REWORKED 2026-09-15.

WHAT CHANGED AND WHY
--------------------
Paper 1 sec 5.3 describes comparing two zip archives:
    A = weights/checkpoints/chakra_transformer_best.pth      (module.-prefixed)
    B = weights/checkpoints/chakra_transformer_best.pth.bak  (clean keys)

Operand A DOES NOT EXIST in the working tree. Confirmed absent by globbing
**/*.pth across the repository. It was never LFS-tracked and was not removed by
the 2026-09-15 filter-repo rewrite; both surviving .bak copies predate that
event. Its absence is simply a fact about the current tree.

What does exist is new_weights/chakra_transformer_best/ -- an UNPACKED tree
containing data.pkl plus 312 storage records under data/. Grepping its data.pkl
shows module.-prefixed key strings (module.decode_head..., etc.), so it is the
prefixed artifact in unpacked form.

So this script compares:
    A' = new_weights/chakra_transformer_best/   (unpacked tree, prefixed)
    B  = weights/checkpoints/chakra_transformer_best.pth.bak   (zip, clean)

*** THIS IS NOT THE SAME TEST. READ THIS BEFORE WRITING UP ANY RESULT. ***

  1. TENSOR-BLOB IDENTITY -- fully testable. Storage records are raw bytes in
     both forms. Comparing new_weights/data/N against the data/N entries inside
     the .bak zip is a genuine byte-for-byte test of the paper's claim that
     every tensor storage blob is identical.

  2. KEY SETS AFTER STRIPPING "module." -- fully testable. The key strings live
     in data.pkl in both forms.

  3. THE 6,128-BYTE data.pkl DELTA -- TESTABLE ONLY UNDER AN ASSUMPTION, and
     the assumption cannot be checked because the original zip is gone.
     The claim is about the serialized pickle inside the original .pth
     (73,677 bytes) versus inside .pth.bak (67,549 bytes). Extracting a zip
     entry yields its original bytes, so IF new_weights/data.pkl is a faithful
     extraction of the .pth's data.pkl, its on-disk size is that same 73,677
     and the delta is directly measurable.
     BUT if new_weights/ was produced by RE-SERIALIZING rather than extracting,
     the pickle framing could differ and the delta would be an artifact of the
     re-save, not of the module. prefix.
     We cannot distinguish these, because the original .pth is absent.
     Blob identity does NOT settle it -- raw tensor bytes would survive a
     re-serialization too.

     => If the measured delta is exactly 6,128 and data.pkl is exactly 73,677,
        treat that as strong corroboration of sec 5.3.
     => If it differs, YOU CANNOT TELL whether the paper is wrong or the
        unpacked tree is not a faithful extraction. Report both possibilities.
        Do NOT report a nearby number as though it were the paper's claim.

Also checks whether the two .bak copies (identical size, 13 days apart) are
byte-identical, which bears on provenance.

SAFETY: never imports torch, never calls torch.load, never instantiates a
model. data.pkl is read with a restricted unpickler whose find_class returns
inert stubs for everything except collections.OrderedDict.

Run from the repository root:
    .\.venv\Scripts\python.exe verification_scripts\02_checkpoint_byte_compare.py

Writes: verification_results/checkpoint_compare.json
"""
import collections
import hashlib
import io
import json
import pickle
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTDIR = REPO / "verification_results"
OUTDIR.mkdir(exist_ok=True)

PTH_MAIN  = REPO / "weights" / "checkpoints" / "chakra_transformer_best.pth"
BAK_MAIN  = REPO / "weights" / "checkpoints" / "chakra_transformer_best.pth.bak"
BAK_STALE = REPO / "archive" / "_stale" / "chakra_transformer_best.pth.bak"
UNPACKED  = REPO / "new_weights" / "chakra_transformer_best"

CLAIM = {
    "data_pkl_prefixed": 73677,
    "data_pkl_clean": 67549,
    "delta": 6128,
    "n_keys": 312,
    "n_entries": 318,
}


class _Stub:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return _Stub()
    def __setstate__(self, state): pass


def _stub_factory(module, name):
    def _f(*a, **k): return _Stub()
    _f.__name__ = f"stub_{module}_{name}"
    return _f


class RestrictedUnpickler(pickle.Unpickler):
    """Recovers structure and string keys. Imports nothing, executes nothing."""
    def find_class(self, module, name):
        if module == "collections" and name == "OrderedDict":
            return collections.OrderedDict
        return _stub_factory(module, name)

    def persistent_load(self, pid):
        return _Stub()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            c = f.read(chunk)
            if not c:
                break
            h.update(c)
    return h.hexdigest()


def flatten_keys(obj, prefix=""):
    """Collect string keys from a state_dict or a dict of state_dicts."""
    keys = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if not isinstance(k, str):
                continue
            if isinstance(v, dict):
                keys.extend(flatten_keys(v, prefix + k + "|"))
            else:
                keys.append(prefix + k)
    return keys


def read_zip(path):
    """{normalised_entry: (size, sha256)} + raw data.pkl bytes."""
    entries, datapkl = {}, None
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            zi = z.getinfo(n)
            if zi.is_dir():
                continue
            raw = z.read(n)
            parts = n.split("/", 1)
            norm = parts[1] if len(parts) == 2 else n
            entries[norm] = (len(raw), sha256_bytes(raw))
            if norm.endswith("data.pkl"):
                datapkl = raw
    return entries, datapkl


def read_tree(d):
    entries, datapkl = {}, None
    for p in sorted(d.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(d).as_posix()
        entries[rel] = (p.stat().st_size, sha256_file(p))
        if p.name == "data.pkl":
            datapkl = p.read_bytes()
    return entries, datapkl


report = {"claim_under_test": CLAIM, "inputs": {}, "notes": [], "caveats": []}

print("=" * 74)
print("Paper 1 sec 5.3 re-verification (REWORKED -- substitute operand)")
print("=" * 74)

report["inputs"]["pth_main_present"] = PTH_MAIN.exists()
print(f"\nchakra_transformer_best.pth present : {PTH_MAIN.exists()}")
if not PTH_MAIN.exists():
    report["caveats"].append(
        "Operand A (the module.-prefixed .pth zip) is ABSENT. The unpacked "
        "new_weights/ tree is used as a substitute. This is not the zip-vs-zip "
        "comparison Paper 1 sec 5.3 describes."
    )
    print("  -> using new_weights/ unpacked tree as substitute operand A'")

# ---- the two .bak copies ---------------------------------------------------
print("\n--- .bak provenance check " + "-" * 47)
bak_info = {}
for label, p in (("bak_main", BAK_MAIN), ("bak_stale", BAK_STALE)):
    if p.exists():
        st = p.stat()
        bak_info[label] = {"path": str(p), "size": st.st_size, "mtime": st.st_mtime,
                           "sha256": sha256_file(p)}
        print(f"{label:<10} {st.st_size:>15,} B  sha256={bak_info[label]['sha256'][:16]}...")
    else:
        bak_info[label] = {"path": str(p), "exists": False}
        print(f"{label:<10} MISSING")
report["inputs"]["bak_copies"] = bak_info

if "sha256" in bak_info.get("bak_main", {}) and "sha256" in bak_info.get("bak_stale", {}):
    same = bak_info["bak_main"]["sha256"] == bak_info["bak_stale"]["sha256"]
    report["inputs"]["bak_copies_byte_identical"] = same
    print(f"\n  two .bak copies byte-identical: {same}")
    print("  (identical size, mtimes 13 days apart -- if byte-identical, the")
    print("   later one is a copy, not an independent re-serialization)")

# ---- load both operands ----------------------------------------------------
if not (UNPACKED.is_dir() and BAK_MAIN.exists()):
    report["notes"].append("Cannot compare: missing unpacked tree or .bak.")
    print("\n!! Cannot compare -- required inputs missing.")
else:
    print("\n--- reading operands (this reads ~2.5 GB; allow a few minutes) ---")
    a_entries, a_pkl = read_tree(UNPACKED)
    b_entries, b_pkl = read_zip(BAK_MAIN)

    a_keys = flatten_keys(RestrictedUnpickler(io.BytesIO(a_pkl)).load()) if a_pkl else []
    b_keys = flatten_keys(RestrictedUnpickler(io.BytesIO(b_pkl)).load()) if b_pkl else []

    a_storage = {k: v for k, v in a_entries.items() if k.startswith("data/")}
    b_storage = {k: v for k, v in b_entries.items() if k.startswith("data/")}
    shared = sorted(set(a_storage) & set(b_storage))
    identical = [k for k in shared if a_storage[k][1] == b_storage[k][1]]
    differing = [k for k in shared if a_storage[k][1] != b_storage[k][1]]

    a_pkl_size = len(a_pkl) if a_pkl else None
    b_pkl_size = len(b_pkl) if b_pkl else None
    delta = (a_pkl_size - b_pkl_size) if (a_pkl_size and b_pkl_size) else None

    strip = lambda ks: sorted(k.replace("module.", "").replace("_orig_mod.", "") for k in ks)
    sa, sb = strip(a_keys), strip(b_keys)

    comp = {
        "operand_a": str(UNPACKED) + "  (UNPACKED TREE -- substitute)",
        "operand_b": str(BAK_MAIN) + "  (zip)",
        "a_total_files": len(a_entries),
        "b_total_entries": len(b_entries),
        "a_storage_records": len(a_storage),
        "b_storage_records": len(b_storage),
        "n_storage_shared": len(shared),
        "n_storage_byte_identical": len(identical),
        "n_storage_differing": len(differing),
        "differing_names_sample": differing[:20],
        "a_data_pkl_bytes": a_pkl_size,
        "b_data_pkl_bytes": b_pkl_size,
        "measured_delta": delta,
        "claimed_delta": CLAIM["delta"],
        "delta_matches_claim": (delta == CLAIM["delta"]) if delta is not None else None,
        "a_data_pkl_matches_claimed_73677": a_pkl_size == CLAIM["data_pkl_prefixed"],
        "b_data_pkl_matches_claimed_67549": b_pkl_size == CLAIM["data_pkl_clean"],
        "a_n_keys": len(a_keys),
        "b_n_keys": len(b_keys),
        "a_n_module_prefixed": sum(1 for k in a_keys if k.startswith("module.")),
        "b_n_module_prefixed": sum(1 for k in b_keys if k.startswith("module.")),
        "key_sets_identical_after_strip": sa == sb,
        "only_in_a_after_strip": sorted(set(sa) - set(sb))[:20],
        "only_in_b_after_strip": sorted(set(sb) - set(sa))[:20],
    }
    report["comparison"] = comp

    print("\n" + "=" * 74)
    print("RESULTS")
    print("=" * 74)
    print(f"storage records            : A={comp['a_storage_records']}  B={comp['b_storage_records']}")
    print(f"storage byte-identical     : {comp['n_storage_byte_identical']} / {comp['n_storage_shared']}")
    print(f"storage differing          : {comp['n_storage_differing']}")
    print(f"keys                       : A={comp['a_n_keys']}  B={comp['b_n_keys']}   (claim: 312 / 312)")
    print(f"module.-prefixed           : A={comp['a_n_module_prefixed']}  B={comp['b_n_module_prefixed']}")
    print(f"key sets equal after strip : {comp['key_sets_identical_after_strip']}")
    print()
    print(f"data.pkl A (unpacked file) : {a_pkl_size}   (claim for .pth: 73,677)")
    print(f"data.pkl B (inside zip)    : {b_pkl_size}   (claim for .bak: 67,549)")
    print(f"measured delta             : {delta}   (claim: 6,128)")
    print(f"delta matches claim        : {comp['delta_matches_claim']}")
    print("=" * 74)

    report["caveats"].append(
        "The data.pkl delta above is measured between an unpacked data.pkl "
        "file and a data.pkl entry inside a zip. It equals the paper's claim "
        "ONLY IF new_weights/ is a faithful extraction of the original .pth "
        "rather than a re-serialization. The original .pth is absent, so this "
        "cannot be confirmed. Tensor-blob identity does not settle it."
    )
    if comp["delta_matches_claim"]:
        report["notes"].append(
            "Measured delta equals the claimed 6,128. Strong corroboration of "
            "sec 5.3, still one step weaker than the original zip-vs-zip test."
        )
    else:
        report["notes"].append(
            "Measured delta does NOT equal 6,128. This is ambiguous between "
            "(a) the paper's figure being wrong and (b) new_weights/ not being "
            "a faithful extraction. Report the ambiguity; do not pick one."
        )

out = OUTDIR / "checkpoint_compare.json"
out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
print(f"\nWrote {out}")
for c in report["caveats"]:
    print(f"\nCAVEAT: {c}")
for n in report["notes"]:
    print(f"\nNOTE: {n}")
