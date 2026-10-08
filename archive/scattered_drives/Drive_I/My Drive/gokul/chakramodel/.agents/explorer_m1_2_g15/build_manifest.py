import os
import json
import re
from pathlib import Path

# Load raw inventory
with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\c_downloads_raw.json", "r", encoding="utf-8") as f:
    c_raw = json.load(f)
with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\j_downloads_raw.json", "r", encoding="utf-8") as f:
    j_raw = json.load(f)

# Combine file entries
entries = []
for item in c_raw:
    if item.get("type") == "file":
        entries.append(("C_Downloads", item["path"], item["name"], item["size"], item["mtime"]))
for item in j_raw:
    if item.get("type") == "file":
        entries.append(("J_Downloads", item["path"], item["name"], item["size"], item["mtime"]))

print(f"Total files evaluated: {len(entries)}")

# 1. Deny filters
personal_regex = re.compile(r"(passport|resume|receipt|payment|booking|mess\s*fees|bill|profile\.pdf|\.ics$|leads|eclipse|acer\s*care|chatgpt\s*installer|chromesetup|desktop\.ini$|screenshot|opus_keyword)", re.I)

# 2. Inclusion criteria
chakra_indicators = [
    "chakra", "polyp", "kvasir", "cvc", "etis", "pranet", "colondb",
    "bytetrack", "sam2", "conformal", "anti_fabrication", "combocld",
    "om-krish", "om-final", "finalmuruga", "crossvali", "cross_dataset",
    "v7verifiactiob", "claudev7", "yolo", "combo", "fcbformer", "endoslam",
    "chakramodel_om_4", "muruga-perumal", "testingnamashivaya", "prrof"
]

manifest = []

