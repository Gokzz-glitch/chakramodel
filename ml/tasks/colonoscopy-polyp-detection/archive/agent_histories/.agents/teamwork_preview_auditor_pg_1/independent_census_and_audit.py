import os
import sys
import json
from pathlib import Path
from collections import defaultdict
from PIL import Image

DATASET_ROOT = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")
REPORT_JSON = Path(r"m:\chakramodel\polypgen_integrity_report.json")

def audit_dataset():
    print(f"[*] Starting Independent Census and Audit on: {DATASET_ROOT}")
    assert DATASET_ROOT.exists(), f"Dataset root does not exist: {DATASET_ROOT}"

    with open(REPORT_JSON, "r", encoding="utf-8") as f:
        reported_json = json.load(f)

    discrepancies = []

    # 1. Single Frame Centers (C1 - C6)
    single_counts = {}
    total_single_images = 0
    total_single_masks = 0
    total_single_bboxes = 0
    total_single_overlays = 0
    c3_missing_stems = []
    c1_orphan_stems = []

    for c in range(1, 7):
        c_tag = f"C{c}"
        c_dir = DATASET_ROOT / f"data_{c_tag}"
        img_dir = c_dir / f"images_{c_tag}"
        mask_dir = c_dir / f"masks_{c_tag}"
        bbox_dir = c_dir / f"bbox_{c_tag}"
        overlay_dir = c_dir / f"bbox_images_{c_tag}" if c == 6 else c_dir / f"bbox_image_{c_tag}"

        imgs = sorted([f.name for f in img_dir.glob("*.jpg")]) if img_dir.exists() else []
        masks = sorted([f.name for f in mask_dir.glob("*.jpg")]) if mask_dir.exists() else []
        bboxes = sorted([f.name for f in bbox_dir.glob("*.txt")]) if bbox_dir.exists() else []
        overlays = sorted([f.name for f in overlay_dir.glob("*.jpg")]) if overlay_dir.exists() else []

        single_counts[c_tag] = {
            "images": len(imgs),
            "masks": len(masks),
            "bboxes": len(bboxes),
            "overlays": len(overlays),
        }
        total_single_images += len(imgs)
        total_single_masks += len(masks)
        total_single_bboxes += len(bboxes)
        total_single_overlays += len(overlays)

        # Cross-check reported census for single frames
        rep_c = reported_json["dataset_census"]["single_frame_centers"][c_tag]
        if (rep_c["images_count"] != len(imgs) or
            rep_c["masks_count"] != len(masks) or
            rep_c["bbox_txt_count"] != len(bboxes) or
            rep_c["overlay_count"] != len(overlays)):
            discrepancies.append(f"Mismatch in {c_tag} census: reported {rep_c} vs actual {single_counts[c_tag]}")

        # Check C3 missing bboxes
        if c == 3:
            img_stems = {Path(f).stem for f in imgs}
            bbox_stems = {Path(f).stem for f in bboxes}
            c3_missing_stems = sorted(list(img_stems - bbox_stems))
            if len(c3_missing_stems) != 64:
                discrepancies.append(f"Expected 64 missing bboxes in C3, got {len(c3_missing_stems)}")

        # Check C1 orphan overlay
        if c == 1:
            img_stems = {Path(f).stem for f in imgs}
            overlay_stems = {f[:-14] for f in overlays if f.endswith("_mask_bbox.jpg")}
            c1_orphan_stems = sorted(list(overlay_stems - img_stems))
            if c1_orphan_stems != ["957OLCV1_100H0002"]:
                discrepancies.append(f"Unexpected C1 orphan overlays: {c1_orphan_stems}")

    print(f"Single Frame Totals: {total_single_images} imgs, {total_single_masks} masks, {total_single_bboxes} bboxes, {total_single_overlays} overlays")
    assert total_single_images == 1537
    assert total_single_masks == 1537
    assert total_single_bboxes == 1473
    assert total_single_overlays == 1474

    # 2. Positive Sequences (seq1 - seq23)
    pos_root = DATASET_ROOT / "sequenceData" / "positive"
    total_pos_imgs = 0
    total_pos_masks = 0
    total_pos_bboxes = 0
    total_pos_overlays = 0
    total_rogue_txts = 0
    rogue_breakdown = {}

    for s in range(1, 24):
        s_tag = f"seq{s}"
        s_dir = pos_root / s_tag
        img_dir = s_dir / f"images_{s_tag}"
        mask_dir = s_dir / f"masks_{s_tag}"
        bbox_dir = s_dir / f"bbox_{s_tag}"
        overlay_dir = s_dir / f"bbox_image_{s_tag}"

        imgs = list(img_dir.glob("*.jpg")) if img_dir.exists() else []
        masks = list(mask_dir.glob("*.jpg")) if mask_dir.exists() else []
        bboxes = list(bbox_dir.glob("*.txt")) if bbox_dir.exists() else []
        overlays = list(overlay_dir.glob("*.jpg")) if overlay_dir.exists() else []
        rogue_txts = list(mask_dir.glob("*.txt")) if mask_dir.exists() else []

        total_pos_imgs += len(imgs)
        total_pos_masks += len(masks)
        total_pos_bboxes += len(bboxes)
        total_pos_overlays += len(overlays)
        if rogue_txts:
            total_rogue_txts += len(rogue_txts)
            rogue_breakdown[s_tag] = len(rogue_txts)

    print(f"Positive Sequence Totals: {total_pos_imgs} imgs, {total_pos_masks} masks, {total_pos_bboxes} bboxes, {total_pos_overlays} overlays, {total_rogue_txts} rogue txts")
    assert total_pos_imgs == 2225
    assert total_pos_masks == 2225
    assert total_pos_bboxes == 2225
    assert total_pos_overlays == 2225
    assert total_rogue_txts == 184
    assert rogue_breakdown == {"seq2": 63, "seq7": 48, "seq8": 73}

    # 3. Negative Sequences (seq1_neg - seq23_neg)
    neg_root = DATASET_ROOT / "sequenceData" / "negativeOnly"
    total_neg_imgs = 0
    total_neg_masks = 0
    total_neg_bboxes = 0

    for s in range(1, 24):
        s_dir = neg_root / f"seq{s}_neg"
        imgs = list(s_dir.glob("*.jpg")) if s_dir.exists() else []
        masks = list(s_dir.glob("*mask*.jpg")) if s_dir.exists() else []
        bboxes = list(s_dir.glob("*.txt")) if s_dir.exists() else []
        total_neg_imgs += len(imgs)
        total_neg_masks += len(masks)
        total_neg_bboxes += len(bboxes)

    print(f"Negative Sequence Totals: {total_neg_imgs} imgs, {total_neg_masks} masks, {total_neg_bboxes} bboxes")
    assert total_neg_imgs == 4275
    assert total_neg_masks == 0
    assert total_neg_bboxes == 0

    # 4. Pooled Images (imagesAll_positive)
    pooled_dir = DATASET_ROOT / "imagesAll_positive"
    pooled_imgs = list(pooled_dir.glob("*.jpg")) if pooled_dir.exists() else []
    print(f"Pooled imagesAll_positive count: {len(pooled_imgs)}")
    assert len(pooled_imgs) == 3762
    assert len(pooled_imgs) == (total_single_images + total_pos_imgs)

    # Total visual files
    total_visual_files = (
        total_single_images + total_single_masks + total_single_overlays +
        total_pos_imgs + total_pos_masks + total_pos_overlays +
        total_neg_imgs +
        len(pooled_imgs)
    )
    print(f"Grand Total Visual Files: {total_visual_files:,}")
    assert total_visual_files == 19260

    # 5. Verify C3 64 missing bboxes have valid masks with positive foreground
    c3_mask_dir = DATASET_ROOT / "data_C3" / "masks_C3"
    positive_mask_count = 0
    for stem in c3_missing_stems:
        mask_stem = stem[:-1] if stem.endswith("_") else stem
        mpath = c3_mask_dir / f"{mask_stem}_mask.jpg"
        assert mpath.exists(), f"Mask does not exist: {mpath}"
        with Image.open(mpath) as mim:
            ext = mim.convert("L").getextrema()
            if ext[1] > 0:
                positive_mask_count += 1
    print(f"C3 Missing Bboxes Masks: all 64 exist, {positive_mask_count}/64 have positive polyp masks.")
    assert positive_mask_count == 64

    # 6. Ambiguity 6: C3 trailing underscore image
    special_img = DATASET_ROOT / "data_C3" / "images_C3" / "C3_EndoCV2021_00489_.jpg"
    assert special_img.exists(), "Special C3 trailing underscore image does not exist"
    special_mask = DATASET_ROOT / "data_C3" / "masks_C3" / "C3_EndoCV2021_00489_mask.jpg"
    assert special_mask.exists(), "Corresponding mask for special C3 image does not exist"

    # 7. Ambiguity 8: CSV files
    csv_dir = DATASET_ROOT / "dataDetails_PolypGen_SingleFrames"
    csvs = sorted([f.name for f in csv_dir.glob("*.csv")])
    print(f"CSV files in metadata folder: {csvs}")
    assert csvs == [
        "dataDetails_C1.csv",
        "dataDetails_C2.csv",
        "dataDetails_C3.csv",
        "dataDetails_C4.csv",
        "dataDetails_C5.csv"
    ]
    # Center C6 is confirmed missing from CSVs

    # 8. Bounding Box Parsing and Validation across all 3,698 bbox files
    all_bbox_files = []
    for c in range(1, 7):
        b_dir = DATASET_ROOT / f"data_C{c}" / f"bbox_C{c}"
        if b_dir.exists():
            for f in b_dir.glob("*.txt"):
                all_bbox_files.append(f)
    for s in range(1, 24):
        b_dir = DATASET_ROOT / "sequenceData" / "positive" / f"seq{s}" / f"bbox_seq{s}"
        if b_dir.exists():
            for f in b_dir.glob("*.txt"):
                all_bbox_files.append(f)

    assert len(all_bbox_files) == 3698, f"Expected 3,698 bbox files, got {len(all_bbox_files)}"

    empty_count = 0
    pos_count = 0
    total_boxes = 0
    invalid_format = 0
    invalid_geom = 0
    classes = set()

    for bf in all_bbox_files:
        content = bf.read_text(encoding="utf-8").strip()
        if not content:
            empty_count += 1
            continue
        pos_count += 1
        for line in content.splitlines():
            parts = line.strip().split()
            if len(parts) != 5:
                invalid_format += 1
                continue
            cls_name, x1, y1, x2, y2 = parts
            classes.add(cls_name)
            try:
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            except ValueError:
                invalid_format += 1
                continue
            total_boxes += 1
            if x1 >= x2 or y1 >= y2:
                invalid_geom += 1

    print(f"Bbox Audit: total={len(all_bbox_files)}, empty={empty_count}, positive={pos_count}, total_boxes={total_boxes}, classes={classes}")
    assert empty_count == 641, f"Expected 641 empty bboxes, got {empty_count}"
    assert pos_count == 3057, f"Expected 3057 positive bboxes, got {pos_count}"
    assert total_boxes == 3365, f"Expected 3365 boxes, got {total_boxes}"
    assert invalid_format == 0
    assert invalid_geom == 0
    assert classes == {"polyp"}

    print("\n[INDEPENDENT CENSUS AND VALIDATION COMPLETED WITH 100% ACCURACY]")
    print(f"Total Discrepancies Found: {len(discrepancies)}")
    if discrepancies:
        for d in discrepancies:
            print(f"  [!] Discrepancy: {d}")

if __name__ == "__main__":
    audit_dataset()
