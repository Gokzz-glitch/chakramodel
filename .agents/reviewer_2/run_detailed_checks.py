import json
import os
import sys

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

def analyze_details():
    results = {}
    for nb_name in NOTEBOOKS:
        nb_path = os.path.join(NOTEBOOKS_DIR, nb_name)
        with open(nb_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
        
        cells = nb.get("cells", [])
        code_sources = [ "".join(c.get("source", [])) for c in cells if c.get("cell_type") == "code" ]
        
        res = {
            "notebook": nb_name,
            "num_cells": len(cells),
            "num_code_cells": len(code_sources),
            "features": {}
        }
        
        full_code = "\n".join(code_sources)
        
        # Check specific features per notebook
        if "Combo1" in nb_name:
            res["features"]["resnet101"] = "resnet101" in full_code.lower()
            res["features"]["yolo_import"] = "from ultralytics import YOLO" in full_code or "YOLO(" in full_code
            res["features"]["dice_focal"] = "DiceFocalLoss" in full_code
            res["features"]["mc_dropout"] = "mc_dropout" in full_code or "MC Dropout" in full_code or "stochastic" in full_code.lower()
            res["features"]["bs32_workers4"] = "32" in full_code and "4" in full_code
            
        elif "Combo2" in nb_name:
            res["features"]["resnet101"] = "resnet101" in full_code.lower()
            res["features"]["topological_loss"] = "Topological" in full_code or "Topo" in full_code or "Betti" in full_code or "euler" in full_code.lower()
            res["features"]["bs32_workers4"] = "32" in full_code and "4" in full_code
            
        elif "Combo3" in nb_name:
            res["features"]["resnet101"] = "resnet101" in full_code.lower()
            res["features"]["adabn"] = "AdaBN" in full_code or "BatchNorm2d" in full_code and "adapt" in full_code.lower()
            res["features"]["zero_backprop_adaptation"] = "torch.no_grad()" in full_code or "momentum = None" in full_code
            res["features"]["bs32_workers4"] = "32" in full_code and "4" in full_code
            
        elif "Combo4" in nb_name:
            res["features"]["resnet101"] = "resnet101" in full_code.lower()
            res["features"]["diffusion_or_controlnet"] = "StableDiffusion" in full_code or "ControlNet" in full_code or "diffusers" in full_code or "synthetic" in full_code.lower()
            res["features"]["mc_dropout_filter"] = "mc_dropout" in full_code or "uncertainty" in full_code.lower()
            res["features"]["retraining_loop"] = "combined_train_loader" in full_code or "retraining" in full_code.lower()
            res["features"]["bs32_workers4"] = "32" in full_code and "4" in full_code
            
        elif "Combo5" in nb_name:
            res["features"]["resnet101"] = "resnet101" in full_code.lower()
            res["features"]["fedavg"] = "FedAvg" in full_code or "aggregate" in full_code.lower()
            res["features"]["multi_client"] = "Hospital" in full_code or "client" in full_code.lower()
            res["features"]["bs32_workers4"] = "32" in full_code and "4" in full_code
            
        elif "Combo6" in nb_name:
            res["features"]["vit_large"] = "vit_large_patch16_384" in full_code
            res["features"]["progressive_decoder"] = "Decoder" in full_code or "ConvTranspose2d" in full_code
            res["features"]["split_conformal"] = "conformal" in full_code.lower() or "calibrate" in full_code.lower()
            res["features"]["trisplit_dataloaders"] = "cal_loader" in full_code or "build_trisplit_dataloaders" in full_code
            res["features"]["bs32_workers4"] = "32" in full_code and "4" in full_code
            
        # Common checks
        res["common"] = {
            "kvasir_download_func": "setup_kvasir_seg_dataset" in full_code,
            "kaggle_working_path": "/kaggle/working/data/kvasir-seg" in full_code,
            "pip_install_present": "!pip install" in "\n".join([ "".join(c.get("source", [])) for c in cells ]),
            "no_git_clone": "git clone" not in full_code,
            "has_amp_fp16": "autocast" in full_code,
            "has_gradscaler": "GradScaler" in full_code,
        }
        
        results[nb_name] = res
        
    return results

if __name__ == "__main__":
    res = analyze_details()
    print(json.dumps(res, indent=2))
