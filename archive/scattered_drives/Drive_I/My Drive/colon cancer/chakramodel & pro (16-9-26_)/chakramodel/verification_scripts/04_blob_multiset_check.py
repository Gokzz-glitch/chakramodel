#!/usr/bin/env python3
"""
Follow-up to script 02: distinguish "blobs genuinely differ" from
"blobs are identical but renumbered".

WHY THIS EXISTS
---------------
Script 02 compared storage records BY NAME: new_weights/data/N against the
data/N entry inside the .bak zip. It reported 310 of 312 differing.

That result is ambiguous, and the ambiguity is a weakness in script 02, not
necessarily a finding about the checkpoints. Storage indices in a PyTorch zip
are assigned by the pickler in serialization order. If the two checkpoints were
serialized on different occasions, data/7 in one need not be the same tensor as
data/7 in the other -- in which case a name-wise comparison would report almost
everything as differing even if the two files contain byte-identical tensor
data.

This script compares the MULTISET of blob hashes instead, which is invariant to
renumbering. That is the test that actually bears on Paper 1 sec 5.3's claim
that "every tensor storage blob is byte-identical".

Interpretation:
  - multiset_identical == True  -> the blob CONTENT is identical in both files
    and only the numbering differs. Paper 1 sec 5.3's claim stands; script 02's
    310/312 was an artifact of comparing by name.
  - multiset_identical == False -> the two files genuinely contain different
    tensor data. Paper 1 sec 5.3's central claim is WRONG and the whole
    "byte-identical tensor storage, differing only by a string prefix"
    argument collapses. Report that plainly; do not soften it.

SAFETY: no torch, no torch.load, no model instantiation.

Run from the repository root:
    .\.venv\Scripts\python.exe verification_scripts\04_blob_multiset_check.py

Writes: verification_results/blob_multiset.json
"""
import collections
import hashlib
import json
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUTDIR = REPO / "verification_results"
OUTDIR.mkdir(exist_ok=True)

UNPACKED = REPO / "new_weights" / "chakra_transformer_best"
BAK = REPO / "weights" / "checkpoints" / "chakra_transformer_best.pth.bak"


def sha(b):
    return hashlib.sha256(b).hexdigest()


print("Reading unpacked tree ...")
a = {}
for p in sorted((UNPACKED / "data").glob("*")):
    if p.is_file():
        a[f"data/{p.name}"] = (p.stat().st_size, sha(p.read_bytes()))

print("Reading .bak zip ...")
b = {}
with zipfile.ZipFile(BAK) as z:
    for n in z.namelist():
        zi = z.getinfo(n)
        if zi.is_dir():
            continue
        parts = n.split("/", 1)
        norm = parts[1] if len(parts) == 2 else n
        if norm.startswith("data/"):
            raw = z.read(n)
            b[norm] = (len(raw), sha(raw))

ha = collections.Counter(h for _, h in a.values())
hb = collections.Counter(h for _, h in b.values())

sa = collections.Counter(s for s, _ in a.values())
sb = collections.Counter(s for s, _ in b.values())

only_a = ha - hb
only_b = hb - ha

name_matches = sum(1 for k in set(a) & set(b) if a[k][1] == b[k][1])

# how many of A's blobs exist ANYWHERE in B
matched_anywhere = sum(min(c, hb[h]) for h, c in ha.items())

# reconstruct the permutation where unambiguous
hb_index = collections.defaultdict(list)
for k, (_, h) in b.items():
    hb_index[h].append(k)
permutation_sample = []
n_moved = 0
for k, (_, h) in sorted(a.items()):
    cands = hb_index.get(h, [])
    if len(cands) == 1 and cands[0] != k:
        n_moved += 1
        if len(permutation_sample) < 15:
            permutation_sample.append({"a": k, "b": cands[0]})

report = {
    "unpacked": str(UNPACKED),
    "bak": str(BAK),
    "n_blobs_a": len(a),
    "n_blobs_b": len(b),
    "n_matching_by_name": name_matches,
    "n_matching_anywhere": matched_anywhere,
    "multiset_identical": (ha == hb),
    "size_multiset_identical": (sa == sb),
    "n_distinct_hashes_a": len(ha),
    "n_distinct_hashes_b": len(hb),
    "n_hashes_only_in_a": sum(only_a.values()),
    "n_hashes_only_in_b": sum(only_b.values()),
    "total_bytes_a": sum(s for s, _ in a.values()),
    "total_bytes_b": sum(s for s, _ in b.values()),
    "n_blobs_renumbered_unambiguously": n_moved,
    "permutation_sample": permutation_sample,
}

out = OUTDIR / "blob_multiset.json"
out.write_text(json.dumps(report, indent=2), encoding="utf-8")

print("\n" + "=" * 70)
print(f"blobs A / B                 : {report['n_blobs_a']} / {report['n_blobs_b']}")
print(f"match BY NAME               : {report['n_matching_by_name']}  <- script 02's test")
print(f"match ANYWHERE (multiset)   : {report['n_matching_anywhere']}  <- the correct test")
print(f"multiset identical          : {report['multiset_identical']}")
print(f"size multiset identical     : {report['size_multiset_identical']}")
print(f"blobs only in A / only in B : {report['n_hashes_only_in_a']} / {report['n_hashes_only_in_b']}")
print(f"total bytes A / B           : {report['total_bytes_a']:,} / {report['total_bytes_b']:,}")
print(f"unambiguously renumbered    : {report['n_blobs_renumbered_unambiguously']}")
print("=" * 70)
if report["multiset_identical"]:
    print("\n=> Blob CONTENT is identical; only the numbering differs.")
    print("   Paper 1 sec 5.3's byte-identity claim STANDS.")
    print("   Script 02's 310/312 was an artifact of comparing by name.")
else:
    print("\n=> Blob content genuinely DIFFERS between the two files.")
    print("   Paper 1 sec 5.3's central claim does NOT hold as written.")
    print("   Report this plainly. Do not soften it.")
print(f"\nWrote {out}")
