import json
from pathlib import Path

p = Path(r"m:\chakramodel\.agents\teamwork_preview_explorer_pg_1\fast_stats.json")
with open(p, "r", encoding="utf-8") as fp:
    d = json.load(fp)

print("=== EXTRACTED ROOT ===")
for k, v in d.get("extracted_root", {}).items():
    print(f"  {k:35} | dir: {v['is_dir']} | size: {v['size']}")

print("\n=== POLYPGEN ROOT FILES ===")
for k, v in d.get("polypgen_root_files", {}).items():
    print(f"  {k:45} | {v}")

print("\n=== SINGLE FRAMES TOTALS (Centers C1-C6) ===")
print(json.dumps(d["single_frames_totals"], indent=2))

print("\n=== CENTERS BREAKDOWN ===")
for c, info in d["centers"].items():
    print(f"{c}:")
    for k, v in info.items():
        if isinstance(v, dict) and "file_count" in v:
            print(f"  {k:22}: {v['file_count']:5} files, exts: {v['extensions']}, hidden: {v.get('hidden_files', [])}")
        else:
            print(f"  {k:22}: {v}")

print("\n=== SEQUENCE POSITIVE TOTALS ===")
print(json.dumps(d["sequence_positive_totals"], indent=2))

print("\n=== SEQUENCE POSITIVE PER-SEQ BREAKDOWN ===")
for seq, info in d["sequence_positive"].items():
    img_cnt = 0
    mask_cnt = 0
    bbox_cnt = 0
    for k, v in info.items():
        if "images_" in k: img_cnt = v.get("file_count", 0)
        elif "masks_" in k: mask_cnt = v.get("file_count", 0)
        elif "bbox_seq" in k: bbox_cnt = v.get("file_count", 0)
    print(f"  {seq:8}: images={img_cnt:4}, masks={mask_cnt:4}, bboxes={bbox_cnt:4}")

print("\n=== SEQUENCE NEGATIVE TOTALS ===")
print(json.dumps(d["sequence_negative_totals"], indent=2))

print("\n=== SEQUENCE NEGATIVE PER-SEQ BREAKDOWN ===")
for seq, info in d["sequence_negative"].items():
    if isinstance(info, dict):
        print(f"  {seq:12}: {info.get('file_count', 0):4} files, exts: {info.get('extensions')}, subdirs: {info.get('subdirs')}")
    else:
        print(f"  {seq:12}: {info}")

print("\n=== IMAGES ALL POSITIVE ===")
print(json.dumps(d["imagesAll_positive"], indent=2))

print("\n=== CODES ===")
print(json.dumps(d["codes"], indent=2))

print("\n=== DATA DETAILS CSVs ===")
for name, cinfo in d["dataDetails"].items():
    print(f"{name}: {cinfo.get('row_count')} rows, size={cinfo.get('size')}, header: {cinfo.get('header')}")

print("\n=== CONCATENATED ZIP ===")
print(json.dumps(d.get("concatenated_zip", {}), indent=2))
