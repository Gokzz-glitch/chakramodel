import os
import cv2
import argparse
from glob import glob


def mask_to_bbox(mask):
    ys, xs = (mask > 0).nonzero()
    if len(xs) == 0 or len(ys) == 0:
        return None
    x1, x2 = xs.min(), xs.max()
    y1, y2 = ys.min(), ys.max()
    return x1, y1, x2, y2


def to_yolo_bbox(x1, y1, x2, y2, w, h):
    cx = ((x1 + x2) / 2.0) / w
    cy = ((y1 + y2) / 2.0) / h
    bw = (x2 - x1) / w
    bh = (y2 - y1) / h
    return cx, cy, bw, bh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images_dir", required=True, help="Path to images")
    ap.add_argument("--masks_dir", required=True, help="Path to masks")
    ap.add_argument("--labels_out", required=True, help="Path to YOLO labels output dir")
    ap.add_argument("--ext", default="png", help="Image extension (png/jpg)")
    args = ap.parse_args()

    os.makedirs(args.labels_out, exist_ok=True)
    images = sorted(glob(os.path.join(args.images_dir, f"*.{args.ext}")))
    if not images:
        print("No images found.")
        return

    converted = 0
    skipped = 0
    for img_path in images:
        name = os.path.splitext(os.path.basename(img_path))[0]
        mask_path = os.path.join(args.masks_dir, f"{name}.{args.ext}")
        if not os.path.exists(mask_path):
            skipped += 1
            continue

        img = cv2.imread(img_path)
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if img is None or mask is None:
            skipped += 1
            continue

        h, w = img.shape[:2]
        bbox = mask_to_bbox(mask)
        out_path = os.path.join(args.labels_out, f"{name}.txt")

        if bbox is None:
            open(out_path, "w").close()
            skipped += 1
            continue

        x1, y1, x2, y2 = bbox
        cx, cy, bw, bh = to_yolo_bbox(x1, y1, x2, y2, w, h)

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"0 {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
        converted += 1

    print(f"Done. Converted: {converted}, Skipped: {skipped}")


if __name__ == "__main__":
    main()