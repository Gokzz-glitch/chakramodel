import os
from pathlib import Path

POLYPGEN = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")

print("=== 1. Inspect C1 extra bbox_image ===")
c1_img = set(os.path.splitext(f)[0] for f in os.listdir(POLYPGEN / "data_C1" / "images_C1"))
c1_bbox_img = set(f.replace("_mask_bbox", "").replace(".jpg", "") for f in os.listdir(POLYPGEN / "data_C1" / "bbox_image_C1"))
extra_in_bbox_img = [f for f in os.listdir(POLYPGEN / "data_C1" / "bbox_image_C1") if f.replace("_mask_bbox", "").replace(".jpg", "") not in c1_img]
print("Extra files in data_C1/bbox_image_C1:", extra_in_bbox_img)

print("\n=== 2. Inspect C3 missing bboxes ===")
c3_imgs = set(os.path.splitext(f)[0] for f in os.listdir(POLYPGEN / "data_C3" / "images_C3"))
c3_bboxes = set(f.replace("_mask.txt", "") for f in os.listdir(POLYPGEN / "data_C3" / "bbox_C3"))
c3_missing = sorted(list(c3_imgs - c3_bboxes))
print(f"Count of C3 images without bbox: {len(c3_missing)}")
print("Sample C3 images without bbox:", c3_missing[:10])

# Check mask files for these missing bboxes
c3_masks_missing = []
for name in c3_missing:
    mask_file = POLYPGEN / "data_C3" / "masks_C3" / f"{name}_mask.jpg"
    c3_masks_missing.append((name, mask_file.exists(), mask_file.stat().st_size if mask_file.exists() else 0))
print("Mask status for missing bboxes (sample):", c3_masks_missing[:5])

print("\n=== 3. Inspect seq2, seq7, seq8 double masks ===")
for s in ["seq2", "seq7", "seq8"]:
    mask_dir = POLYPGEN / "sequenceData" / "positive" / s / f"masks_{s}"
    masks = sorted(os.listdir(mask_dir))
    print(f"{s} total masks: {len(masks)}, sample mask names:")
    print("  ", masks[:8])

print("\n=== 4. Inspect codes/ files ===")
codes_dir = POLYPGEN / "codes"
for root, dirs, files in os.walk(codes_dir):
    for f in files:
        fp = os.path.join(root, f)
        print(f"  {f:35} | {os.path.getsize(fp)} bytes")

print("\n=== 5. Inspect CSV headers and content in dataDetails_PolypGen_SingleFrames ===")
dt_dir = POLYPGEN / "dataDetails_PolypGen_SingleFrames"
for f in dt_dir.iterdir():
    if f.suffix == ".csv":
        with open(f, "r", encoding="utf-8") as fp:
            lines = [fp.readline().strip() for _ in range(4)]
            print(f"--- {f.name} ---")
            for l in lines:
                print("  ", l)

print("\n=== 6. Check .agents directory in extracted root ===")
agents_dir = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\.agents")
for root, dirs, files in os.walk(agents_dir):
    rel = os.path.relpath(root, agents_dir)
    print(f"  [{rel}] dirs: {dirs}, files: {files}")
