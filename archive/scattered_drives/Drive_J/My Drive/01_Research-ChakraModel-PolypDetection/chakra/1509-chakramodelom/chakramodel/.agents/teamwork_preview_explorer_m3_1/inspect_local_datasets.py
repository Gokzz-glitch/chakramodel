from pathlib import Path
import cv2

root = Path(r"m:\chakramodel\data")
datasets = ["kvasir-seg", "cvc-clinicdb", "cvc-colondb", "cvc-300", "etis-larib"]

print("="*80)
print(f"{'DATASET':<15} | {'IMAGES':<8} | {'MASKS':<8} | {'SAMPLE IMG SHAPE':<18} | {'SAMPLE MASK SHAPE':<18}")
print("="*80)

for d in datasets:
    img_dir = root / d / "images"
    mask_dir = root / d / "masks"
    if not img_dir.exists():
        print(f"{d:<15} | NOT FOUND")
        continue
    imgs = list(img_dir.glob("*"))
    masks = list(mask_dir.glob("*")) if mask_dir.exists() else []
    
    sample_img_shape = "N/A"
    sample_mask_shape = "N/A"
    if imgs:
        im = cv2.imread(str(imgs[0]))
        if im is not None:
            sample_img_shape = str(im.shape)
    if masks:
        mk = cv2.imread(str(masks[0]), cv2.IMREAD_GRAYSCALE)
        if mk is not None:
            sample_mask_shape = str(mk.shape)
            
    print(f"{d:<15} | {len(imgs):<8} | {len(masks):<8} | {sample_img_shape:<18} | {sample_mask_shape:<18}")

print("="*80)
