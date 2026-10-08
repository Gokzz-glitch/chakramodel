"""
Evaluate a custom PyTorch segmentation model (e.g. CompNet, architecture given in
model.py) on the ENTIRE original PolypGen2021_MultiCenterData_v3 dataset, and rebuild
a mirrored review folder: same subfolder structure (C1..C6, sequenceData/positive/
seq1..seq23, sequenceData/negativeOnly/seq1_neg..seq23_neg), with every image replaced
by a 3-panel image: [ original | original mask (or "no mask" for negative folders) |
model prediction ]. Writes a master Excel/CSV index, and a summary.md with evaluation
metrics (Dice, IoU, precision, recall, F1) computed against the original masks where
they exist, plus a "flag rate" for the mask-free negativeOnly folders.

This is written for CompNet's shape specifically (single-channel logit output, no
final sigmoid in forward()) but is easy to adapt: everything model-specific lives in
load_model() and predict_mask() below.

Requires model.py (the file with the CompNet class) to be reachable -- either sitting
next to this script, or pointed to with --model_file.

Works in a normal terminal (Windows/Linux) and in notebook platforms like Kaggle. If a
required path isn't given on the command line, it is asked for with input().

Usage:
  python evaluate_polypgen_full.py
  python evaluate_polypgen_full.py --dataset D:/datasets/PolypGen2021_MultiCenterData_v3 \
      --weights path/to/compnet_weights.pth --model_file model.py --out E:/polygon2021_evaluated_and_reviewed_for_CompNet
"""
import argparse
import csv
import importlib.util
import os
from pathlib import Path

import cv2
import numpy as np

IMG_EXTS = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]
MASK_EXTS = [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"]
MASK_SUFFIXES = ["", "_mask", "_gt", "_segmentation"]
PANEL_H = 420
CENTRES = [1, 2, 3, 4, 5, 6]
SEQUENCES = range(1, 24)


# ------------------------------------------------------------------------------- small utils
def ask(prompt, default=None):
    suffix = f" [{default}]" if default else ""
    val = input(f"{prompt}{suffix}: ").strip()
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        val = val[1:-1].strip()  # tolerate quotes pasted/typed around the path
    return val or default


def find_first_existing(candidates):
    for c in candidates:
        if c.is_dir():
            return c
    return None


def list_images(folder):
    if not folder or not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMG_EXTS)


def find_mask(mask_dir, stem):
    if not mask_dir or not mask_dir.is_dir():
        return None
    idx = {f.name.lower(): f.name for f in mask_dir.iterdir() if f.is_file()}
    for suf in MASK_SUFFIXES:
        for ext in MASK_EXTS:
            actual = idx.get((stem + suf + ext).lower())
            if actual:
                return mask_dir / actual
    return None


