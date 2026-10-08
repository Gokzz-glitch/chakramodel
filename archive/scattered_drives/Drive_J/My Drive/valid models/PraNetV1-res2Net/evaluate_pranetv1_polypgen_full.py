"""
Evaluate PraNet-V1 (Res2Net50 backbone) -- from ai4colonoscopy/PraNet-V2's
binary_seg/lib/PraNet_Res2Net.py -- on the ENTIRE original PolypGen2021_MultiCenterData_v3
dataset, and rebuild a mirrored review folder: same subfolder structure (C1..C6,
sequenceData/positive/seq1..seq23, sequenceData/negativeOnly/seq1_neg..seq23_neg),
with every image replaced by a 3-panel image: [ original | original mask (or "no
mask" for negative folders) | model prediction ]. Writes a master Excel/CSV index,
and a summary.md with per-image and per-folder Dice/IoU/Precision/Recall/F1, plus a
flag rate for negativeOnly.

Preprocessing and output handling are both taken directly from the repo's own
binary_seg/MyTest_med.py and binary_seg/utils/dataloader.py-style test_dataset (the
same loader class every PraNet-family fork reuses unchanged), not guessed:
  - image loaded as RGB (PIL .convert('RGB') in the original; we read with cv2,
    which gives BGR, so we explicitly convert BGR->RGB to match)
  - resized to testsize x testsize (352 by default, matching the paper)
  - scaled to [0, 1] then normalized with ImageNet mean/std:
      mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
  - model returns 4 outputs (lateral_map_5, lateral_map_4, lateral_map_3,
    lateral_map_2); MyTest_med.py uses only the LAST one (lateral_map_2) as the
    final prediction -- that is what this script does too for PraNet
    (defined in PraNet_Res2Net.py)

Thresholding -- a deliberate difference from the original inference code: MyTest_med.py
never thresholds; it min-max normalizes each image's sigmoid map to 0-1 and saves it as
a grayscale picture for continuous-map metrics. Doing that per image forces every
image's brightest pixel to exactly 1.0, so putting a threshold on top of it would
give EVERY frame a predicted region, even one where the model is confident there is
no polyp (and "max probability" would always read 1.00). So by default this script
thresholds the RAW sigmoid probability at --thresh (0.5, the natural decision point
for a sigmoid output). Pass --minmax to apply the author's per-image normalization
before thresholding, if you want to see that behaviour.

Requires the repo's own `lib` folder (containing PraNet_Res2Net.py, Res2Net_v1b.py,
pvtv2.py, and ideally ResNet.py) to be importable -- point --lib_parent at the
FOLDER THAT CONTAINS `lib`, not at `lib` itself. This is necessary because
PraNet_Res2Net.py uses `from .Res2Net_v1b import ...` (a relative import, so `lib`
must be a real importable package) and `from lib.pvtv2 import pvt_v2_b2` (an
absolute import, so the folder must literally be named `lib`). The repo's
constructor may also look for the Res2Net50 pretrained file in ./models/ --
the script switches into --lib_parent while building the model so that works.

Works in a normal terminal (Windows/Linux) and in notebook platforms like Kaggle. If
a required path isn't given on the command line, it is asked for with input().

Usage:
  python evaluate_pranetv1_polypgen_full.py
  python evaluate_pranetv1_polypgen_full.py --dataset D:/datasets/PolypGen2021_MultiCenterData_v3 \
      --weights ./snapshots/PraNet-V1/RES-V1.pth --lib_parent ./binary_seg \
      --testsize 352 --out E:/pranetv1_eval
"""
import argparse
import csv
import os
import sys
from pathlib import Path

import cv2
import numpy as np

