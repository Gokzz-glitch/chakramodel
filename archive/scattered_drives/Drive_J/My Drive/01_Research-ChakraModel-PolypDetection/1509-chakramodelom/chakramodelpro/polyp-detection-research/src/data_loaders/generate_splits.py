import os
import random
from pathlib import Path

def generate_splits(
    data_dir: str = "data/raw/kvasir-seg/images",
    output_dir: str = "data/processed",
    train_ratio: float = 0.9,
    seed: int = 42
):
    """
    Scans the dataset directory and generates train/test split text files.
    Standard Kvasir-SEG split is 900 train / 100 test.
    """
    random.seed(seed)
    
    # Ensure paths are absolute or relative to the project root
    project_root = Path(__file__).resolve().parents[2]
    images_dir = project_root / data_dir
    processed_dir = project_root / output_dir
    test_splits_dir = processed_dir / "test_splits"
    
    processed_dir.mkdir(parents=True, exist_ok=True)
    test_splits_dir.mkdir(parents=True, exist_ok=True)
    
    if not images_dir.exists():
        raise FileNotFoundError(f"Images directory not found at {images_dir}")
        
    # Get all image filenames
    valid_exts = {".jpg", ".png", ".jpeg"}
    images = [f.name for f in images_dir.iterdir() if f.is_file() and f.suffix.lower() in valid_exts]
    
    if len(images) == 0:
        raise ValueError(f"No images found in {images_dir}")
        
    images.sort()
    random.shuffle(images)
    
    # Kvasir-SEG has 1000 images, standard split is 900/100
    num_train = int(len(images) * train_ratio)
    train_images = images[:num_train]
    test_images = images[num_train:]
    
    train_file = processed_dir / "train.txt"
    test_file = test_splits_dir / "kvasir_test.txt"
    
    # For train.txt, prefix with dataset name to support multi-dataset training later
    with open(train_file, "w") as f:
        for img in train_images:
            f.write(f"kvasir-seg/images/{img}\n")
            
    with open(test_file, "w") as f:
        for img in test_images:
            f.write(f"kvasir-seg/images/{img}\n")
            
    print(f"Split generated successfully:")
    print(f"Total images: {len(images)}")
    print(f"Train split ({len(train_images)} images) -> {train_file}")
    print(f"Test split ({len(test_images)} images) -> {test_file}")

if __name__ == "__main__":
    generate_splits()
