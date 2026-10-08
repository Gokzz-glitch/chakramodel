# ============================================================
# ChakraNet Combination #4: DiffusionAug-PraNet
# ============================================================
# RUN THIS ON: Kaggle (Free T4, 16GB VRAM) or Colab
#
# What this does:
#   1. Loads a pre-trained diffusion model (Stable Diffusion + ControlNet)
#   2. Takes polyp MASKS from Kvasir-SEG as input
#   3. Generates realistic synthetic polyp IMAGES matching those masks
#   4. Filters synthetic images using MC Dropout uncertainty
#   5. Saves the filtered dataset for retraining on your local laptop
#
# HOW TO USE:
#   Step 1: Upload this notebook to Kaggle or Colab
#   Step 2: Upload your trained weights (pranet_kvasir_best.pth) 
#   Step 3: Upload Kvasir-SEG masks folder
#   Step 4: Run all cells
#   Step 5: Download the filtered synthetic dataset
# ============================================================

# ─── Cell 1: Install Dependencies ────────────────────────────
# !pip install -q diffusers transformers accelerate torch torchvision opencv-python-headless

import os
import sys
import cv2
import numpy as np
import torch
from pathlib import Path

print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")

# ─── Cell 2: Setup Directories ──────────────────────────────
# On Kaggle: /kaggle/working/
# On Colab: /content/
BASE_DIR = Path(r"m:\chakramodel")
MASKS_DIR = BASE_DIR / "data" / "kvasir-seg" / "masks"
OUTPUT_DIR = BASE_DIR / "synthetic_polyps"
OUTPUT_DIR.mkdir(exist_ok=True)
(OUTPUT_DIR / "images").mkdir(exist_ok=True)
(OUTPUT_DIR / "masks").mkdir(exist_ok=True)

print(f"Base: {BASE_DIR}")
print(f"Masks: {MASKS_DIR}")
print(f"Output: {OUTPUT_DIR}")

# ─── Cell 3: Load Diffusion Model ───────────────────────────
from diffusers import StableDiffusionControlNetPipeline, ControlNetModel
from diffusers import UniPCMultistepScheduler

print("Loading ControlNet model (this takes 2-3 minutes)...")

# ControlNet conditioned on Canny edges (closest to polyp boundaries)
controlnet = ControlNetModel.from_pretrained(
    "lllyasviel/control_v11p_sd15_canny",
    torch_dtype=torch.float16
)

pipe = StableDiffusionControlNetPipeline.from_pretrained(
    "stable-diffusion-v1-5/stable-diffusion-v1-5",
    controlnet=controlnet,
    torch_dtype=torch.float16,
    safety_checker=None
)

pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config)
pipe.enable_model_cpu_offload()  # Saves VRAM by offloading to CPU when not needed
pipe.enable_xformers_memory_efficient_attention()  # Further VRAM savings

print("✅ Diffusion model loaded!")

# ─── Cell 4: Generate Synthetic Polyps ───────────────────────
from PIL import Image

PROMPT = "endoscopic colonoscopy image showing a colorectal polyp, medical imaging, clinical photograph, mucosal tissue, realistic lighting"
NEGATIVE = "cartoon, drawing, illustration, blurry, low quality, text, watermark"

def mask_to_canny_control(mask_path, size=512):
    """Convert a binary polyp mask to a Canny edge map for ControlNet."""
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        return None
    mask = cv2.resize(mask, (size, size))
    # Create edge map from mask boundary
    edges = cv2.Canny(mask, 50, 150)
    # Dilate slightly to make edges more visible to ControlNet
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)
    return Image.fromarray(edges)