IMG_EXTS = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]
MASK_EXTS = [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"]
MASK_SUFFIXES = ["", "_mask", "_gt", "_segmentation"]
PANEL_H = 420
CENTRES = [1, 2, 3, 4, 5, 6]
SEQUENCES = range(1, 24)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


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




# ------------------------------------------------------------------------------- model loading (PraNet-V1-specific)
def load_model(lib_parent, weights_path, device):
    """PraNet_Res2Net.py uses a relative import (`from .Res2Net_v1b import ...`) and
    an absolute one (`from lib.pvtv2 import pvt_v2_b2`), so `lib` must be imported as
    a real package, not loaded as a loose file. lib_parent must be the folder that
    CONTAINS `lib` (i.e. lib_parent/lib/PraNet_Res2Net.py must exist).

    The repo's own constructors read backbone files via paths relative to the current
    working directory (./models/...), so the working directory is switched to
    lib_parent ONLY while the model is being constructed, then switched back --
    every other path you pass in keeps working from wherever you launched the script."""
    import torch

    lib_parent = Path(lib_parent).resolve()
    weights_path = Path(weights_path).resolve()
    lib_dir = lib_parent / "lib"
    if not (lib_dir / "PraNet_Res2Net.py").is_file():
        raise SystemExit(f"Expected {lib_dir / 'PraNet_Res2Net.py'} to exist -- "
                         f"--lib_parent must be the folder that CONTAINS 'lib', not 'lib' itself.")
    init_file = lib_dir / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")  # make `lib` a proper importable package

    # (no extra backbone file required beyond what the repo's constructor handles)

    sys.path.insert(0, str(lib_parent))
    from lib.PraNet_Res2Net import PraNet

    print("[info] constructing PraNet (the repo's own code may load backbone weights "
         "from ./models/ or download them the first time -- that is not this script)")
    original_cwd = os.getcwd()
    try:
        os.chdir(lib_parent)  # so the repo's ./models/... relative paths resolve
        model = PraNet()
    except Exception as e:
        raise SystemExit(f"Constructing PraNet failed: {e}\n"
                         f"If this mentions a missing res2net50_v1b_26w_4s-3cf99910.pth or a failed download, put that file in <lib_parent>/models/ (per the repo README) or make sure this machine has internet access, then run again.")
    finally:
        os.chdir(original_cwd)

    state_dict = torch.load(weights_path, map_location=device)
    model.load_state_dict(state_dict)  # strict=True, matching MyTest_med.py for V1 models
    model.to(device)
    model.eval()
    return model


def predict_mask(model, img_bgr, device, testsize, thresh, minmax=False):
    """Matches MyTest_med.py: BGR->RGB, resize to testsize x testsize, scale to 0-1,
    ImageNet mean/std normalize, take the model's LAST output (lateral_map_2), resize
    the logits to the original size, sigmoid. The RAW sigmoid probability is then
    thresholded (see module docstring for why the author's per-image min-max
    normalization is NOT applied unless minmax=True).
    Returns: binary_mask (uint8, original image size, 0/255), max_probability (float 0-1)."""
    import torch
    import torch.nn.functional as F

    h0, w0 = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(img_rgb, (testsize, testsize)).astype(np.float32) / 255.0
    tensor = torch.from_numpy(resized).permute(2, 0, 1)
    mean = torch.tensor(IMAGENET_MEAN).view(3, 1, 1)
    std = torch.tensor(IMAGENET_STD).view(3, 1, 1)
    tensor = (tensor - mean) / std
    tensor = tensor.unsqueeze(0).to(device)

    with torch.no_grad():
        outs = model(tensor)
        res5, res4, res3, res2 = outs  # 4-tuple; MyTest_med.py uses only the last (res2)
        res = res2
        res = F.interpolate(res, size=(h0, w0), mode="bilinear", align_corners=False)
        res = res.sigmoid().data.cpu().numpy().squeeze()

    if minmax:  # the author's per-image normalization (forces max -> 1.0 on every image)
        res = (res - res.min()) / (res.max() - res.min() + 1e-8)
    binary = (res >= thresh).astype(np.uint8) * 255
    return binary, float(res.max())


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
    ap.add_argument("--weights", default=None, help="path to the .pth checkpoint (e.g. RES-V1.pth)")
    ap.add_argument("--lib_parent", default=None,
                    help="folder that CONTAINS the repo's 'lib' folder (which holds PraNet_Res2Net.py, "
                         "Res2Net_v1b.py, pvtv2.py) -- e.g. the 'binary_seg' folder from the clone")
    ap.add_argument("--out", default=None, help="output root folder for the reviewed dataset")
    ap.add_argument("--testsize", type=int, default=352, help="input size (352, matching the paper)")
    ap.add_argument("--thresh", type=float, default=0.5, help="threshold on the raw sigmoid probability")
    ap.add_argument("--minmax", action="store_true",
                    help="apply the author's per-image min-max normalization before thresholding "
                         "(off by default -- it makes every frame, even polyp-free ones, get a predicted region)")
    ap.add_argument("--device", default=None, help="cuda / cpu; default: cuda if available")
    ap.add_argument("--denoise", type=int, default=0,
                    help="OFF by default (0). If set to a pixel-area threshold (e.g. 40), removes "
                         "scattered speckle regions smaller than that from the predicted mask before "
                         "drawing AND before computing Dice/IoU/etc.")
    args = ap.parse_args()

    import torch

    dataset_root = Path(args.dataset or ask("Path to the PolypGen2021_MultiCenterData_v3 dataset folder"))
    weights_path = Path(args.weights or ask("Path to the .pth checkpoint (e.g. RES-V1.pth)"))
    lib_parent = Path(args.lib_parent or ask("Folder that CONTAINS the repo's 'lib' folder (e.g. binary_seg)"))
    if not dataset_root.is_dir():
        raise SystemExit(f"Dataset folder not found: {dataset_root}")
    if not weights_path.is_file():
        raise SystemExit(f"Weights file not found: {weights_path}")

    default_out = "/kaggle/working/pranetv1_polypgen2021_reviewed" \
        if os.path.isdir("/kaggle") else "E:/pranetv1_polypgen2021_reviewed"
    out_root = Path(args.out or ask("Output folder for the reviewed dataset", default_out))
    out_root.mkdir(parents=True, exist_ok=True)

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    print(f"Model: PraNet-V1 (Res2Net50 backbone), testsize: {args.testsize}x{args.testsize}")
    print("Preprocessing (confirmed from MyTest_med.py / the repo's test_dataset loader): "
         "BGR->RGB -> resize -> scale 0-1 -> ImageNet mean/std normalize. "
         "Using the model's LAST output (lateral_map_2), matching MyTest_med.py. "
         f"Threshold {args.thresh} is applied to the RAW sigmoid probability"
         f"{' after the author-style per-image min-max normalization (--minmax)' if args.minmax else ''}.\n")

    model = load_model(lib_parent, weights_path, device)
    print(f"Loaded PraNet-V1 from {weights_path}\n")

    units = discover_units(dataset_root)
    if not units:
        raise SystemExit(f"No recognizable PolypGen folders found under {dataset_root}")
    total_images = sum(len(list_images(u["images_dir"])) for u in units)
    print(f"Found {len(units)} source folders, {total_images} images total.\n")

    rows = []
    category_stats = {}
    neg_flagged = {}
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
            pred_bin, top_prob = predict_mask(model, orig, device, args.testsize, args.thresh, args.minmax)
            pred_bin = clean_speckle(pred_bin, args.denoise)
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
            panels = [
                label_panel(to_panel(orig), "1. Original image"),
                label_panel(to_panel(mask_panel_src, blank_text="no mask (negative folder)" if unit["masks_dir"] is None else "mask not found"),
                           "2. Original mask"),
                label_panel(to_panel(pred_overlay), f"3. Predicted (regions={n_regions}, maxP={top_prob:.2f}) {metrics_text}"),
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

    lines = []
    lines.append("# PraNet-V1 Evaluation Summary — PolypGen2021_MultiCenterData_v3\n")
    lines.append("- Model: `PraNet-V1` (Res2Net50 backbone, class `PraNet`)")
    lines.append(f"- Weights: `{weights_path}`")
    lines.append(f"- Test size: {args.testsize}x{args.testsize}, threshold: {args.thresh} on the "
                 f"{'min-max-normalized' if args.minmax else 'raw sigmoid'} probability map")
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
    lines.append("- Model: PraNet-V1 (Res2Net50 backbone).")
    lines.append("- Uses the model's LAST output (lateral_map_2) as the final prediction, matching MyTest_med.py.")
    if args.minmax:
        lines.append("- --minmax was ON: each image's probability map was min-max normalized before thresholding, "
                     "so every frame's brightest pixel is 1.0 and polyp-free frames are still expected to be flagged.")
    else:
        lines.append("- The threshold was applied to the RAW sigmoid probability (no per-image min-max normalization), "
                     "so a frame the model is confident is polyp-free stays empty. max_probability is the raw sigmoid maximum.")
    lines.append("- Metrics are computed from the model's own predicted mask vs. the original dataset mask, "
                 "at the original image resolution.")
    if args.denoise > 0:
        lines.append(f"- Speckle cleanup was ON (--denoise {args.denoise}).")
    else:
        lines.append("- Speckle cleanup was OFF: every number below reflects the model's raw, unfiltered prediction.")
    lines.append("")

    lines.append("## Per-image metrics — every image with a ground-truth mask\n")
    lines.append("| Category | Filename | Dice | IoU | Precision | Recall | F1 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in rows:
        if r[7] != "":
            lines.append(f"| {r[0]} | {r[1]} | {r[7]:.3f} | {r[8]:.3f} | {r[9]:.3f} | {r[10]:.3f} | {r[11]:.3f} |")
    lines.append("")

    if neg_flagged:
        lines.append("## Per-image results — every negativeOnly frame (no ground truth)\n")
        lines.append("| Category | Filename | Predicted regions | Max probability | Flagged |")
        lines.append("|---|---|---|---|---|")
        for r in rows:
            if r[7] == "" and r[0].startswith("sequenceData/negativeOnly"):
                flagged = "yes" if r[5] > 0 else "no"
                lines.append(f"| {r[0]} | {r[1]} | {r[5]} | {r[6]:.3f} | {flagged} |")
        lines.append("")

    (out_root / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Summary: {out_root / 'summary.md'}")
    print(f"\nDone. {done} images evaluated and reviewed. Output tree: {out_root}")


if __name__ == "__main__":
    main()
