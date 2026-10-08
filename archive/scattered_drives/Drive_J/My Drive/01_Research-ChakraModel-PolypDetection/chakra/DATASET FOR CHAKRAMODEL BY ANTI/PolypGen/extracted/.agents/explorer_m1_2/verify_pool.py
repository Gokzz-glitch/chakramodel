import json
from pathlib import Path
from collections import Counter
from PIL import Image

DATASET_ROOT = Path(r"J:\My Drive\DATASET FOR CHAKRAMODEL BY ANTI\PolypGen\extracted\PolypGen2021_MultiCenterData_v3")

def verify_images_all_positive():
    print("--- Verifying imagesAll_positive contents ---", flush=True)
    all_pos_dir = DATASET_ROOT / "imagesAll_positive"
    all_pos_files = {f.name for f in all_pos_dir.iterdir() if f.is_file() and not f.name.startswith(".")}
    
    # Collect all single frame positive images
    single_frame_images = set()
    for c in range(1, 7):
        c_img_dir = DATASET_ROOT / f"data_C{c}" / f"images_C{c}"
        for f in c_img_dir.iterdir():
            if f.is_file() and not f.name.startswith("."):
                single_frame_images.add(f.name)
                
    # Collect all sequence positive images
    seq_pos_images = set()
    pos_dir = DATASET_ROOT / "sequenceData" / "positive"
    for s_p in pos_dir.iterdir():
        if not s_p.is_dir():
            continue
        img_d = next((d for d in s_p.iterdir() if d.name.startswith("images_")), None)
        if img_d:
            for f in img_d.iterdir():
                if f.is_file() and not f.name.startswith("."):
                    seq_pos_images.add(f.name)
                    
    combined = single_frame_images | seq_pos_images
    print(f"Single frame unique images: {len(single_frame_images)}")
    print(f"Sequence positive unique images: {len(seq_pos_images)}")
    print(f"Single + Sequence overlap: {len(single_frame_images & seq_pos_images)}")
    print(f"Combined expected: {len(combined)}")
    print(f"Actual in imagesAll_positive: {len(all_pos_files)}")
    print(f"Difference (in combined but not in imagesAll_positive): {len(combined - all_pos_files)}")
    print(f"Difference (in imagesAll_positive but not in combined): {len(all_pos_files - combined)}")
    if combined - all_pos_files:
        print(f"  Sample missing from imagesAll_positive: {list(combined - all_pos_files)[:5]}")
    if all_pos_files - combined:
        print(f"  Sample extra in imagesAll_positive: {list(all_pos_files - combined)[:5]}")

    # Inspect resolutions across all positive sequences
    print("\n--- Inspecting positive sequence image resolutions ---", flush=True)
    seq_res = Counter()
    for s_p in sorted(pos_dir.iterdir()):
        if not s_p.is_dir():
            continue
        img_d = next((d for d in s_p.iterdir() if d.name.startswith("images_")), None)
        if img_d:
            first_f = next((f for f in img_d.iterdir() if f.is_file() and not f.name.startswith(".")), None)
            if first_f:
                with Image.open(first_f) as im:
                    seq_res[f"{im.size[0]}x{im.size[1]}"] += len(list(img_d.glob("*.jpg")))
                    print(f"  {s_p.name}: {first_f.name} resolution={im.size[0]}x{im.size[1]}, count={len(list(img_d.glob('*.jpg')))}")
    print(f"Positive sequence resolution summary: {dict(seq_res)}")

    # Inspect resolutions across negative sequences
    print("\n--- Inspecting negative sequence image resolutions ---", flush=True)
    neg_dir = DATASET_ROOT / "sequenceData" / "negativeOnly"
    neg_res = Counter()
    for s_p in sorted(neg_dir.iterdir()):
        if not s_p.is_dir():
            continue
        first_f = next((f for f in s_p.iterdir() if f.is_file() and not f.name.startswith(".")), None)
        if first_f:
            with Image.open(first_f) as im:
                n_files = len(list(s_p.glob("*.jpg")))
                neg_res[f"{im.size[0]}x{im.size[1]}"] += n_files
                print(f"  {s_p.name}: {first_f.name} resolution={im.size[0]}x{im.size[1]}, count={n_files}")
    print(f"Negative sequence resolution summary: {dict(neg_res)}")

if __name__ == "__main__":
    verify_images_all_positive()