for src, p, name, sz, mtime in entries:
    name_lower = name.lower()
    p_lower = p.lower()
    ext = Path(name).suffix.lower()

    # Check denial
    if personal_regex.search(name) or personal_regex.search(p):
        manifest.append({
            "source_type": src,
            "source_path": p,
            "name": name,
            "size": sz,
            "category": "QUARANTINED_PERSONAL",
            "reason": "Matches personal/unrelated denial pattern",
            "action": "EXCLUDE"
        })
        continue

    # Check inclusion
    is_chakra = any(ind in name_lower or ind in p_lower for ind in chakra_indicators)
    # Check if inside CHAKRAMODEL_OM_4 snapshot
    if "chakramodel_om_4" in p_lower:
        is_chakra = True

    if not is_chakra:
        # check if .ipynb
        if ext == ".ipynb":
            # inspect if notebook is one of the generic numbered ones from kaggle
            if re.match(r"^notebook[0-9a-f]{10}", name_lower) or "finalrun" in name_lower or "testing" in name_lower:
                is_chakra = True
            else:
                manifest.append({
                    "source_type": src,
                    "source_path": p,
                    "name": name,
                    "size": sz,
                    "category": "UNRELATED",
                    "reason": "Notebook without Chakramodel indicators",
                    "action": "EXCLUDE"
                })
                continue
        else:
            manifest.append({
                "source_type": src,
                "source_path": p,
                "name": name,
                "size": sz,
                "category": "UNRELATED",
                "reason": "No Chakramodel indicators",
                "action": "EXCLUDE"
            })
            continue

    # Categorize and assign target destination
    cat = "UNKNOWN"
    dest = None
    priority = "NORMAL"

    if ext in ('.pth', '.pt', '.ckpt', '.onnx', '.weights') or name in ("om-finalkaggle-upload", "chakra_transformer_best.zip"):
        cat = "WEIGHTS"
        priority = "CRITICAL"
        if "chakra_transformer" in name_lower or "combo" in name_lower or "pranet" in name_lower:
            dest = f"M:\\chakramodel\\weights\\checkpoints\\{name if ext != '' else name + '.zip'}"
        else:
            dest = f"M:\\chakramodel\\weights\\yolo\\{name}"
    elif ext == '.ipynb':
        cat = "NOTEBOOK"
        if "om-krish-4-6 (2)" in name_lower:
            priority = "CRITICAL_PROVENANCE"
            dest = f"M:\\chakramodel\\notebooks\\provenance\\{name}"
        elif "om-krish" in name_lower:
            priority = "HIGH"
            dest = f"M:\\chakramodel\\notebooks\\training_runs\\{name}"
        elif any(k in name_lower for k in ("claudev7", "crossvali", "verified_eval", "evalharness", "universal_evaluation", "verify")):
            priority = "HIGH"
            dest = f"M:\\chakramodel\\notebooks\\evaluation\\{name}"
        else:
            dest = f"M:\\chakramodel\\notebooks\\kaggle_archive\\{name}"
    elif ext == '.zip':
        cat = "ARCHIVE"
        if "weight" in name_lower:
            priority = "CRITICAL"
            dest = f"M:\\chakramodel\\weights\\archive\\{name}"
        elif "dataset" in name_lower or "cvc" in name_lower:
            priority = "HIGH"
            dest = f"M:\\chakramodel\\data\\archive\\{name}"
        elif "toolkit" in name_lower or "fabrication" in name_lower:
            priority = "HIGH"
            dest = f"M:\\chakramodel\\tools\\archive\\{name}"
        else:
            dest = f"M:\\chakramodel\\results\\archives\\{name}"
    elif ext in ('.json', '.csv'):
        cat = "EVAL_OR_METRICS"
        if "eval" in name_lower or "metric" in name_lower or "results" in name_lower or "verdict" in name_lower:
            priority = "HIGH"
            dest = f"M:\\chakramodel\\results\\recovered\\{name}"
        else:
            dest = f"M:\\chakramodel\\results\\recovered\\{name}"
    elif ext == '.pdf':
        cat = "DOC_OR_PAPER"
        if re.match(r"^\d{2}_", name):
            dest = f"M:\\chakramodel\\research_papers\\{name}"
        elif "audit" in name_lower:
            priority = "HIGH"
            dest = f"M:\\chakramodel\\docs\\audit\\{name}"
        else:
            dest = f"M:\\chakramodel\\docs\\pdfs\\{name}"
    elif ext in ('.md', '.txt'):
        cat = "DOC"
        dest = f"M:\\chakramodel\\docs\\recovered\\{name}"
    elif ext == '.py':
        cat = "CODE"
        dest = f"M:\\chakramodel\\src\\recovered\\{name}"
    else:
        cat = "OTHER_ASSET"
        dest = f"M:\\chakramodel\\assets\\recovered\\{name}"

    # Check collision status with dest
    dest_exists = False
    dest_size = None
    dest_identical = False
    if dest:
        dest_path = Path(dest)
        dest_exists = dest_path.exists()
        if dest_exists:
            dest_size = dest_path.stat().st_size
            if dest_size == sz:
                dest_identical = True

    manifest.append({
        "source_type": src,
        "source_path": p,
        "name": name,
        "size": sz,
        "mtime": mtime,
        "category": cat,
        "priority": priority,
        "recommended_destination": dest,
        "dest_exists": dest_exists,
        "dest_size": dest_size,
        "dest_identical": dest_identical,
        "action": "SKIP_IDENTICAL" if dest_identical else ("BACKUP_AND_UPDATE" if dest_exists else "RECOVER")
    })

with open(r"M:\chakramodel\.agents\explorer_m1_2_g15\recovery_manifest.json", "w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)

print(f"Manifest written with {len(manifest)} items.")

# Print category breakdown
from collections import Counter
c = Counter(m["category"] for m in manifest)
for k, v in c.most_common():
    print(f"  {k:25}: {v}")

a = Counter(m["action"] for m in manifest)
print("\nAction breakdown:")
for k, v in a.most_common():
    print(f"  {k:25}: {v}")
