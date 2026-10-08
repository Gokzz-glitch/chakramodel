#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
overlay_audit.py -- Annotation overlay detection for all 7 manifests
=====================================================================

For every image referenced by the 7 manifests used in
configs/baseline_unet.yaml this script:

  1. Runs multi-heuristic overlay detection (no filenames or metadata used).
  2. Classifies each image as:
       - CLEAN       : all heuristics below threshold
       - OVERLAY     : one or more heuristics confidently triggered
       - UNCERTAIN   : borderline, manual review needed
  3. Generates contact sheets (random samples) per manifest role.
  4. Generates a flagged contact sheet for every suspected overlay image.
  5. Writes a machine-readable JSON report.

Does NOT modify, delete, move, repair, or overwrite any source file.
Does NOT remove any path from any manifest.
Exits with code 1 if any OVERLAY is found in train or val splits.

Detection heuristics (all operate on raw RGB pixel arrays):
  H1  Unnatural saturated green / cyan dominance (annotation contours)
  H2  Solid-color connected components (burned-in colored masks)
  H3  Thin bright-edge network (drawn lines / arrows)
  H4  White / bright-grey text-region density (burned-in text)
  H5  Rectangular border anomaly (scale bars, info boxes)
  H6  Non-circular black border inside image center (endoscope border OK,
       interior black rectangles are annotations)

Usage
-----
    python scripts/overlay_audit.py [--project-root .]
                                    [--contact-samples 20]
                                    [--workers 1]
