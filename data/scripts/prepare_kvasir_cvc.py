import os
import shutil
import random
import argparse
from glob import glob


def ensure(p):
    os.makedirs(p, exist_ok=True)


def copy_pair(img_path, label_path, out_img_dir, out_lbl_dir):
    shutil.copy2(img_path, os.path.join(out_img_dir, os.path.basename(img_path)))
    shutil.copy2(label_path, os.path.join(out_lbl_dir, os.path.basename(label_path)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images_dir", required=True)
    ap.add_argument("--labels_dir", required=True)
    ap.add_argument("--out_root", default="data/processed")
    ap.add_argument("--train", type=float, default=0.8)
    ap.add_argument("--val", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ext", default="png")
    args = ap.parse_args()

    random.seed(args.seed)
    assert 0 < args.train < 1
    assert 0 <= args.val < 1
    assert args.train + args.val < 1

    all_imgs = sorted(glob(os.path.join(args.images_dir, f"*.{args.ext}")))
    pairs = []
    for img in all_imgs:
        stem = os.path.splitext(os.path.basename(img))[0]
        lbl = os.path.join(args.labels_dir, f"{stem}.txt")
        if os.path.exists(lbl):
            pairs.append((img, lbl))

    random.shuffle(pairs)
    n = len(pairs)
    n_train = int(n * args.train)
    n_val = int(n * args.val)

    train_pairs = pairs[:n_train]
    val_pairs = pairs[n_train:n_train + n_val]
    test_pairs = pairs[n_train + n_val:]

    for split in ["train", "val", "test"]:
        ensure(os.path.join(args.out_root, "images", split))
        ensure(os.path.join(args.out_root, "labels", split))

    for img, lbl in train_pairs:
        copy_pair(img, lbl,
                  os.path.join(args.out_root, "images/train"),
                  os.path.join(args.out_root, "labels/train"))

    for img, lbl in val_pairs:
        copy_pair(img, lbl,
                  os.path.join(args.out_root, "images/val"),
                  os.path.join(args.out_root, "labels/val"))

    for img, lbl in test_pairs:
        copy_pair(img, lbl,
                  os.path.join(args.out_root, "images/test"),
                  os.path.join(args.out_root, "labels/test"))

    print(f"Prepared dataset at: {args.out_root}")
    print(f"train={len(train_pairs)}, val={len(val_pairs)}, test={len(test_pairs)}")


if __name__ == "__main__":
    main()