def generate_synthetic_batch(mask_paths, n_per_mask=2, size=512):
    """Generate synthetic polyp images from masks."""
    generated = []
    
    for i, mask_path in enumerate(mask_paths):
        control_image = mask_to_canny_control(mask_path, size)
        if control_image is None:
            continue
        
        for j in range(n_per_mask):
            # Generate with different seeds for variety
            generator = torch.Generator(device="cpu").manual_seed(i * 100 + j)
            
            result = pipe(
                prompt=PROMPT,
                negative_prompt=NEGATIVE,
                image=control_image,
                num_inference_steps=20,  # Fast generation
                guidance_scale=7.5,
                controlnet_conditioning_scale=0.8,
                generator=generator,
            )
            
            synth_img = result.images[0]
            synth_np = np.array(synth_img)
            
            # Save
            img_name = f"synth_{mask_path.stem}_{j}.png"
            cv2.imwrite(str(OUTPUT_DIR / "images" / img_name), cv2.cvtColor(synth_np, cv2.COLOR_RGB2BGR))
            
            # Copy the original mask
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            mask = cv2.resize(mask, (size, size))
            cv2.imwrite(str(OUTPUT_DIR / "masks" / img_name), mask)
            
            generated.append(img_name)
            
        if (i + 1) % 10 == 0:
            print(f"  Generated {(i+1) * n_per_mask}/{len(mask_paths) * n_per_mask} images...")
    
    return generated

# Get all mask paths
mask_paths = sorted(MASKS_DIR.glob("*.jpg")) + sorted(MASKS_DIR.glob("*.png"))
print(f"Found {len(mask_paths)} masks")

# Generate 2 synthetic images per mask (1000 masks → 2000 synthetic images)
# Adjust n_per_mask based on your time budget
generated = generate_synthetic_batch(mask_paths[:500], n_per_mask=2)
print(f"\n✅ Generated {len(generated)} synthetic polyp images!")

# ─── Cell 5: Filter with MC Dropout Uncertainty ─────────────
# Upload pranet_kvasir_best.pth to BASE_DIR before running this cell

# NOTE: You need to upload pranet_segmenter.py and the weights file
# Copy these from your local laptop:
#   - src/pranet_segmenter.py
#   - weights/pranet_kvasir_best.pth

print("\n📊 Filtering synthetic images with MC Dropout uncertainty...")
print("Upload pranet_segmenter.py and pranet_kvasir_best.pth first!")
print("Then uncomment and run the filtering code below.")

"""
# Uncomment after uploading model files:

sys.path.insert(0, str(BASE_DIR))
from pranet_segmenter import PraNetMicroRefiner

device = torch.device("cuda")
model = PraNetMicroRefiner(channels=24).to(device)
model.load_state_dict(torch.load(BASE_DIR / "pranet_kvasir_best.pth", map_location=device))
model.eval()

KEEP_DIR = OUTPUT_DIR / "filtered"
(KEEP_DIR / "images").mkdir(parents=True, exist_ok=True)
(KEEP_DIR / "masks").mkdir(parents=True, exist_ok=True)

kept = 0
discarded = 0
mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)

for img_name in generated:
    img_path = OUTPUT_DIR / "images" / img_name
    img = cv2.imread(str(img_path))
    if img is None:
        continue
    
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (352, 352))
    tensor = torch.from_numpy(resized).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    tensor = (tensor - mean) / std
    tensor = tensor.to(device)
    
    # MC Dropout: 8 passes
    model.enable_mc_dropout()
    probs = []
    with torch.no_grad():
        for _ in range(8):
            logits = model(tensor)
            probs.append(torch.sigmoid(logits).squeeze().cpu().numpy())
    model.mc_dropout = False
    
    variance = np.var(np.stack(probs), axis=0)
    mean_uncertainty = float(np.mean(variance))
    
    # KEEP images where model is CONFIDENT (low uncertainty = realistic looking)
    if mean_uncertainty < 0.05:  # Threshold — tune this
        import shutil
        shutil.copy2(img_path, KEEP_DIR / "images" / img_name)
        shutil.copy2(OUTPUT_DIR / "masks" / img_name, KEEP_DIR / "masks" / img_name)
        kept += 1
    else:
        discarded += 1

print(f"Kept: {kept}, Discarded: {discarded}")
print(f"Acceptance rate: {kept/(kept+discarded)*100:.1f}%")
"""

# ─── Cell 6: Download Results ───────────────────────────────
# On Kaggle: Results auto-save to /kaggle/working/synthetic_polyps/
# On Colab: 
#   from google.colab import files
#   !zip -r synthetic_polyps.zip synthetic_polyps/
#   files.download('synthetic_polyps.zip')

print("\n✅ DONE! Download the 'synthetic_polyps' folder to your local laptop.")
print("Then on your laptop, run:")
print("  python src/train_pranet.py --epochs 200 --batch 4 --data_dir data/kvasir-aug")