"""

import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ─── Manifest definitions (same 7 as integrity_check.py) ─────────────────────
MANIFEST_ROLES = {
    "train":         "data/processed/manifests/train_pranet_train.tsv",
    "val":           "data/processed/manifests/val_pranet.tsv",
    "test_kvasir":   "data/processed/manifests/test_kvasir.tsv",
    "test_clinicdb": "data/processed/manifests/test_cvc_clinicdb.tsv",
    "test_colondb":  "data/processed/manifests/test_cvc_colondb.tsv",
    "test_etis":     "data/processed/manifests/test_etis_laribpolypdb.tsv",
    "test_cvc300":   "data/processed/manifests/test_cvc_300.tsv",
}

RANDOM_SEED = 42
CONTACT_THUMB_SIZE = (180, 180)   # px per thumbnail in contact sheet
FLAGGED_THUMB_SIZE = (320, 320)   # px per thumbnail in flagged sheet

# ─── Verdict thresholds ───────────────────────────────────────────────────────
# Adjust here; the raw scores are logged so thresholds can be re-tuned offline.
OVERLAY_THRESHOLD   = 3    # score >= this -> OVERLAY
UNCERTAIN_THRESHOLD = 1    # score >= this -> UNCERTAIN, else CLEAN


# ─── Helpers ─────────────────────────────────────────────────────────────────

def read_manifest(tsv_path: Path) -> list[tuple[str, str]]:
    pairs = []
    with open(tsv_path, encoding="utf-8") as fh:
        header = fh.readline().strip().split("\t")
        if "image" in header:
            ic, mc = header.index("image"), header.index("mask")
        elif "image_path" in header:
            ic, mc = header.index("image_path"), header.index("mask_path")
        else:
            raise ValueError(f"Unknown header in {tsv_path}: {header}")
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                pairs.append((parts[ic], parts[mc]))
    return pairs


def load_rgb(path: Path) -> np.ndarray | None:
    """Load image as uint8 HxWx3 RGB array. Returns None on failure."""
    try:
        with Image.open(path) as im:
            return np.array(im.convert("RGB"), dtype=np.uint8)
    except Exception:
        return None


def make_thumbnail(arr: np.ndarray, size: tuple[int, int]) -> Image.Image:
    """Resize array to thumbnail, preserving aspect ratio with black padding."""
    h, w = arr.shape[:2]
    tw, th = size
    scale = min(tw / w, th / h)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    im = Image.fromarray(arr).resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (tw, th), (0, 0, 0))
    canvas.paste(im, ((tw - nw) // 2, (th - nh) // 2))
    return canvas


def make_contact_sheet(
    entries: list[tuple[np.ndarray, str]],   # (rgb_array, label)
    cols: int = 5,
    thumb_size: tuple[int, int] = CONTACT_THUMB_SIZE,
    title: str = "",
) -> Image.Image:
    """Build a contact sheet PIL image from a list of (rgb_array, label) pairs."""
    n = len(entries)
    if n == 0:
        img = Image.new("RGB", (400, 80), (30, 30, 30))
        ImageDraw.Draw(img).text((10, 30), "No images", fill=(200, 200, 200))
        return img

    rows = math.ceil(n / cols)
    tw, th = thumb_size
    label_h = 20
    header_h = 40 if title else 0
    total_w = cols * tw
    total_h = header_h + rows * (th + label_h)

    sheet = Image.new("RGB", (total_w, total_h), (20, 20, 20))
    draw = ImageDraw.Draw(sheet)

    if title:
        draw.text((8, 10), title, fill=(230, 230, 230))

    for idx, (arr, label) in enumerate(entries):
        row, col = divmod(idx, cols)
        x = col * tw
        y = header_h + row * (th + label_h)
        thumb = make_thumbnail(arr, thumb_size)
        sheet.paste(thumb, (x, y))
        # truncate label to fit
        short = label[-26:] if len(label) > 26 else label
        draw.text((x + 2, y + th + 2), short, fill=(180, 220, 180))

    return sheet


# ─── Detection heuristics ────────────────────────────────────────────────────

def h1_green_cyan_dominance(arr: np.ndarray) -> tuple[float, str]:
    """
    H1: Unnatural saturated green / cyan pixels.
    Tissue is red/pink; bright isolated green/cyan regions are annotation contours.
    Returns (score_contribution, detail).
    """
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    total = arr.shape[0] * arr.shape[1]

    # Pure green dominance: G > R+50, G > B+50, G > 100
    green_mask = ((g - r) > 50) & ((g - b) > 50) & (g > 100)
    # Cyan dominance: G > 120, B > 120, R < 80
    cyan_mask = (g > 120) & (b > 120) & (r < 80)
    # Combined anomalous pixels
    anomalous = (green_mask | cyan_mask).astype(np.uint8) * 255

    # Only count if they form connected components of >= 50 pixels
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(anomalous, connectivity=8)
    sig_area = sum(
        stats[i, cv2.CC_STAT_AREA]
        for i in range(1, n_labels)
        if stats[i, cv2.CC_STAT_AREA] >= 50
    )
    ratio = sig_area / total if total > 0 else 0.0

    score = 0.0
    if ratio > 0.02:    # > 2% of image is anomalously green/cyan
        score = 2.0
    elif ratio > 0.005: # > 0.5%
        score = 1.0

    detail = f"H1 green/cyan ratio={ratio:.4f} sig_area={sig_area} components={n_labels-1}"
    return score, detail


def h2_solid_color_components(arr: np.ndarray) -> tuple[float, str]:
    """
    H2: Large solid-color connected regions.
    Natural tissue always has texture; a colored overlay creates uniformly-colored
    connected regions with near-zero local variance.
    """
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    total = h * w

    # Local variance in 7x7 window -- regions with variance < 5 are suspiciously flat
    gray_f = gray.astype(np.float32)
    mean_f = cv2.blur(gray_f, (7, 7))
    sq_f   = cv2.blur(gray_f ** 2, (7, 7))
    var_f  = sq_f - mean_f ** 2

    # Flat AND not black (black endoscope border is normal)
    flat_mask = ((var_f < 5.0) & (gray > 15)).astype(np.uint8) * 255
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(flat_mask, connectivity=8)

    # Find significant flat components (>= 500 px, not a narrow strip)
    suspect = []
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        rect_w = stats[i, cv2.CC_STAT_WIDTH]
        rect_h = stats[i, cv2.CC_STAT_HEIGHT]
        if area >= 500:
            # Exclude very narrow strips (scale bars)
            aspect = max(rect_w, rect_h) / (min(rect_w, rect_h) + 1)
            if aspect < 8:   # not too elongated -- a rectangular block is suspicious
                suspect.append(area)

    sig_area = sum(suspect)
    ratio = sig_area / total if total > 0 else 0.0

    score = 0.0
    if ratio > 0.05 and len(suspect) >= 2:
        score = 2.0
    elif ratio > 0.02:
        score = 1.0

    detail = f"H2 flat_ratio={ratio:.4f} suspect_components={len(suspect)}"
    return score, detail


def h3_thin_bright_edge_network(arr: np.ndarray) -> tuple[float, str]:
    """
    H3: Dense thin-edge network not consistent with natural tissue.
    Drawn annotation contours / arrows produce very sharp, continuous thin edges.
    We detect these by:
      - Computing Canny edges
      - Checking the edge pixel density
      - Looking for very long contours (perimeter >> area -- thin closed curves)
    """
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    total = h * w

    # Canny with tight thresholds to pick up sharp artificial edges
    edges = cv2.Canny(gray, threshold1=80, threshold2=200)
    edge_density = edges.sum() / 255 / total

    # Find contours from the Canny image
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Drawn annotation contours: long perimeter, enclosed area
    thin_count = 0
    for c in contours:
        perim = cv2.arcLength(c, closed=False)
        area  = cv2.contourArea(c)
        # Very thin = perimeter >> sqrt(area)  (not a blob, but a line)
        if perim > 100 and area > 0 and (perim / (math.sqrt(area) + 1)) > 10:
            thin_count += 1

    score = 0.0
    if edge_density > 0.15 and thin_count > 5:
        score = 2.0
    elif edge_density > 0.12 and thin_count > 3:
        score = 1.0

    detail = f"H3 edge_density={edge_density:.4f} thin_contours={thin_count}"
    return score, detail


def h4_white_text_region(arr: np.ndarray) -> tuple[float, str]:
    """
    H4: Burned-in text or info overlays.
    Text is usually white or bright-grey on a dark background,
    concentrated in corners/edges of the frame.
    """
    h, w = arr.shape[:2]
    total = h * w

    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)

    # Bright nearly-white pixels
    white_mask = ((r > 210) & (g > 210) & (b > 210)).astype(np.uint8) * 255
    white_count = int(white_mask.sum() / 255)
    white_ratio = white_count / total

    # Are these concentrated near image edges (top 15%, bottom 15%)?
    border_h = max(1, int(h * 0.15))
    border_region = np.vstack([white_mask[:border_h, :], white_mask[-border_h:, :]])
    border_white = int(border_region.sum() / 255)
    border_ratio = border_white / (2 * border_h * w) if (2 * border_h * w) > 0 else 0.0

    # Text-like: white pixels form small isolated clusters (not big blobs)
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(white_mask, connectivity=8)
    small_text_blobs = sum(
        1 for i in range(1, n_labels)
        if 10 <= stats[i, cv2.CC_STAT_AREA] <= 300
    )

    score = 0.0
    if border_ratio > 0.05 and small_text_blobs > 20:
        score = 2.0
    elif border_ratio > 0.03 and small_text_blobs > 10:
        score = 1.0
    elif white_ratio > 0.08:   # Large white regions anywhere
        score = 1.0

    detail = (f"H4 white_ratio={white_ratio:.4f} border_ratio={border_ratio:.4f} "
              f"text_blobs={small_text_blobs}")
    return score, detail


def h5_rectangular_border_anomaly(arr: np.ndarray) -> tuple[float, str]:
    """
    H5: Rectangular scale bars or info boxes.
    Looks for high-contrast filled rectangles that are not the natural endoscope
    circular border (which is round, not rectangular).
    """
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    # Threshold to find very dark regions (potential borders)
    _, dark = cv2.threshold(gray, 20, 255, cv2.THRESH_BINARY_INV)

    # Find rectangles via contour approximation
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rect_count = 0
    for c in contours:
        area = cv2.contourArea(c)
        if area < 500:
            continue
        peri = cv2.arcLength(c, closed=True)
        approx = cv2.approxPolyDP(c, 0.04 * peri, closed=True)
        if len(approx) == 4:
            # It's roughly rectangular
            # Natural endoscope border is one large oval/circle -- not 4-sided
            rect_count += 1

    score = 0.0
    if rect_count >= 3:
        score = 2.0
    elif rect_count >= 1:
        score = 1.0

    detail = f"H5 suspicious_rectangles={rect_count}"
    return score, detail


def h6_yellow_red_annotation_marks(arr: np.ndarray) -> tuple[float, str]:
    """
    H6: Yellow or bright-red annotation marks (arrows, circles, ROI markers).
    Yellow is very rare in natural colonoscopy tissue but common in medical annotations.
    Bright red isolated from tissue context (very small connected clusters of pure red)
    is also common for annotation markers.
    """
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)
    total = arr.shape[0] * arr.shape[1]

    # Yellow: R > 180, G > 180, B < 80
    yellow_mask = ((r > 180) & (g > 180) & (b < 80)).astype(np.uint8) * 255
    # Pure bright red (not tissue): R > 200, G < 60, B < 60
    pure_red_mask = ((r > 200) & (g < 60) & (b < 60)).astype(np.uint8) * 255
    # Magenta / purple (very unnatural in tissue)
    magenta_mask = ((r > 150) & (b > 150) & (g < 80)).astype(np.uint8) * 255

    combined = cv2.bitwise_or(cv2.bitwise_or(yellow_mask, pure_red_mask), magenta_mask)
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(combined, connectivity=8)
    sig_components = [
        stats[i, cv2.CC_STAT_AREA]
        for i in range(1, n_labels)
        if stats[i, cv2.CC_STAT_AREA] >= 30
    ]
    sig_area = sum(sig_components)
    ratio = sig_area / total if total > 0 else 0.0

    yellow_px = int(yellow_mask.sum() / 255)
    pure_red_px = int(pure_red_mask.sum() / 255)
    magenta_px = int(magenta_mask.sum() / 255)

    score = 0.0
    if ratio > 0.01 or len(sig_components) >= 3:
        score = 2.0
    elif ratio > 0.003 or len(sig_components) >= 1:
        score = 1.0

    detail = (f"H6 yellow={yellow_px} pure_red={pure_red_px} magenta={magenta_px} "
              f"sig_components={len(sig_components)} ratio={ratio:.4f}")
    return score, detail


HEURISTICS = [
    ("H1_green_cyan",      h1_green_cyan_dominance),
    ("H2_solid_color",     h2_solid_color_components),
    ("H3_thin_edges",      h3_thin_bright_edge_network),
    ("H4_white_text",      h4_white_text_region),
    ("H5_rect_border",     h5_rectangular_border_anomaly),
    ("H6_annotation_mark", h6_yellow_red_annotation_marks),
]


def classify(total_score: float) -> str:
    if total_score >= OVERLAY_THRESHOLD:
        return "OVERLAY"
    elif total_score >= UNCERTAIN_THRESHOLD:
        return "UNCERTAIN"
    else:
        return "CLEAN"


def analyse_image(img_path: Path) -> dict:
    """Run all heuristics on one image. Returns per-heuristic scores + verdict."""
    arr = load_rgb(img_path)
    if arr is None:
        return {
            "readable": False,
            "verdict": "UNREADABLE",
            "total_score": None,
            "heuristic_scores": {},
            "heuristic_details": {},
        }

    heuristic_scores = {}
    heuristic_details = {}
    total_score = 0.0

    for name, fn in HEURISTICS:
        try:
            s, d = fn(arr)
        except Exception as exc:
            s, d = 0.0, f"ERROR: {exc}"
        heuristic_scores[name] = round(s, 4)
        heuristic_details[name] = d
        total_score += s

    return {
        "readable": True,
        "shape": list(arr.shape),
        "verdict": classify(total_score),
        "total_score": round(total_score, 4),
        "heuristic_scores": heuristic_scores,
        "heuristic_details": heuristic_details,
    }


# ─── Contact sheet builder ────────────────────────────────────────────────────

def build_contact_sheet(
    role: str,
    pairs: list[tuple[str, str]],
    results: dict[str, dict],
    root: Path,
    n_samples: int,
    out_dir: Path,
    thumb_size: tuple[int, int] = CONTACT_THUMB_SIZE,
) -> str:
    """Random sample contact sheet. Returns saved path."""
    rng = random.Random(RANDOM_SEED)
    sample_pairs = rng.sample(pairs, min(n_samples, len(pairs)))

    entries = []
    for img_rel, _ in sample_pairs:
        arr = load_rgb(root / img_rel)
        if arr is not None:
            verdict = results.get(img_rel, {}).get("verdict", "?")
            score   = results.get(img_rel, {}).get("total_score", "?")
            label = f"{Path(img_rel).name}|{verdict}|{score}"
            entries.append((arr, label))

    cols = min(5, len(entries))
    sheet = make_contact_sheet(entries, cols=cols, thumb_size=thumb_size,
                               title=f"{role} — random sample ({len(entries)} shown)")
    out_path = out_dir / f"contact_{role}.png"
    sheet.save(str(out_path))
    return str(out_path)


def build_flagged_sheet(
    flagged_entries: list[dict],   # list of result records with "image_rel"
    root: Path,
    out_dir: Path,
    thumb_size: tuple[int, int] = FLAGGED_THUMB_SIZE,
) -> str | None:
    """Contact sheet of all flagged (OVERLAY + UNCERTAIN) images."""
    if not flagged_entries:
        return None

    entries = []
    for rec in flagged_entries:
        arr = load_rgb(root / rec["image_rel"])
        if arr is not None:
            label = f"{Path(rec['image_rel']).name}|{rec['verdict']}|{rec['total_score']}"
            entries.append((arr, label))

    if not entries:
        return None

    cols = min(5, len(entries))
    sheet = make_contact_sheet(entries, cols=cols, thumb_size=thumb_size,
                               title=f"FLAGGED images ({len(entries)} total)")
    out_path = out_dir / "flagged_all.png"
    sheet.save(str(out_path))
    return str(out_path)


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Annotation overlay audit")
    parser.add_argument("--project-root", default=".", help="Project root")
    parser.add_argument("--contact-samples", type=int, default=20,
                        help="Number of random samples per contact sheet")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    out_dir = root / "results" / "overlays"
    cs_dir  = out_dir / "contact_sheets"
    cs_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / f"overlay_audit_{timestamp}.json"

    t0 = time.perf_counter()
    print("=" * 72)
    print("  OVERLAY AUDIT -- annotation detection via 6 heuristics")
    print("=" * 72)
    print(f"  Project root : {root}")
    print(f"  Output dir   : {out_dir}")
    print()

    # -- per-image result cache (image_rel -> analysis dict)
    image_cache: dict[str, dict] = {}

    # -- per-role report
    role_reports: dict[str, dict] = {}
    all_flagged: list[dict] = []   # OVERLAY + UNCERTAIN across train/val

    train_val_overlays: list[dict] = []

    for role, rel_path in MANIFEST_ROLES.items():
        tsv = root / rel_path
        print(f"\n[{role}] {rel_path}")

        if not tsv.exists():
            print(f"  ERROR: manifest not found -- skipping")
            role_reports[role] = {"error": "manifest not found"}
            continue

        pairs = read_manifest(tsv)
        print(f"  {len(pairs)} pairs")

        clean_list:    list[dict] = []
        overlay_list:  list[dict] = []
        uncertain_list: list[dict] = []
        unreadable_list: list[str] = []

        # Collect unique image paths for this role
        unique_imgs = list({img_rel for img_rel, _ in pairs})

        for i, img_rel in enumerate(unique_imgs):
            if (i + 1) % 100 == 0 or i == 0:
                print(f"  ... {i+1}/{len(unique_imgs)}")

            img_path = root / img_rel

            if not img_path.exists():
                unreadable_list.append(img_rel)
                continue

            if img_rel not in image_cache:
                image_cache[img_rel] = analyse_image(img_path)
            result = image_cache[img_rel]

            # Find the corresponding mask for this image
            mask_rels = [mask_rel for ir, mask_rel in pairs if ir == img_rel]
            mask_rel = mask_rels[0] if mask_rels else None

            record = {
                "manifest": role,
                "image_rel": img_rel,
                "mask_rel": mask_rel,
                "verdict": result["verdict"],
                "total_score": result["total_score"],
                "heuristic_scores": result.get("heuristic_scores", {}),
                "heuristic_details": result.get("heuristic_details", {}),
                "readable": result.get("readable", False),
                "shape": result.get("shape"),
            }

            if not result.get("readable"):
                unreadable_list.append(img_rel)
            elif result["verdict"] == "CLEAN":
                clean_list.append(record)
            elif result["verdict"] == "OVERLAY":
                overlay_list.append(record)
                all_flagged.append(record)
                if role in ("train", "val"):
                    train_val_overlays.append(record)
                print(f"  *** OVERLAY detected: {img_rel}  score={result['total_score']}")
                for h, s in result["heuristic_scores"].items():
                    if s > 0:
                        print(f"       {h}: {s}  {result['heuristic_details'][h]}")
            elif result["verdict"] == "UNCERTAIN":
                uncertain_list.append(record)
                all_flagged.append(record)
                print(f"  ~~~ UNCERTAIN: {img_rel}  score={result['total_score']}")

        print(f"  CLEAN={len(clean_list)}  OVERLAY={len(overlay_list)}  "
              f"UNCERTAIN={len(uncertain_list)}  UNREADABLE={len(unreadable_list)}")

        # Contact sheet for this role
        cs_path = build_contact_sheet(
            role, pairs, image_cache, root,
            args.contact_samples, cs_dir
        )
        print(f"  Contact sheet -> {cs_path}")

        role_reports[role] = {
            "manifest_path": str(tsv),
            "total_pairs": len(pairs),
            "unique_images": len(unique_imgs),
            "clean_count": len(clean_list),
            "overlay_count": len(overlay_list),
            "uncertain_count": len(uncertain_list),
            "unreadable_count": len(unreadable_list),
            "contact_sheet_path": cs_path,
            "confirmed_clean": [r["image_rel"] for r in clean_list],
            "confirmed_overlay": [
                {
                    "manifest": r["manifest"],
                    "image_path": r["image_rel"],
                    "mask_path": r["mask_rel"],
                    "reason": ", ".join(
                        f"{h}(score={s})" for h, s in r["heuristic_scores"].items() if s > 0
                    ),
                    "confidence": "HIGH" if r["total_score"] >= 4 else "MEDIUM",
                    "total_score": r["total_score"],
                    "heuristic_details": r["heuristic_details"],
                }
                for r in overlay_list
            ],
            "uncertain_manual_review": [
                {
                    "manifest": r["manifest"],
                    "image_path": r["image_rel"],
                    "mask_path": r["mask_rel"],
                    "reason": ", ".join(
                        f"{h}(score={s})" for h, s in r["heuristic_scores"].items() if s > 0
                    ),
                    "confidence": "LOW",
                    "total_score": r["total_score"],
                    "heuristic_details": r["heuristic_details"],
                }
                for r in uncertain_list
            ],
        }

    # -- Flagged contact sheet (all OVERLAY + UNCERTAIN)
    flagged_sheet_path = build_flagged_sheet(all_flagged, root, cs_dir)
    if flagged_sheet_path:
        print(f"\n  Flagged contact sheet -> {flagged_sheet_path}")

    # -- Final verdict
    elapsed = time.perf_counter() - t0
    training_blocked = len(train_val_overlays) > 0

    total_clean     = sum(r.get("clean_count", 0)    for r in role_reports.values())
    total_overlay   = sum(r.get("overlay_count", 0)  for r in role_reports.values())
    total_uncertain = sum(r.get("uncertain_count", 0) for r in role_reports.values())
    total_unique    = len(image_cache)

    print("\n" + "=" * 72)
    print("  SUMMARY")
    print("=" * 72)
    print(f"  Unique images analysed : {total_unique}")
    print(f"  CLEAN                  : {total_clean}")
    print(f"  OVERLAY                : {total_overlay}")
    print(f"  UNCERTAIN              : {total_uncertain}")
    print(f"  Elapsed                : {elapsed:.1f}s")

    if training_blocked:
        print(f"\n  STOP: {len(train_val_overlays)} confirmed overlay(s) found in train/val.")
        print("  Exact paths:")
        for rec in train_val_overlays:
            print(f"    [{rec['manifest']}] {rec['image_rel']}")
        print("  Do NOT proceed to training until these are manually reviewed.")
    else:
        print("\n  No confirmed overlays in train or val. Training not blocked by this check.")
        if total_uncertain > 0:
            print(f"  {total_uncertain} UNCERTAIN images require manual review of the contact sheets.")

    # -- Write JSON report
    report = {
        "schema_version": "1.0",
        "timestamp_utc": timestamp,
        "project_root": str(root),
        "thresholds": {
            "overlay": OVERLAY_THRESHOLD,
            "uncertain": UNCERTAIN_THRESHOLD,
        },
        "heuristics": [name for name, _ in HEURISTICS],
        "summary": {
            "total_unique_images_analysed": total_unique,
            "total_clean": total_clean,
            "total_overlay": total_overlay,
            "total_uncertain": total_uncertain,
            "elapsed_seconds": round(elapsed, 2),
            "training_blocked": training_blocked,
            "flagged_contact_sheet": flagged_sheet_path,
        },
        "per_role": role_reports,
        "train_val_overlay_paths": [
            {
                "manifest": r["manifest"],
                "image_path": r["image_rel"],
                "mask_path": r["mask_rel"],
                "reason": ", ".join(
                    f"{h}(score={s})" for h, s in r["heuristic_scores"].items() if s > 0
                ),
                "confidence": "HIGH" if r["total_score"] >= 4 else "MEDIUM",
                "total_score": r["total_score"],
            }
            for r in train_val_overlays
        ],
    }

    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    print(f"\n  JSON report -> {report_path}")

    return 1 if training_blocked else 0


if __name__ == "__main__":
    sys.exit(main())
