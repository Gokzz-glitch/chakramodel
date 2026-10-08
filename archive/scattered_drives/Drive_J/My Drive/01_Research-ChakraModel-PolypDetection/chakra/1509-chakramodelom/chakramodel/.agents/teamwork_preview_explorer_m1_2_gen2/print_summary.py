import json

with open(r"m:\chakramodel\.agents\teamwork_preview_explorer_m1_2_gen2\dataset_metrics.json", "r") as f:
    d = json.load(f)

print("=== ZIP SUMMARY ===")
for k, v in d["zips"].items():
    if k == "CVC_ClinicVideoDB_Kaggle.zip":
        continue
    smb = v.get("size_mb", 0)
    tf = v.get("total_files", 0)
    vc = v.get("video_count", 0)
    ic = v.get("image_count", 0)
    mc = v.get("mask_count", 0)
    umc = v.get("unmasked_image_count", 0)
    td = v.get("top_dirs", [])[:8]
    exts = v.get("ext_counts", {})
    print(f"{k}: {smb} MB | Files: {tf} | Videos: {vc} | Images: {ic} (Masks: {mc}, Unmasked: {umc})")
    print(f"   Top dirs: {td}")
    print(f"   Exts: {exts}")

print("\n=== DIR SUMMARY ===")
for k, v in d["dirs"].items():
    smb = v.get("size_mb", 0)
    tf = v.get("total_files", 0)
    vc = v.get("video_count", 0)
    ic = v.get("image_count", 0)
    mc = v.get("mask_count", 0)
    umc = v.get("unmasked_image_count", 0)
    td = v.get("top_dirs", [])[:8]
    exts = v.get("ext_counts", {})
    print(f"{k}: {smb} MB | Files: {tf} | Videos: {vc} | Images: {ic} (Masks: {mc}, Unmasked: {umc})")
    print(f"   Top dirs: {td}")
    print(f"   Exts: {exts}")
