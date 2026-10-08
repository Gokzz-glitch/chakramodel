import os
import torch
import cv2
import numpy as np
from torch.utils.data import DataLoader

import sys
sys.path.insert(0, os.path.abspath("src"))

from chakra_transformer.transformer_segmenter import ChakraTransformerSegmenter
from train_pranet import KvasirSEGDataset
from metrics_engine_v2 import MetricsEngineV2

def calculate_topological_connectivity(pred_mask):
    """
    Given a binary prediction mask (H, W), calculate if it has exactly 1 connected component (polyp).
    Returns 1 if single component, 0 if fragmented (multiple components) or empty.
    """
    pred_np = pred_mask.cpu().numpy().astype(np.uint8)
    num_labels, labels = cv2.connectedComponents(pred_np)
    # num_labels includes the background (0), so 2 means background + 1 component.
    if num_labels == 2:
        return 1
    return 0

from pathlib import Path

def evaluate_dataset(model, dataset_path, device, name):
    print(f"\n--- Evaluating Zero-Shot on {name} ---")
    img_dir = Path(dataset_path) / "images"
    mask_dir = Path(dataset_path) / "masks"
    
    if not img_dir.exists():
        print(f"Dataset path missing: {img_dir}")
        return
        
    dataset = KvasirSEGDataset(img_dir, mask_dir, img_size=384, augment=False)
    dataloader = DataLoader(dataset, batch_size=4, shuffle=False, num_workers=0)
    
    metrics_engine = MetricsEngineV2()
    
    total_dice = 0
    total_miou = 0
    
    total_single_components = 0
    total_masks = 0
    
    model.eval()
    with torch.no_grad():
        for i, (images, masks) in enumerate(dataloader):
            images = images.to(device)
            masks = masks.to(device)
            
            outputs = model(images)
            preds = torch.sigmoid(outputs)
            
            for b in range(images.size(0)):
                res = metrics_engine.compute_all(preds[b:b+1], masks[b:b+1])
                total_dice += res["Dice"]
                total_miou += res["mIoU"]
                
                # Binarize prediction at 0.5 for topological check
                binary_pred = (preds[b, 0] > 0.5).float()
                total_single_components += calculate_topological_connectivity(binary_pred)
                total_masks += 1
                
    avg_dice = total_dice / total_masks
    avg_miou = total_miou / total_masks
    topo_score = (total_single_components / total_masks) * 100
    
    print(f"Test DSC: {avg_dice:.4f}")
    print(f"Test mIoU: {avg_miou:.4f}")
    print(f"Topological Single-Component Score: {topo_score:.2f}%")

if __name__ == "__main__":
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Initialize Model
    model = ChakraTransformerSegmenter(backbone_name='vit_large_patch16_384', pretrained=False).to(device)
    
    # Load Pre-trained weights (trained on Kvasir-SEG)
    weights_path = "weights/chakra_transformer_best.pth"
    if os.path.exists(weights_path):
        print(f"Loading weights from {weights_path}")
        state_dict = torch.load(weights_path, map_location=device)
        model.load_state_dict(state_dict)
    else:
        print("ERROR: Weights not found!")
        sys.exit(1)
        
    evaluate_dataset(model, r"data\cvc-clinicdb", device, "CVC-ClinicDB")
    evaluate_dataset(model, r"data\etis-larib", device, "ETIS-Larib")
