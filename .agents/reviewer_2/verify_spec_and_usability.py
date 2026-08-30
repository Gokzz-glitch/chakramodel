import json
import os
import sys
import ast
import re

sys.stdout.reconfigure(encoding='utf-8')

NOTEBOOKS_DIR = r"m:\chakramodel\notebooks"
NOTEBOOKS = [
    "Combo1_ChakraNet_Focal.ipynb",
    "Combo2_Topo_ChakraNet.ipynb",
    "Combo3_AdaBN_ChakraNet.ipynb",
    "Combo4_DiffusionAug_ChakraNet.ipynb",
    "Combo5_Federated_ChakraNet.ipynb",
    "Combo6_ChakraTransformer.ipynb",
]

def detailed_inspection():
    report = []
    
    for nb_name in NOTEBOOKS:
        nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
            
        cells = nb.get("cells", [])
        
        info = {
            "notebook": nb_name,
            "cells_count": len(cells),
            "cells_structure": [],
            "backbone_details": [],
            "yolo_details": [],
            "dataloader_configs": [],
            "dataset_pipeline": [],
            "loss_functions": [],
            "training_loop": [],
            "eval_metrics": [],
            "external_repos": [],
            "integrity_checks": [],
        }
        
        for idx, cell in enumerate(cells):
            c_type = cell.get("cell_type")
            source = "".join(cell.get("source", []))
            lines = source.splitlines()
            header = lines[0] if lines else ""
            info["cells_structure"].append({"cell_idx": idx, "type": c_type, "header": header[:80]})
            
            # Check external repos
            if "git clone" in source:
                info["external_repos"].append(f"Cell {idx}: found 'git clone'")
                
            # Check backbones
            for l in lines:
                if any(k in l.lower() for k in ["resnet101", "vit_large", "vit_base", "yolov8"]):
                    info["backbone_details"].append(f"Cell {idx}: {l.strip()}")
                if "yolo" in l.lower() and any(k in l.lower() for k in ["yolov8x", "yolov8n", "yolo(", "yolo ="]):
                    info["yolo_details"].append(f"Cell {idx}: {l.strip()}")
                if "dataloader(" in l.lower() or "batch_size" in l.lower() or "num_workers" in l.lower():
                    if any(k in l.lower() for k in ["batch_size", "num_workers", "dataloader", "pin_memory"]):
                        info["dataloader_configs"].append(f"Cell {idx}: {l.strip()}")
                if any(k in l.lower() for k in ["simula", "zenodo", "huggingface", "kvasir-seg.zip", "setup_kvasir_seg_dataset"]):
                    info["dataset_pipeline"].append(f"Cell {idx}: {l.strip()}")
                if any(k in l.lower() for k in ["dicefocalloss", "topologicalloss", "conformal", "loss =", "criterion ="]):
                    info["loss_functions"].append(f"Cell {idx}: {l.strip()}")
                if any(k in l.lower() for k in ["scaler.step", "optimizer.step", "autocast", "backward()"]):
                    info["training_loop"].append(f"Cell {idx}: {l.strip()}")
                if any(k in l.lower() for k in ["dice", "dsc", "iou", "miou", "precision", "recall", "fps", "conformal"]):
                    if "def " in l or "class " in l or "print(" in l and any(m in l for m in ["DSC", "mIoU", "FPS", "Coverage"]):
                        info["eval_metrics"].append(f"Cell {idx}: {l.strip()}")
                        
        report.append(info)
        
    return report

if __name__ == "__main__":
    rep = detailed_inspection()
    for item in rep:
        print("=" * 90)
        print(f"NOTEBOOK: {item['notebook']} ({item['cells_count']} cells)")
        print("=" * 90)
        print("\n--- Cell Structure ---")
        for cs in item['cells_structure']:
            print(f"  [{cs['cell_idx']}] {cs['type']}: {cs['header']}")
            
        print("\n--- Backbone Details ---")
        for bd in set(item['backbone_details']):
            print(f"  {bd}")
            
        if item['yolo_details']:
            print("\n--- YOLO Details ---")
            for yd in set(item['yolo_details']):
                print(f"  {yd}")
                
        print("\n--- DataLoader Configurations ---")
        for dl in set(item['dataloader_configs']):
            print(f"  {dl}")
            
        print("\n--- Dataset Pipeline ---")
        for dp in set(item['dataset_pipeline']):
            print(f"  {dp}")
            
        print("\n--- External Repositories (git clone) ---")
        if item['external_repos']:
            for er in item['external_repos']:
                print(f"  ⚠️ {er}")
        else:
            print("  ✅ ZERO external git clones found (fully self-contained).")
            
        print("\n--- Training Loop & Optimization ---")
        for tl in list(set(item['training_loop']))[:6]:
            print(f"  {tl}")
            
        print("\n--- Evaluation & Metrics ---")
        for em in list(set(item['eval_metrics']))[:6]:
            print(f"  {em}")
        print("\n")