def label_panel(img, text):
    img = img.copy()
    cv2.rectangle(img, (0, 0), (img.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(img, text, (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def to_panel(img, height=PANEL_H, blank_text=None):
    if img is None:
        img = np.full((height, height, 3), 40, np.uint8)
        if blank_text:
            cv2.putText(img, blank_text, (10, height // 2), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (180, 180, 180), 1, cv2.LINE_AA)
        return img
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    h, w = img.shape[:2]
    scale = height / h
    return cv2.resize(img, (max(1, int(w * scale)), height))


# ------------------------------------------------------------------------------- source discovery
def discover_units(dataset_root):
    root = Path(dataset_root)
    units = []
    for c in CENTRES:
        base = find_first_existing([root / f"data_C{c}", root / f"C{c}"])
        if base is None:
            continue
        img_dir = find_first_existing([base / f"images_C{c}", base / "images"])
        msk_dir = find_first_existing([base / f"masks_C{c}", base / "masks"])
        units.append({"category": f"C{c}", "images_dir": img_dir, "masks_dir": msk_dir,
                       "out_subdir": Path(f"C{c}"), "has_gt": True})

    seq_root = find_first_existing([root / "sequenceData", root / "sequencedata"])
    if seq_root:
        pos_root = find_first_existing([seq_root / "positive"])
        if pos_root:
            for n in SEQUENCES:
                base = pos_root / f"seq{n}"
                if not base.is_dir():
                    continue
                img_dir = find_first_existing([base / f"images_seq{n}", base / "images"])
                msk_dir = find_first_existing([base / f"masks_seq{n}", base / "masks"])
                units.append({"category": f"sequenceData/positive/seq{n}", "images_dir": img_dir,
                               "masks_dir": msk_dir, "out_subdir": Path("sequenceData") / "positive" / f"seq{n}",
                               "has_gt": True})
        neg_root = find_first_existing([seq_root / "negativeOnly"])
        if neg_root:
            for n in SEQUENCES:
                base = find_first_existing([neg_root / f"seq{n}_neg", neg_root / f"seq{n}"])
                if base is None:
                    continue
                units.append({"category": f"sequenceData/negativeOnly/seq{n}_neg", "images_dir": base,
                               "masks_dir": None, "out_subdir": Path("sequenceData") / "negativeOnly" / f"seq{n}_neg",
                               "has_gt": False})
    return units


# ------------------------------------------------------------------------------- model loading (CompNet-specific)
def load_model(model_file, model_class, weights_path, device):
    """Loads the architecture class from model_file, builds it, and loads the weights
    into it. Handles a plain state_dict, a checkpoint dict with a 'state_dict' key, a
    'module.' (DataParallel) prefix, or a fully pickled nn.Module saved directly."""
    import torch

    spec = importlib.util.spec_from_file_location("user_model_arch", model_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, model_class):
        raise SystemExit(f"'{model_class}' class not found in {model_file}. "
                         f"Pass --model_class if the class has a different name.")
    ArchClass = getattr(mod, model_class)

    checkpoint = torch.load(weights_path, map_location=device)

    if isinstance(checkpoint, torch.nn.Module):
        model = checkpoint  # the file already contains a full model object
    else:
        state_dict = checkpoint.get("state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
        state_dict = {(k[7:] if k.startswith("module.") else k): v for k, v in state_dict.items()}
        model = ArchClass()
        model.load_state_dict(state_dict)

    model.to(device)
    model.eval()
    return model


def predict_mask(model, img_bgr, device, imgsz, thresh):
    """Matches the training pipeline exactly: cv2.IMREAD_COLOR loads BGR and the
    training code never converts to RGB, so the image is fed in BGR order here too
    (no cv2.cvtColor). Resize to imgsz x imgsz, HWC->CHW, cast to float32, divide by
    255.0 (no mean/std normalization -- none was used in training).
    CompNet's forward() returns raw logits, single channel, no sigmoid applied.
    Returns: binary_mask (uint8, original image size, 0/255), max_probability (float 0-1)."""
    import torch

    h0, w0 = img_bgr.shape[:2]
    resized = cv2.resize(img_bgr, (imgsz, imgsz))  # stays BGR -- matches training
    tensor = torch.from_numpy(resized).float().permute(2, 0, 1).unsqueeze(0) / 255.0
    tensor = tensor.to(device)

    with torch.no_grad():
        logits = model(tensor)
        probs = torch.sigmoid(logits)[0, 0].cpu().numpy()  # HxW, 0-1

    binary_small = (probs >= thresh).astype(np.uint8) * 255
    binary = cv2.resize(binary_small, (w0, h0), interpolation=cv2.INTER_NEAREST)
    return binary, float(probs.max())


# ------------------------------------------------------------------------------- metrics
def dice_iou_prf(pred_bin, gt_bin):
    """pred_bin, gt_bin: uint8 arrays, 0 or 255, same shape. Returns dict of metrics."""
    p = pred_bin > 0
    g = gt_bin > 0
    inter = np.logical_and(p, g).sum()
    union = np.logical_or(p, g).sum()
    p_sum, g_sum = p.sum(), g.sum()

    if g_sum == 0 and p_sum == 0:
        return {"dice": 1.0, "iou": 1.0, "precision": 1.0, "recall": 1.0, "f1": 1.0}
    dice = (2 * inter) / (p_sum + g_sum) if (p_sum + g_sum) else 0.0
    iou = inter / union if union else 0.0
    precision = inter / p_sum if p_sum else 0.0
    recall = inter / g_sum if g_sum else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {"dice": dice, "iou": iou, "precision": precision, "recall": recall, "f1": f1}


def clean_speckle(pred_bin, min_area=0):
    """Optional cosmetic cleanup: morphological opening (removes lone speckled pixels)
    plus a minimum connected-component area filter. Off unless --denoise is passed, so
    the raw model output and its metrics are never silently altered by default."""
    if min_area <= 0:
        return pred_bin
    kernel = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(pred_bin, cv2.MORPH_OPEN, kernel)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    keep = np.zeros_like(opened)
    for i in range(1, n):  # label 0 is background
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            keep[labels == i] = 255
    return keep


def overlay_prediction(orig_bgr, pred_bin, color=(255, 105, 30), alpha=0.45):
    """Fills the predicted region with a translucent blue color, covering the whole
    predicted shape -- no outline, no bounding box, no label, since CompNet only
    outputs a mask and nothing else should be drawn on top of it. If nothing was
    predicted, returns the original image completely unchanged."""
    contours, _ = cv2.findContours(pred_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    n_regions = len(contours)
    if n_regions == 0:
        return orig_bgr.copy(), 0

    overlay = orig_bgr.copy()
    mask_bool = pred_bin > 0
    colored = np.full_like(orig_bgr, color, dtype=np.uint8)
    blended = cv2.addWeighted(orig_bgr, 1 - alpha, colored, alpha, 0)
    overlay[mask_bool] = blended[mask_bool]
    return overlay, n_regions


# ------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=None, help="path to PolypGen2021_MultiCenterData_v3")
    ap.add_argument("--weights", default=None, help="path to the trained CompNet weights file")
    ap.add_argument("--model_file", default="model.py", help="path to the .py file containing the model class")
    ap.add_argument("--model_class", default="CompNet", help="class name inside model_file")
    ap.add_argument("--out", default=None, help="output root folder for the reviewed dataset")
    ap.add_argument("--imgsz", type=int, default=512, help="input size the model was trained at")
    ap.add_argument("--thresh", type=float, default=0.5, help="sigmoid threshold for a positive pixel")
    ap.add_argument("--device", default=None, help="cuda / cpu; default: cuda if available")
    ap.add_argument("--denoise", type=int, default=0,
                    help="OFF by default (0). If set to a pixel-area threshold (e.g. 40), removes "
                         "scattered speckle regions smaller than that from the predicted mask before "
                         "drawing AND before computing Dice/IoU/etc. Use only if you want a cosmetically "
                         "cleaner mask and are OK with metrics reflecting the cleaned mask, not the raw one.")
    args = ap.parse_args()

    import torch

    dataset_root = Path(args.dataset or ask("Path to the PolypGen2021_MultiCenterData_v3 dataset folder"))
    weights_path = Path(args.weights or ask("Path to the trained CompNet weights file"))
    if not dataset_root.is_dir():
        raise SystemExit(f"Dataset folder not found: {dataset_root}")
    if not weights_path.is_file():
        raise SystemExit(f"Weights file not found: {weights_path}")
    model_file = Path(args.model_file)
    if not model_file.is_file():
        raise SystemExit(f"Model architecture file not found: {model_file} "
                         f"(pass --model_file, or place model.py next to this script)")

    default_out = "/kaggle/working/polygon2021_evaluated_and_reviewed_for_CompNet" \
        if os.path.isdir("/kaggle") else "E:/polygon2021_evaluated_and_reviewed_for_CompNet"
    out_root = Path(args.out or ask("Output folder for the reviewed dataset", default_out))
    out_root.mkdir(parents=True, exist_ok=True)

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print("Preprocessing (matches training): cv2.IMREAD_COLOR (BGR, unchanged) -> resize to "
         f"{args.imgsz}x{args.imgsz} -> HWC->CHW -> float32 -> divide by 255.0. No mean/std "
         "normalization, no augmentation (inference always runs as augment=False).\n")

    model = load_model(model_file, args.model_class, weights_path, device)
    print(f"Loaded {args.model_class} from {weights_path}\n")

    units = discover_units(dataset_root)
    if not units:
        raise SystemExit(f"No recognizable PolypGen folders found under {dataset_root}")
    total_images = sum(len(list_images(u["images_dir"])) for u in units)
    print(f"Found {len(units)} source folders, {total_images} images total.\n")

    rows = []
    category_stats = {}  # category -> list of metric dicts (only for has_gt units)
    neg_flagged = {}      # category -> [count_flagged, count_total]  (only for negativeOnly units)
    done = 0

    for unit in units:
        images = list_images(unit["images_dir"])
        if not images:
            continue
        out_dir = out_root / unit["out_subdir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{unit['category']}] {len(images)} images -> {out_dir}")
        cat_metrics = []
        neg_count = [0, 0]

        for img_path in images:
            orig = cv2.imread(str(img_path))
            if orig is None:
                print(f"  [skip] unreadable image: {img_path}")
                continue
            pred_bin, top_prob = predict_mask(model, orig, device, args.imgsz, args.thresh)
            pred_bin = clean_speckle(pred_bin, args.denoise)  # no-op unless --denoise is set
            pred_overlay, n_regions = overlay_prediction(orig, pred_bin)

            mask_path = find_mask(unit["masks_dir"], img_path.stem) if unit["masks_dir"] else None
            gt_bin = None
            if mask_path:
                gt_raw = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                if gt_raw is not None:
                    _, gt_bin = cv2.threshold(gt_raw, 127, 255, cv2.THRESH_BINARY)

            metrics_text = ""
            if unit["has_gt"] and gt_bin is not None:
                m = dice_iou_prf(pred_bin, gt_bin)
                cat_metrics.append(m)
                metrics_text = f"Dice={m['dice']:.3f} IoU={m['iou']:.3f}"
            elif not unit["has_gt"]:
                neg_count[1] += 1
                if n_regions > 0:
                    neg_count[0] += 1

            mask_panel_src = cv2.imread(str(mask_path)) if mask_path else None
            pred_label = f"3. Predicted: no polyp {metrics_text}".strip() if n_regions == 0 \
                else f"3. Predicted (regions={n_regions}, maxP={top_prob:.2f}) {metrics_text}"
            panels = [
                label_panel(to_panel(orig), "1. Original image"),
                label_panel(to_panel(mask_panel_src, blank_text="no mask (negative folder)" if unit["masks_dir"] is None else "mask not found"),
                           "2. Original mask"),
                label_panel(to_panel(pred_overlay), pred_label),
            ]
            combined = np.hstack(panels)
            out_name = f"{img_path.stem}_reviewed.jpg"
            out_path = out_dir / out_name
            cv2.imwrite(str(out_path), combined)

            row = [unit["category"], img_path.name, str(img_path),
                   str(mask_path) if mask_path else ("N/A (negative folder)" if unit["masks_dir"] is None else "NOT FOUND"),
                   str(out_path), n_regions, round(top_prob, 3)]
            if unit["has_gt"] and gt_bin is not None:
                m = cat_metrics[-1]
                row += [round(m["dice"], 4), round(m["iou"], 4), round(m["precision"], 4),
                        round(m["recall"], 4), round(m["f1"], 4)]
            else:
                row += ["", "", "", "", ""]
            rows.append(row)
            done += 1
            if done % 200 == 0:
                print(f"  {done}/{total_images}")

        if cat_metrics:
            category_stats[unit["category"]] = cat_metrics
        if unit["has_gt"] is False:
            neg_flagged[unit["category"]] = neg_count

    print(f"  {done}/{total_images} (final)")

    # --- master index ---------------------------------------------------------------------
    header = ["category", "filename", "ORIGINAL_IMAGE_PATH", "ORIGINAL_MASK_PATH",
               "output_reviewed_image_path", "predicted_regions", "max_probability",
               "dice", "iou", "precision", "recall", "f1"]
    csv_path = out_root / "evaluation_index.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"\nCSV index: {csv_path}")

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
        from openpyxl.utils import get_column_letter
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Evaluation Index"
        ws.append(header)
        for r in rows:
            ws.append(r)
        for i, c in enumerate(ws[1], start=1):
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F4E79" if i in (3, 4) else "305496")
        for i, width in enumerate([28, 26, 50, 50, 50, 14, 12, 9, 9, 10, 9, 9], start=1):
            ws.column_dimensions[get_column_letter(i)].width = width
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        wb.save(out_root / "evaluation_index.xlsx")
        print(f"Excel index: {out_root / 'evaluation_index.xlsx'}")
    except ImportError:
        print("(openpyxl not installed -- only the CSV index was written; pip install openpyxl for Excel too)")

    # --- summary.md -------------------------------------------------------------------------
    lines = []
    lines.append("# CompNet Evaluation Summary — PolypGen2021_MultiCenterData_v3\n")
    lines.append(f"- Model weights: `{weights_path}`")
    lines.append(f"- Model architecture: `{args.model_class}` from `{model_file}`")
    lines.append(f"- Input size: {args.imgsz}x{args.imgsz}, sigmoid threshold: {args.thresh}")
    lines.append(f"- Device used: {device}")
    lines.append(f"- Total images evaluated: {done}\n")

    if category_stats:
        lines.append("## Segmentation metrics (folders with ground-truth masks)\n")
        lines.append("Per-pixel Dice / IoU / Precision / Recall / F1, averaged over all images in each folder.\n")
        lines.append("| Category | Images | Dice | IoU | Precision | Recall | F1 |")
        lines.append("|---|---|---|---|---|---|---|")
        all_m = []
        for cat, ms in category_stats.items():
            all_m += ms
            avg = {k: sum(m[k] for m in ms) / len(ms) for k in ms[0]}
            lines.append(f"| {cat} | {len(ms)} | {avg['dice']:.3f} | {avg['iou']:.3f} | "
                         f"{avg['precision']:.3f} | {avg['recall']:.3f} | {avg['f1']:.3f} |")
        if all_m:
            overall = {k: sum(m[k] for m in all_m) / len(all_m) for k in all_m[0]}
            lines.append(f"| **OVERALL** | **{len(all_m)}** | **{overall['dice']:.3f}** | **{overall['iou']:.3f}** | "
                         f"**{overall['precision']:.3f}** | **{overall['recall']:.3f}** | **{overall['f1']:.3f}** |")
        lines.append("")

    if neg_flagged:
        lines.append("## Flag rate on negativeOnly folders (no ground truth — model prediction only)\n")
        lines.append("A \"flagged\" frame is one where the model predicted at least one positive region, "
                     "despite the frame being labeled as containing no polyp.\n")
        lines.append("| Sequence | Frames | Flagged | Flag rate |")
        lines.append("|---|---|---|---|")
        tot_flag, tot_n = 0, 0
        for cat, (flagged, n) in neg_flagged.items():
            tot_flag += flagged
            tot_n += n
            rate = 100 * flagged / n if n else 0
            lines.append(f"| {cat} | {n} | {flagged} | {rate:.1f}% |")
        overall_rate = 100 * tot_flag / tot_n if tot_n else 0
        lines.append(f"| **TOTAL** | **{tot_n}** | **{tot_flag}** | **{overall_rate:.1f}%** |")
        lines.append("")

    lines.append("## Notes\n")
    lines.append("- Metrics are computed from the model's own predicted mask vs. the original dataset mask, "
                 "at the original image resolution (predicted mask is upsampled back after inference).")
    lines.append("- Folders with no ground-truth mask (negativeOnly) cannot have Dice/IoU/etc. computed against "
                 "anything, so only a flag rate is reported for them — a high flag rate on a specific sequence "
                 "may indicate that sequence contains unlabeled polyps worth reviewing manually.")
    if args.denoise > 0:
        lines.append(f"- Speckle cleanup was ON (--denoise {args.denoise}): regions smaller than "
                     f"{args.denoise} pixels were removed from the predicted mask before metrics and "
                     "visualization, for both the folder-level and per-image tables below.")
    else:
        lines.append("- Speckle cleanup was OFF: every number below reflects the model's raw, unfiltered "
                     "prediction, exactly as it came out of the network.")
    lines.append("")

    lines.append("## Per-image metrics — every image with a ground-truth mask\n")
    lines.append(f"{len(all_m) if category_stats else 0} rows, one per image, in source-folder order. "
                 "Identical to evaluation_index.csv but inlined here as requested.\n")
    lines.append("| Category | Filename | Dice | IoU | Precision | Recall | F1 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        if r[7] != "":  # dice column is non-empty only for images with ground truth
            lines.append(f"| {r[0]} | {r[1]} | {r[7]:.3f} | {r[8]:.3f} | {r[9]:.3f} | {r[10]:.3f} | {r[11]:.3f} |")
    lines.append("")

    if neg_flagged:
        lines.append("## Per-image results — every negativeOnly frame (no ground truth)\n")
        lines.append("`flagged = yes` means the model predicted at least one polyp region on a frame "
                     "labeled as having none.\n")
        lines.append("| Category | Filename | Predicted regions | Max probability | Flagged |")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            if r[7] == "" and r[0].startswith("sequenceData/negativeOnly"):
                flagged = "yes" if r[5] > 0 else "no"
                lines.append(f"| {r[0]} | {r[1]} | {r[5]} | {r[6]:.3f} | {flagged} |")
        lines.append("")

    lines.append("- The two tables above are the complete per-image results; evaluation_index.csv / .xlsx "
                 "contain the same rows in spreadsheet form for filtering/sorting.")

    (out_root / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Summary: {out_root / 'summary.md'}")

    print(f"\nDone. {done} images evaluated and reviewed. Output tree: {out_root}")


if __name__ == "__main__":
    main()
