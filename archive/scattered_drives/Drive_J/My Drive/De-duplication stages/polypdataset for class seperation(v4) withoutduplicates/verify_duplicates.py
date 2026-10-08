#!/usr/bin/env python3
"""
Independent check of the output folder made by find_duplicates.py.
It does NOT reuse the first script's logic: it re-hashes every kept image with a
different algorithm (BLAKE2b, no size shortcut) and answers three questions:

  CHECK 1  Is any duplicate still left among the kept (original) images?
  CHECK 2  Is every image in the 'duplicates' folders a byte-identical copy of a kept image?
  CHECK 3  Does every moved duplicate image have its mask moved too? Which masks were left behind?

Read-only: nothing in the folder is changed.
"""

import difflib
import filecmp
import hashlib
import os
import sys
from collections import defaultdict

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif", ".webp"}
CLASSES = {"positive": "duplicates of positive", "negativeonly": "duplicates of negative"}
MASK_SUFFIXES = ("_mask", "-mask")   # same as in find_duplicates.py
SHOW = 25   # max items printed per list


def blake(path):
    h = hashlib.blake2b()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def list_images(root, skip_dir=None):
    found = []
    for dp, dns, fns in os.walk(root):
        if skip_dir:
            dns[:] = [d for d in dns if os.path.join(dp, d) != skip_dir]
        found += [os.path.join(dp, f) for f in fns if os.path.splitext(f)[1].lower() in IMAGE_EXTS]
    return found


def is_mask(path):
    return os.path.basename(os.path.dirname(path)).lower() in ("masks", "mask")


def in_images_folder(path):
    return os.path.basename(os.path.dirname(path)).lower() == "images"


def stem(path):
    s = os.path.splitext(os.path.basename(path))[0]
    if is_mask(path):
        for suf in MASK_SUFFIXES:
            if s.endswith(suf):
                s = s[:-len(suf)]
    return s


def dataset_key(path):
    """(dataset folder, file stem) - the folder that holds both images/ and masks/."""
    return (os.path.dirname(os.path.dirname(path)), stem(path))


def show(items, indent="    "):
    for it in items[:SHOW]:
        print(f"{indent}{it}")
    if len(items) > SHOW:
        print(f"{indent}... and {len(items) - SHOW} more")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else input("Enter the OUTPUT folder made by find_duplicates.py: ")
    out = os.path.abspath(os.path.expanduser(out.strip().strip('"')))
    if not os.path.isdir(out):
        sys.exit(f"Error: '{out}' is not a valid folder.")

    top = {d.lower(): d for d in os.listdir(out) if os.path.isdir(os.path.join(out, d))}
    summary = []

    for key, dup_name in CLASSES.items():
        if key not in top:
            continue
        cls_root = os.path.join(out, top[key])
        dup_root = os.path.join(cls_root, dup_name)

        kept_all = list_images(cls_root, skip_dir=dup_root)
        kept_imgs = [p for p in kept_all if not is_mask(p)]
        kept_masks = [p for p in kept_all if is_mask(p)]
        dup_all = list_images(dup_root) if os.path.isdir(dup_root) else []
        dup_imgs = [p for p in dup_all if not is_mask(p)]
        dup_masks = [p for p in dup_all if is_mask(p)]

        print("\n" + "=" * 70)
        print(key.upper())
        print("=" * 70)
        print(f"Kept images: {len(kept_imgs)} | kept masks: {len(kept_masks)} | "
              f"duplicate images: {len(dup_imgs)} | duplicate masks: {len(dup_masks)}")

        # ---- CHECK 1: no duplicates left among kept images ----
        print(f"\nCHECK 1: hashing all {len(kept_imgs)} kept images (no size shortcut)...")
        by_hash = defaultdict(list)
        for p in kept_imgs:
            by_hash[blake(p)].append(p)
        leftover = [g for g in by_hash.values() if len(g) > 1]
        ok1 = not leftover
        print(f"  Identical images still among the kept ones: {sum(len(g) - 1 for g in leftover)}"
              f"  ->  {'PASS' if ok1 else 'FAIL'}")
        for g in leftover[:SHOW]:
            print("    group:", *[os.path.relpath(x, out) for x in g], sep="\n      ")

        # ---- CHECK 2: every moved image is a true duplicate ----
        print(f"\nCHECK 2: confirming each of the {len(dup_imgs)} moved images matches a kept image byte-for-byte...")
        bad = []
        for p in dup_imgs:
            match = by_hash.get(blake(p))
            if not (match and filecmp.cmp(match[0], p, shallow=False)):
                bad.append(os.path.relpath(p, out))
        ok2 = not bad
        print(f"  Verified true duplicates: {len(dup_imgs) - len(bad)} / {len(dup_imgs)}"
              f"  ->  {'PASS' if ok2 else 'FAIL'}")
        show(bad)

        # ---- CHECK 3: masks (positive only) - compares COUNTS per folder, not file names ----
        ok3 = True
        if key == "positive":
            def folder_counts(imgs, masks):
                ci, cm = defaultdict(int), defaultdict(int)
                for p in imgs:
                    if in_images_folder(p):
                        ci[os.path.dirname(os.path.dirname(p))] += 1
                for m in masks:
                    cm[os.path.dirname(os.path.dirname(m))] += 1
                return ci, cm

            mismatch = []
            for where, imgs, masks in (("kept", kept_imgs, kept_masks), ("moved", dup_imgs, dup_masks)):
                ci, cm = folder_counts(imgs, masks)
                for d in sorted(set(ci) | set(cm)):
                    if ci[d] != cm[d]:
                        mismatch.append((where, os.path.relpath(d, out), ci[d], cm[d]))
            ok3 = not mismatch
            print("\nCHECK 3: masks (image count vs mask count in every folder)")
            print(f"  Kept   : {len(kept_imgs)} images, {len(kept_masks)} masks")
            print(f"  Moved  : {len(dup_imgs)} images, {len(dup_masks)} masks")
            print(f"  Folders where images != masks: {len(mismatch)}  ->  {'PASS' if ok3 else 'ATTENTION'}")
            for where, d, ni, nm in mismatch[:SHOW]:
                print(f"    [{where}] {d}: {ni} images vs {nm} masks")

            if mismatch:   # help find the unpaired files
                dup_mask_keys = {dataset_key(m) for m in dup_masks}
                missing = [p for p in dup_imgs if in_images_folder(p) and dataset_key(p) not in dup_mask_keys]
                for p in missing[:SHOW]:
                    rel_dir = cls_root + os.path.dirname(os.path.dirname(p))[len(dup_root):]
                    names = {os.path.basename(m): m for m in kept_masks
                             if os.path.dirname(os.path.dirname(m)) == rel_dir}
                    close = difflib.get_close_matches(os.path.basename(p), list(names), n=3, cutoff=0.0)
                    print(f"\n    moved image with no moved mask : {os.path.relpath(p, out)}")
                    for c in close:
                        print(f"      possible mask left behind    : {os.path.relpath(names[c], out)}")

        summary.append((key, ok1, ok2, ok3))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for key, ok1, ok2, ok3 in summary:
        print(f"{key:13s} check1 {'PASS' if ok1 else 'FAIL'} | check2 {'PASS' if ok2 else 'FAIL'}"
              f" | check3 {'PASS' if ok3 else 'ATTENTION'}")


if __name__ == "__main__":
    main()
